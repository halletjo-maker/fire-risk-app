"""Module 1 — identification par adresse mail (sans mot de passe)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from ..database import get_conn

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
