"""Dépendances FastAPI partagées."""
from __future__ import annotations

from fastapi import Header, HTTPException

from .database import get_conn


def current_user(x_user_email: str | None = Header(default=None)) -> dict:
    """Utilisateur identifié par l'en-tête X-User-Email (envoyé par le frontend)."""
    if not x_user_email:
        raise HTTPException(status_code=401, detail="Utilisateur non identifié")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, created_at, last_login_at FROM users WHERE email = ?",
            (x_user_email.strip(),),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu")
    return dict(row)
