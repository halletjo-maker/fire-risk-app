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


def admin_user(request: Request) -> dict:
    """Utilisateur connecté ET administrateur (invitations, gestion des membres)."""
    user = current_user(request)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Réservé à l'administrateur de l'application.")
    return user
