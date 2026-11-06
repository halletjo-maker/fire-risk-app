"""Notifications sur le téléphone : abonnement de l'appareil, réglages, test."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import get_conn
from ..deps import current_user
from ..services import push

router = APIRouter(prefix="/push", tags=["notifications"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000, pattern=r"^https://")
    keys: Keys


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


class KindsIn(BaseModel):
    alerts: bool | None = None
    trades: bool | None = None
    access: bool | None = None


@router.get("")
def status(user: dict = Depends(current_user)) -> dict:
    return push.status(user["id"])


@router.post("/subscribe")
def subscribe(payload: SubscriptionIn, request: Request, user: dict = Depends(current_user)) -> dict:
    push.subscribe(user["id"], payload.endpoint, payload.keys.p256dh, payload.keys.auth,
                   request.headers.get("user-agent"))
    return push.status(user["id"])


@router.post("/unsubscribe")
def unsubscribe(payload: EndpointIn, user: dict = Depends(current_user)) -> dict:
    push.unsubscribe(user["id"], payload.endpoint)
    return push.status(user["id"])


@router.put("/kinds")
def kinds(payload: KindsIn, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        for kind, value in payload.model_dump(exclude_none=True).items():
            conn.execute(f"UPDATE users SET {push.KINDS[kind]} = ? WHERE id = ?", (int(value), user["id"]))
    return push.status(user["id"])


@router.post("/test")
def test(user: dict = Depends(current_user)) -> dict:
    n = push.notify(user["id"], None, "MM100 ✅", "Les notifications fonctionnent sur cet appareil.", "/")
    if not n:
        raise HTTPException(status_code=409, detail="Aucun appareil n'a reçu la notification. Réactive-les sur ce téléphone.")
    return {"sent": n}
