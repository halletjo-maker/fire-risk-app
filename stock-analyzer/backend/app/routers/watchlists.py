"""Watchlists — socle minimal (liste + création). Gestion complète au Module 8."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..config import WATCHLIST_COLORS
from ..database import get_conn
from ..deps import current_user

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = WATCHLIST_COLORS[0]

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom est obligatoire")
        return v

    @field_validator("color")
    @classmethod
    def check_color(cls, v: str) -> str:
        if v.upper() not in WATCHLIST_COLORS:
            raise ValueError("Couleur non proposée")
        return v.upper()


@router.get("/colors")
def colors() -> dict:
    return {"colors": WATCHLIST_COLORS}


@router.get("")
def list_watchlists(user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.name, w.color, w.position, w.created_at,
                   COUNT(i.id) AS item_count
            FROM watchlists w
            LEFT JOIN watchlist_items i ON i.watchlist_id = w.id
            WHERE w.user_id = ?
            GROUP BY w.id
            ORDER BY w.position, w.id
            """,
            (user["id"],),
        ).fetchall()
    return {"watchlists": [dict(r) for r in rows]}


@router.post("", status_code=201)
def create_watchlist(payload: WatchlistIn, user: dict = Depends(current_user)) -> dict:
    try:
        with get_conn() as conn:
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM watchlists WHERE user_id = ?",
                (user["id"],),
            ).fetchone()[0]
            cur = conn.execute(
                "INSERT INTO watchlists (user_id, name, color, position) VALUES (?, ?, ?, ?)",
                (user["id"], payload.name, payload.color, pos),
            )
            row = conn.execute(
                "SELECT id, name, color, position, created_at, 0 AS item_count "
                "FROM watchlists WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Une watchlist porte déjà ce nom")
    return {"watchlist": dict(row)}
