"""Module 1 — compte utilisateur : adresse mail + mot de passe, session par cookie."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from ..database import get_conn
from ..deps import admin_user, current_user
from ..services import auth
from ..services.mail import sender

router = APIRouter(prefix="/users", tags=["utilisateur"])

BAD_CREDENTIALS = "Adresse mail ou mot de passe incorrect."


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)


class RegisterIn(Credentials):
    invitation: str | None = Field(default=None, max_length=200)


class InvitationIn(BaseModel):
    email: EmailStr
    app_url: str | None = Field(default=None, max_length=200)  # adresse vue par l'invitant (lien du mail)


class PreferencesIn(BaseModel):
    monthly_report: bool


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)
    new_password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)


def _user(conn, user_id: int) -> dict:
    row = conn.execute(
        "SELECT id, email, is_admin, created_at, last_login_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return {**dict(row), "is_admin": bool(row["is_admin"])}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "inconnu"


@router.get("/current")
def current(request: Request) -> dict:
    """Utilisateur de la session en cours (cookie), et état de l'écran de connexion."""
    return {
        "user": auth.user_for_token(auth.token_from_request(request)),
        "setup_required": auth.setup_required(),
        "registration_open": auth.registration_open(),
    }


@router.get("/invitation/{token}")
def invitation(token: str) -> dict:
    """Écran « tu es invité » : adresse concernée (public, jeton secret à usage unique)."""
    with get_conn() as conn:
        inv = auth.invitation_for_token(conn, token)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitation invalide, déjà utilisée ou expirée.")
    return {"email": inv["email"], "invited_by": inv["invited_by"], "expires_at": inv["expires_at"]}


@router.post("/register")
def register(payload: RegisterIn, request: Request, response: Response) -> dict:
    """Création du mot de passe : premier compte, adresse de ALLOWED_EMAILS, ou invitation."""
    email = payload.email.strip().lower()
    problem = auth.password_problem(payload.password)
    with get_conn() as conn:
        inv = auth.invitation_for_token(conn, payload.invitation) if payload.invitation else None
    if payload.invitation:
        if inv is None or inv["email"].lower() != email:
            raise HTTPException(status_code=403, detail="Invitation invalide, déjà utilisée ou expirée.")
    elif not auth.registration_allowed(email):
        raise HTTPException(status_code=403, detail="La création de compte est fermée sur cette installation.")
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    # Compte créé sans invitation (premier compte ou ALLOWED_EMAILS) = administrateur
    is_admin = inv is None
    with get_conn() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if row and row["password_hash"]:
            raise HTTPException(status_code=409, detail="Ce compte a déjà un mot de passe : connecte-toi.")
        if row:  # compte existant sans mot de passe : on garde ses watchlists
            user_id = row["id"]
        else:
            user_id = conn.execute("INSERT INTO users (email) VALUES (?)", (email,)).lastrowid
        auth.set_password(conn, user_id, payload.password)
        conn.execute("UPDATE users SET last_login_at = datetime('now'), is_admin = MAX(is_admin, ?) WHERE id = ?",
                     (int(is_admin), user_id))
        if inv:
            conn.execute("UPDATE invitations SET used_at = datetime('now') WHERE id = ?", (inv["id"],))
        token = auth.create_session(conn, user_id)
        user = _user(conn, user_id)
    auth.set_cookie(response, request, token)
    return {"user": user}


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response) -> dict:
    email, ip = payload.email.strip().lower(), _client_ip(request)
    wait = auth.throttle.blocked(email, ip)
    if wait:
        raise HTTPException(status_code=429, detail=f"Trop d'essais. Réessaie dans {wait} minute(s).")
    with get_conn() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not auth.verify_password(payload.password, row["password_hash"] if row else None):
        auth.throttle.fail(email, ip)
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS)
    auth.throttle.success(email)
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],))
        token = auth.create_session(conn, row["id"])
        user = _user(conn, row["id"])
    auth.set_cookie(response, request, token)
    return {"user": user}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    auth.delete_session(auth.token_from_request(request))
    auth.clear_cookie(response)
    return {"user": None}


@router.post("/password")
def change_password(payload: PasswordChange, request: Request, user: dict = Depends(current_user)) -> dict:
    """Change le mot de passe et déconnecte les autres appareils."""
    with get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()[0]
    if not auth.verify_password(payload.current_password, stored):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect.")
    problem = auth.password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    with get_conn() as conn:
        auth.set_password(conn, user["id"], payload.new_password)
        auth.delete_other_sessions(conn, user["id"], auth.token_from_request(request))
    return {"ok": True}


@router.put("/me/preferences")
def preferences(payload: PreferencesIn, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        conn.execute("UPDATE users SET monthly_report = ? WHERE id = ?", (int(payload.monthly_report), user["id"]))
    return {"monthly_report": payload.monthly_report}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    """Profil de l'utilisateur connecté + quelques chiffres."""
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
    with get_conn() as conn:
        pref = conn.execute("SELECT monthly_report FROM users WHERE id = ?", (uid,)).fetchone()
    return {"user": user, "stats": dict(stats), "preferences": {"monthly_report": bool(pref["monthly_report"]) if pref else True}}


# ── Administration : inviter des amis, gérer les membres ───────────────────

def _app_url(payload_url: str | None, request: Request) -> str:
    url = (payload_url or "").strip().rstrip("/")
    if url.startswith(("http://", "https://")) and " " not in url:
        return url
    return str(request.base_url).rstrip("/")


@router.get("/members")
def members(admin: dict = Depends(admin_user)) -> dict:
    with get_conn() as conn:
        users = conn.execute(
            "SELECT id, email, is_admin, created_at, last_login_at, password_hash IS NOT NULL AS active "
            "FROM users ORDER BY is_admin DESC, created_at"
        ).fetchall()
        invitations = conn.execute(
            "SELECT id, email, created_at, expires_at FROM invitations "
            "WHERE used_at IS NULL AND expires_at > datetime('now') ORDER BY created_at DESC"
        ).fetchall()
    return {
        "members": [{**dict(u), "is_admin": bool(u["is_admin"]), "active": bool(u["active"]),
                     "is_me": u["id"] == admin["id"]} for u in users],
        "invitations": [dict(i) for i in invitations],
    }


@router.post("/invitations", status_code=201)
def invite(payload: InvitationIn, request: Request, admin: dict = Depends(admin_user)) -> dict:
    """Crée un lien d'invitation (7 jours, usage unique) et l'envoie par mail si le SMTP est configuré."""
    email = payload.email.strip().lower()
    with get_conn() as conn:
        existing = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if existing and existing["password_hash"]:
            raise HTTPException(status_code=409, detail="Cette personne a déjà un compte.")
        token, inv = auth.create_invitation(conn, email, admin["id"])
    link = f"{_app_url(payload.app_url, request)}/?invitation={token}"
    text = (
        f"Bonjour,\n\n{admin['email']} t'invite à utiliser Analyse Boursière, une application d'aide "
        "à la décision pour tes placements (analyse technique, fondamentale, actualités, alertes).\n\n"
        f"Crée ton mot de passe ici (lien personnel, valable {auth.INVITATION_DAYS} jours) :\n{link}\n\n"
        "Aide à la décision automatisée, pas un conseil en investissement (MiFID II)."
    )
    mail = sender.send(email, "Invitation : Analyse Boursière", text)
    return {"invitation": inv, "link": link, "mail": {"sent": mail["delivered"], "status": mail["status"]}}


@router.delete("/invitations/{inv_id}")
def cancel_invitation(inv_id: int, admin: dict = Depends(admin_user)) -> dict:
    with get_conn() as conn:
        n = conn.execute("DELETE FROM invitations WHERE id = ? AND used_at IS NULL", (inv_id,)).rowcount
    if not n:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(user_id: int, admin: dict = Depends(admin_user)) -> dict:
    """Retire l'accès d'un membre : compte, sessions, watchlists et alertes supprimés."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Tu ne peux pas supprimer ton propre compte.")
    with get_conn() as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        if row["is_admin"]:
            raise HTTPException(status_code=400, detail="Un administrateur ne peut pas être supprimé ici.")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}
