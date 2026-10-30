"""Module 8 — watchlists multiples (nom + couleur) et produits suivis."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..config import WATCHLIST_COLORS
from ..database import get_conn
from ..deps import current_user
from ..services import market
from ..services import suggestions as suggestions_service
from ..services import watchlist as watchlist_service

router = APIRouter(prefix="/watchlists", tags=["watchlists"])

ITEM_COLUMNS = (
    "i.id, i.watchlist_id, i.symbol, i.product_id, i.name, i.isin, i.exchange, i.product_type, i.position, "
    "i.last_price, i.last_change_pct, i.last_score, i.last_signal, i.last_refresh_at, i.added_at, "
    "i.buy_price, i.buy_kind, i.buy_note, i.sell_price, i.sell_note, "
    "(SELECT COUNT(*) FROM alerts a WHERE a.item_id = i.id AND a.enabled = 1) AS alert_count"
)


# ---------------------------------------------------------------- schémas
def _clean_name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Le nom est obligatoire")
    return v


def _check_color(v: str) -> str:
    if v.upper() not in WATCHLIST_COLORS:
        raise ValueError("Couleur non proposée")
    return v.upper()


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = WATCHLIST_COLORS[0]

    @field_validator("name")
    @classmethod
    def v_name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("color")
    @classmethod
    def v_color(cls, v: str) -> str:
        return _check_color(v)


class WatchlistPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = None

    @field_validator("name")
    @classmethod
    def v_name(cls, v: str | None) -> str | None:
        return _clean_name(v) if v is not None else v

    @field_validator("color")
    @classmethod
    def v_color(cls, v: str | None) -> str | None:
        return _check_color(v) if v is not None else v


class DuplicateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)


class ItemIn(BaseModel):
    product_id: str = Field(min_length=4, max_length=300, description="ex. yf:NOW ou bo:/bourse/...")
    isin: str | None = None


class OrderIn(BaseModel):
    ids: list[int]


# ---------------------------------------------------------------- outils
def _own(conn, watchlist_id: int, user_id: int):
    row = conn.execute(
        "SELECT id, name, color, position, created_at FROM watchlists WHERE id = ? AND user_id = ?",
        (watchlist_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Watchlist introuvable")
    return row


def _summary(conn, watchlist_id: int) -> dict:
    row = conn.execute(
        "SELECT w.id, w.name, w.color, w.position, w.created_at, COUNT(i.id) AS item_count "
        "FROM watchlists w LEFT JOIN watchlist_items i ON i.watchlist_id = w.id WHERE w.id = ? GROUP BY w.id",
        (watchlist_id,),
    ).fetchone()
    return dict(row)


def _unique_name(conn, user_id: int, base: str) -> str:
    names = {r["name"] for r in conn.execute("SELECT name FROM watchlists WHERE user_id = ?", (user_id,))}
    if base not in names:
        return base
    i = 2
    while f"{base} ({i})" in names:
        i += 1
    return f"{base} ({i})"


# ---------------------------------------------------------------- watchlists
@router.get("/colors")
def colors() -> dict:
    return {"colors": WATCHLIST_COLORS}


@router.get("")
def list_watchlists(user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.name, w.color, w.position, w.created_at, COUNT(i.id) AS item_count
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
                "SELECT COALESCE(MAX(position), -1) + 1 FROM watchlists WHERE user_id = ?", (user["id"],)
            ).fetchone()[0]
            cur = conn.execute(
                "INSERT INTO watchlists (user_id, name, color, position) VALUES (?, ?, ?, ?)",
                (user["id"], payload.name, payload.color, pos),
            )
            return {"watchlist": _summary(conn, cur.lastrowid)}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Une watchlist porte déjà ce nom")


@router.patch("/{watchlist_id}")
def update_watchlist(watchlist_id: int, payload: WatchlistPatch, user: dict = Depends(current_user)) -> dict:
    """Renommer et/ou changer la couleur."""
    try:
        with get_conn() as conn:
            _own(conn, watchlist_id, user["id"])
            if payload.name is not None:
                conn.execute("UPDATE watchlists SET name = ?, updated_at = datetime('now') WHERE id = ?",
                             (payload.name, watchlist_id))
            if payload.color is not None:
                conn.execute("UPDATE watchlists SET color = ?, updated_at = datetime('now') WHERE id = ?",
                             (payload.color, watchlist_id))
            return {"watchlist": _summary(conn, watchlist_id)}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Une watchlist porte déjà ce nom")


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: int, user: dict = Depends(current_user)) -> dict:
    """Supprime la watchlist, ses produits et leurs alertes (cascade SQLite)."""
    with get_conn() as conn:
        wl = _own(conn, watchlist_id, user["id"])
        items = conn.execute("SELECT COUNT(*) FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,)).fetchone()[0]
        alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts a JOIN watchlist_items i ON i.id = a.item_id WHERE i.watchlist_id = ?",
            (watchlist_id,),
        ).fetchone()[0]
        conn.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
    return {"deleted": {"id": watchlist_id, "name": wl["name"], "items": items, "alerts": alerts}}


@router.post("/{watchlist_id}/duplicate", status_code=201)
def duplicate_watchlist(watchlist_id: int, payload: DuplicateIn | None = None, user: dict = Depends(current_user)) -> dict:
    """Copie la watchlist et ses produits (les alertes ne sont pas copiées, pour éviter les doublons de mails)."""
    with get_conn() as conn:
        wl = _own(conn, watchlist_id, user["id"])
        name = _unique_name(conn, user["id"], (payload.name if payload and payload.name else f"{wl['name']} (copie)"))
        pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM watchlists WHERE user_id = ?",
                           (user["id"],)).fetchone()[0]
        new_id = conn.execute("INSERT INTO watchlists (user_id, name, color, position) VALUES (?, ?, ?, ?)",
                              (user["id"], name, wl["color"], pos)).lastrowid
        conn.execute(
            "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, isin, exchange, product_type, "
            "position, last_price, last_change_pct, last_score, last_signal, last_refresh_at, "
            "buy_price, buy_kind, buy_note, sell_price, sell_note) "
            "SELECT ?, symbol, product_id, name, isin, exchange, product_type, position, last_price, "
            "last_change_pct, last_score, last_signal, last_refresh_at, "
            "buy_price, buy_kind, buy_note, sell_price, sell_note FROM watchlist_items WHERE watchlist_id = ?",
            (new_id, watchlist_id),
        )
        return {"watchlist": _summary(conn, new_id)}


# ---------------------------------------------------------------- produits
@router.get("/{watchlist_id}/items")
def list_items(watchlist_id: int, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        wl = _own(conn, watchlist_id, user["id"])
        rows = conn.execute(
            f"SELECT {ITEM_COLUMNS} FROM watchlist_items i WHERE i.watchlist_id = ? ORDER BY i.position, i.id",
            (watchlist_id,),
        ).fetchall()
    return {"watchlist": dict(wl), "items": [dict(r) for r in rows]}


@router.post("/{watchlist_id}/items", status_code=201)
def add_item(watchlist_id: int, payload: ItemIn, background: BackgroundTasks,
             user: dict = Depends(current_user)) -> dict:
    """Ajoute un produit ; son score est calculé en arrière-plan juste après."""
    data = market.get_quote(payload.product_id, isin=payload.isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Produit introuvable ou cours indisponible")
    p, q = data["product"], data["quote"]
    symbol = p.get("symbol") or p.get("isin") or payload.product_id
    try:
        with get_conn() as conn:
            _own(conn, watchlist_id, user["id"])
            pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM watchlist_items WHERE watchlist_id = ?",
                               (watchlist_id,)).fetchone()[0]
            item_id = conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, isin, exchange, product_type, "
                "position, last_price, last_change_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (watchlist_id, symbol, payload.product_id, p.get("name"), p.get("isin"), p.get("exchange"),
                 p.get("type") or "AUTRE", pos, q.get("price"), q.get("change_pct")),
            ).lastrowid
            row = conn.execute(f"SELECT {ITEM_COLUMNS} FROM watchlist_items i WHERE i.id = ?", (item_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ce produit est déjà dans cette watchlist")
    background.add_task(watchlist_service.refresh_product, payload.product_id)
    return {"item": dict(row)}


@router.delete("/{watchlist_id}/items/{item_id}")
def remove_item(watchlist_id: int, item_id: int, user: dict = Depends(current_user)) -> dict:
    """Retire un produit ; ses alertes sont supprimées en même temps (cascade)."""
    with get_conn() as conn:
        _own(conn, watchlist_id, user["id"])
        item = conn.execute("SELECT id, name, symbol FROM watchlist_items WHERE id = ? AND watchlist_id = ?",
                            (item_id, watchlist_id)).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Produit introuvable dans cette watchlist")
        alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE item_id = ?", (item_id,)).fetchone()[0]
        conn.execute("DELETE FROM watchlist_items WHERE id = ?", (item_id,))
    return {"deleted": {"id": item_id, "name": item["name"], "symbol": item["symbol"], "alerts": alerts}}


@router.put("/{watchlist_id}/items/order")
def reorder_items(watchlist_id: int, payload: OrderIn, user: dict = Depends(current_user)) -> dict:
    """Nouvel ordre des produits (glisser-déposer)."""
    with get_conn() as conn:
        _own(conn, watchlist_id, user["id"])
        existing = {r["id"] for r in conn.execute("SELECT id FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,))}
        if set(payload.ids) != existing or len(payload.ids) != len(existing):
            raise HTTPException(status_code=422, detail="La liste doit contenir exactement les produits de la watchlist")
        for pos, item_id in enumerate(payload.ids):
            conn.execute("UPDATE watchlist_items SET position = ? WHERE id = ?", (pos, item_id))
    return {"ok": True}


@router.post("/{watchlist_id}/refresh", status_code=202)
def refresh(watchlist_id: int, background: BackgroundTasks, user: dict = Depends(current_user)) -> dict:
    """Rafraîchissement immédiat (en plus de celui toutes les 15 minutes)."""
    with get_conn() as conn:
        _own(conn, watchlist_id, user["id"])
    background.add_task(watchlist_service.refresh_all, watchlist_id)
    return {"scheduled": True}


@router.get("/{watchlist_id}/suggestions")
def suggestions(watchlist_id: int, user: dict = Depends(current_user)) -> dict:
    """Produits à étudier, inspirés de la watchlist (calcul en arrière-plan : status pending puis ready)."""
    with get_conn() as conn:
        _own(conn, watchlist_id, user["id"])
    return suggestions_service.get_or_start(watchlist_id)
