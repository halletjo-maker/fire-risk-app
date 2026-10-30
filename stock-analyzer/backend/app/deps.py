"""Dépendances FastAPI partagées."""
from __future__ import annotations

from fastapi import HTTPException, Request

from .services import auth


def current_user(request: Request) -> dict:
    """Utilisateur de la session (cookie HttpOnly, ou en-tête Authorization: Bearer)."""
    user = auth.user_for_token(auth.token_from_request(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Session expirée : reconnecte-toi.")
    return user
