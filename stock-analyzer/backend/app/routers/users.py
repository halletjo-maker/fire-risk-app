"""Module 1 — compte utilisateur : adresse mail + mot de passe, session par cookie."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from ..database import get_conn
from ..deps import current_user
from ..services import auth

router = APIRouter(prefix="/users", tags=["utilisateur"])

BAD_CREDENTIALS = "Adresse mail ou mot de passe incorrect."


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)
    new_password: str = Field(min_length=1, max_length=auth.PASSWORD_MAX)


def _user(conn, user_id: int) -> dict:
    row = conn.execute(
        "SELECT id, email, created_at, last_login_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row)


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


@router.post("/register")
def register(payload: Credentials, request: Request, response: Response) -> dict:
    """Création du mot de passe (premier compte, ou adresse listée dans ALLOWED_EMAILS)."""
    email = payload.email.strip().lower()
    if not auth.registration_allowed(email):
        raise HTTPException(status_code=403, detail="La création de compte est fermée sur cette installation.")
    problem = auth.password_problem(payload.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    with get_conn() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if row and row["password_hash"]:
            raise HTTPException(status_code=409, detail="Ce compte a déjà un mot de passe : connecte-toi.")
        if row:  # compte existant sans mot de passe : on garde ses watchlists
            user_id = row["id"]
        else:
            user_id = conn.execute("INSERT INTO users (email) VALUES (?)", (email,)).lastrowid
        auth.set_password(conn, user_id, payload.password)
        conn.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,))
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
    return {"user": user, "stats": dict(stats)}
