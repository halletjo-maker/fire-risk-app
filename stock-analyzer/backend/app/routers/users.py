"""Module 1 — identification par adresse mail (sans mot de passe)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from ..database import get_conn
from ..deps import current_user

router = APIRouter(prefix="/users", tags=["utilisateur"])

ACTIVE_USER_KEY = "active_user_id"


class LoginIn(BaseModel):
    email: EmailStr


def _user(conn, user_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, email, created_at, last_login_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


@router.post("/login")
def login(payload: LoginIn) -> dict:
    """Crée l'utilisateur au besoin et le mémorise comme utilisateur actif."""
    email = payload.email.strip().lower()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email) VALUES (?) "
            "ON CONFLICT(email) DO UPDATE SET last_login_at = datetime('now')",
            (email,),
        )
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (ACTIVE_USER_KEY, str(user_id)),
        )
        return {"user": _user(conn, user_id)}


@router.get("/current")
def current() -> dict:
    """Utilisateur mémorisé (reconnu automatiquement au lancement suivant)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (ACTIVE_USER_KEY,)
        ).fetchone()
        user = _user(conn, int(row["value"])) if row and row["value"] else None
    return {"user": user}


@router.post("/logout")
def logout() -> dict:
    """« Changer d'utilisateur » : oublie l'utilisateur actif (ses données restent)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (ACTIVE_USER_KEY,))
    return {"user": None}


@router.get("/known")
def known_users() -> dict:
    """Comptes déjà utilisés sur cette installation (choix rapide à l'écran d'accueil)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT email, last_login_at FROM users ORDER BY last_login_at DESC LIMIT 10"
        ).fetchall()
    return {"users": [dict(r) for r in rows]}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    """Profil de l'utilisateur identifié + quelques chiffres."""
    uid = user["id"]
    with get_conn() as conn:
        stats = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM watchlists WHERE user_id = :u) AS watchlists,
              (SELECT COUNT(*) FROM watchlist_items i
                 JOIN watchlists w ON w.id = i.watchlist_id WHERE w.user_id = :u) AS products,
              (SELECT COUNT(*) FROM alerts a
                 JOIN watchlist_items i ON i.id = a.item_id
                 JOIN watchlists w ON w.id = i.watchlist_id
                 WHERE w.user_id = :u AND a.enabled = 1) AS active_alerts,
              (SELECT COUNT(*) FROM analysis_history WHERE user_id = :u) AS analyses
            """,
            {"u": uid},
        ).fetchone()
    return {"user": user, "stats": dict(stats)}
