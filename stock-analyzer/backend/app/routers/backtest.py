"""Tester la méthode sur le passé."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_conn
from ..deps import current_user
from ..services import backtest

router = APIRouter(prefix="/backtest", tags=["test de la méthode"])


class BacktestIn(BaseModel):
    watchlist_id: int
    years: int = Field(default=10, ge=3, le=10)


@router.get("")
def latest(user: dict = Depends(current_user)) -> dict:
    return {"backtest": backtest.latest(user["id"])}


@router.post("", status_code=202)
def launch(payload: BacktestIn, user: dict = Depends(current_user)) -> dict:
    try:
        bid = backtest.start(user["id"], payload.watchlist_id, payload.years)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"backtest": backtest.latest(user["id"]), "id": bid}
