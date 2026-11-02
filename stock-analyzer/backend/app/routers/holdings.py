"""Mes vraies positions : opérations, plus-values et taxe belge estimée (privé, par utilisateur)."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..database import get_conn
from ..deps import current_user
from ..services import holdings

router = APIRouter(prefix="/holdings", tags=["mes positions"])


class TxIn(BaseModel):
    product_id: str = Field(min_length=3, max_length=120)
    symbol: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="EUR", min_length=3, max_length=4)
    kind: str = Field(pattern="^(BUY|SELL)$")
    day: str
    qty: float = Field(gt=0, le=1e9)
    price: float = Field(gt=0, le=1e9)
    fees_eur: float = Field(default=0, ge=0, le=1e6)
    fx: float | None = Field(default=None, gt=0, le=1e6)

    @field_validator("day")
    @classmethod
    def valid_day(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("Date au format AAAA-MM-JJ")
        d = date.fromisoformat(v)
        if d > date.today() or d.year < 1990:
            raise ValueError("Date impossible")
        return v


class RefIn(BaseModel):
    product_id: str = Field(min_length=3, max_length=120)
    ref_price: float = Field(gt=0, le=1e9)
    currency: str = Field(default="EUR", min_length=3, max_length=4)


@router.get("")
def overview(user: dict = Depends(current_user)) -> dict:
    return holdings.summary(user["id"])


@router.post("/tx", status_code=201)
def add(payload: TxIn, background: BackgroundTasks, user: dict = Depends(current_user)) -> dict:
    try:
        r = holdings.add_transaction(user["id"], payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    background.add_task(holdings.refresh_quotes)  # cours et stop du nouveau titre
    return {**r, **holdings.summary(user["id"])}


@router.delete("/tx/{tx_id}")
def remove(tx_id: int, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        n = conn.execute("DELETE FROM holding_tx WHERE id = ? AND user_id = ?", (tx_id, user["id"])).rowcount
    if not n:
        raise HTTPException(status_code=404, detail="Opération introuvable")
    return holdings.summary(user["id"])


@router.put("/ref")
def set_ref(payload: RefIn, user: dict = Depends(current_user)) -> dict:
    """Valeur au 31/12/2025 encodée à la main (titre inconnu de Yahoo, ou correction)."""
    fx = holdings.fx_on(payload.currency, holdings.REF_DAY)
    if not fx:
        raise HTTPException(status_code=400, detail="Taux de change du 31/12/2025 introuvable.")
    holdings.set_ref(user["id"], payload.product_id, payload.ref_price, fx, "encodé à la main")
    return holdings.summary(user["id"])
