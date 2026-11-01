"""Mots de passe, sessions et protection contre les essais répétés.

- Mots de passe hachés avec scrypt (bibliothèque standard), jamais stockés en clair.
- Session = jeton aléatoire envoyé dans un cookie HttpOnly ; seule son empreinte SHA-256 est en base.
- Après trop d'échecs, la connexion est bloquée 15 minutes (par adresse mail et par IP).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from ..config import get_settings
from ..database import get_conn

COOKIE_NAME = "ab_session"
SESSION_DAYS = 30
INVITATION_DAYS = 7
PASSWORD_MIN = 10
PASSWORD_MAX = 128

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


# ── Mots de passe ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Calcul factice : même durée de réponse que pour un compte existant
        hashlib.scrypt(password.encode(), salt=b"0" * 16, dklen=32, **_SCRYPT)
        return False
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                dklen=len(expected), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def password_problem(password: str) -> str | None:
    if len(password) < PASSWORD_MIN:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN} caractères."
    if len(password) > PASSWORD_MAX:
        return f"Le mot de passe ne peut pas dépasser {PASSWORD_MAX} caractères."
    if password.strip() != password or not password.strip():
        return "Le mot de passe ne peut pas commencer ou finir par un espace."
    return None


def set_password(conn, user_id: int, password: str) -> None:
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))


# ── Création de compte ─────────────────────────────────────────────────────

def setup_required() -> bool:
    """Vrai tant qu'aucun compte n'a de mot de passe (première utilisation)."""
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM users WHERE password_hash IS NOT NULL LIMIT 1").fetchone() is None


def registration_allowed(email: str) -> bool:
    """ALLOWED_EMAILS renseigné : seules ces adresses. Sinon : seulement le tout premier compte."""
    allowed = get_settings().allowed_emails
    if allowed:
        return email.lower() in allowed
    return setup_required()


def registration_open() -> bool:
    return bool(get_settings().allowed_emails) or setup_required()


# ── Sessions ───────────────────────────────────────────────────────────────

def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) "
        f"VALUES (?, ?, datetime('now', '+{SESSION_DAYS} days'))",
        (_digest(token), user_id),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
    return token


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    h = _digest(token)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.is_admin, u.created_at, u.last_login_at, s.last_seen_at "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > datetime('now')",
            (h,),
        ).fetchone()
        if row is None:
            return None
        # Session glissante : prolongée au plus une fois par heure
        if conn.execute("SELECT ? < datetime('now', '-1 hour')", (row["last_seen_at"],)).fetchone()[0]:
            conn.execute(
                "UPDATE sessions SET last_seen_at = datetime('now'), "
                f"expires_at = datetime('now', '+{SESSION_DAYS} days') WHERE token_hash = ?",
                (h,),
            )
    user = dict(row)
    user.pop("last_seen_at")
    user["is_admin"] = bool(user["is_admin"])
    return user


def delete_session(token: str | None) -> None:
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))


def delete_other_sessions(conn, user_id: int, keep_token: str | None) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash IS NOT ?",
                 (user_id, _digest(keep_token) if keep_token else None))


def token_from_request(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(COOKIE_NAME)


def set_cookie(response, request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, path="/",
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


# ── Invitations ────────────────────────────────────────────────────────────

def create_invitation(conn, email: str, invited_by: int, anonymous: bool = False) -> tuple[str, dict]:
    """Remplace l'invitation en attente pour cette adresse ; renvoie (jeton, invitation)."""
    conn.execute("DELETE FROM invitations WHERE email = ? AND used_at IS NULL", (email,))
    token = secrets.token_urlsafe(32)
    inv_id = conn.execute(
        "INSERT INTO invitations (token_hash, email, invited_by, anonymous, expires_at) "
        f"VALUES (?, ?, ?, ?, datetime('now', '+{INVITATION_DAYS} days'))",
        (_digest(token), email, invited_by, int(anonymous)),
    ).lastrowid
    row = conn.execute("SELECT id, email, created_at, expires_at FROM invitations WHERE id = ?", (inv_id,)).fetchone()
    return token, dict(row)


def invitation_for_token(conn, token: str | None) -> dict | None:
    """Invitation valide (ni utilisée, ni expirée) correspondant au jeton."""
    if not token:
        return None
    row = conn.execute(
        "SELECT i.id, i.email, i.expires_at, CASE WHEN i.anonymous THEN NULL ELSE u.email END AS invited_by "
        "FROM invitations i "
        "LEFT JOIN users u ON u.id = i.invited_by "
        "WHERE i.token_hash = ? AND i.used_at IS NULL AND i.expires_at > datetime('now')",
        (_digest(token),),
    ).fetchone()
    return dict(row) if row else None


# ── Mot de passe oublié ────────────────────────────────────────────────────
RESET_MINUTES = 60


def create_reset(conn, user_id: int) -> str:
    """Nouveau lien de réinitialisation (les précédents non utilisés sont annulés)."""
    conn.execute("DELETE FROM password_resets WHERE user_id = ? AND used_at IS NULL", (user_id,))
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO password_resets (token_hash, user_id, expires_at) "
                 f"VALUES (?, ?, datetime('now', '+{RESET_MINUTES} minutes'))", (_digest(token), user_id))
    return token


def reset_for_token(conn, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT r.token_hash, u.id AS user_id, u.email FROM password_resets r JOIN users u ON u.id = r.user_id "
        "WHERE r.token_hash = ? AND r.used_at IS NULL AND r.expires_at > datetime('now')", (_digest(token),)
    ).fetchone()
    return dict(row) if row else None


# ── Limitation des essais ──────────────────────────────────────────────────

class Throttle:
    """Compte les échecs récents ; bloque au-delà de la limite pendant la fenêtre."""

    WINDOW = 15 * 60
    LIMITS = {"email": 5, "ip": 20}

    def __init__(self) -> None:
        self._fails: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque:
        q = self._fails[key]
        while q and q[0] < now - self.WINDOW:
            q.popleft()
        return q

    def blocked(self, email: str, ip: str) -> int:
        """Minutes d'attente restantes (0 = autorisé)."""
        now = time.monotonic()
        wait = 0.0
        with self._lock:
            for kind, key in (("email", email), ("ip", ip)):
                q = self._recent(f"{kind}:{key}", now)
                if len(q) >= self.LIMITS[kind]:
                    wait = max(wait, q[0] + self.WINDOW - now)
        return int(wait // 60) + 1 if wait > 0 else 0

    def fail(self, email: str, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._fails[f"email:{email}"].append(now)
            self._fails[f"ip:{ip}"].append(now)

    def success(self, email: str) -> None:
        with self._lock:
            self._fails.pop(f"email:{email}", None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()


throttle = Throttle()
