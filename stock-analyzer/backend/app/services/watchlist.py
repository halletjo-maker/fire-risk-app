"""Module 8 — mise à jour des produits suivis (prix, variation, score /10, signal)."""
from __future__ import annotations

import logging

from ..database import get_conn
from . import analysis, targets

logger = logging.getLogger(__name__)


def refresh_product(product_id: str) -> dict | None:
    """Analyse complète d'un produit et mise à jour de toutes les lignes qui le suivent."""
    try:
        full = analysis.run(product_id)
    except Exception:
        logger.exception("Rafraîchissement impossible : %s", product_id)
        return None
    if full is None:
        return None
    d, q = full["decision"], full["quote"]
    values = {
        "price": q.get("price"),
        "change": q.get("change_pct"),
        "score": d.get("score") if d.get("available") else None,
        "signal": d.get("signal") if d.get("available") else None,
    }
    try:
        levels = targets.compute(full) or {}
    except Exception:
        logger.exception("Cours cibles impossibles : %s", product_id)
        levels = {}
    for k in ("buy_price", "buy_kind", "buy_note", "sell_price", "sell_note"):
        values[k] = levels.get(k)
    with get_conn() as conn:
        conn.execute(
            "UPDATE watchlist_items SET last_price = :price, last_change_pct = :change, last_score = :score, "
            "last_signal = :signal, buy_price = :buy_price, buy_kind = :buy_kind, buy_note = :buy_note, "
            "sell_price = :sell_price, sell_note = :sell_note, last_refresh_at = datetime('now') "
            "WHERE product_id = :pid",
            {**values, "pid": product_id},
        )
    return values


def refresh_all(watchlist_id: int | None = None) -> int:
    """Rafraîchit chaque produit une seule fois, même s'il figure dans plusieurs watchlists."""
    with get_conn() as conn:
        if watchlist_id is None:
            rows = conn.execute("SELECT DISTINCT product_id FROM watchlist_items WHERE product_id IS NOT NULL").fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT product_id FROM watchlist_items WHERE watchlist_id = ? AND product_id IS NOT NULL",
                (watchlist_id,),
            ).fetchall()
    done = 0
    for r in rows:
        if refresh_product(r["product_id"]) is not None:
            done += 1
    return done
