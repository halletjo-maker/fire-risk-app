"""Suggestions d'achat inspirées d'une watchlist.

Pour les produits suivis (en priorité ceux au meilleur score), on récupère les valeurs que
Yahoo Finance juge similaires, on écarte celles déjà suivies, puis on garde celles dont la
tendance technique est favorable (score ≥ 5,5/10). Un ETF monde est proposé en diversification
si la watchlist n'en contient pas. Calcul en arrière-plan (≈ 30 s), puis cache 6 heures.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timezone

from ..database import get_conn
from . import report
from .sources import cache

logger = logging.getLogger(__name__)

TTL = 6 * 3600
RETRY_AFTER_FAILURE = 10 * 60
MAX_BASES = 6          # produits de la watchlist servant de point de départ
PEERS_PER_BASE = 5
MAX_CANDIDATES = 8     # candidats évalués (limite les requêtes vers les sources)
MAX_SUGGESTIONS = 4
MIN_SCORE = 5.5

_running: set[str] = set()
_failed: dict[str, float] = {}
_lock = threading.Lock()


def _items(watchlist_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT symbol, product_id, name, product_type, last_score, last_signal FROM watchlist_items "
            "WHERE watchlist_id = ? AND product_id IS NOT NULL", (watchlist_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def _key(watchlist_id: int, items: list[dict]) -> str:
    ids = ",".join(sorted(i["product_id"] for i in items))
    return f"sugg:{watchlist_id}:{hashlib.sha1(ids.encode()).hexdigest()[:12]}"


def get_or_start(watchlist_id: int) -> dict:
    """Suggestions prêtes (cache) ou lancement du calcul en arrière-plan."""
    items = _items(watchlist_id)
    if not items:
        return {"status": "ready", "items": [], "message": "Ajoute des produits à cette watchlist pour recevoir des suggestions."}
    key = _key(watchlist_id, items)
    cached = cache.get(key, TTL)
    if cached is not None:
        return {"status": "ready", **cached}
    with _lock:
        if time.monotonic() - _failed.get(key, -1e9) < RETRY_AFTER_FAILURE:
            return {"status": "ready", "items": [], "message": "Suggestions momentanément indisponibles. Réessaie plus tard."}
        if key not in _running:
            _running.add(key)
            threading.Thread(target=_compute, args=(key, items), daemon=True).start()
    return {"status": "pending"}


def _compute(key: str, items: list[dict]) -> None:
    try:
        cache.put(key, build(items), source="suggestions")
    except Exception:
        logger.exception("Suggestions impossibles (%s)", key)
        with _lock:
            _failed[key] = time.monotonic()
    finally:
        with _lock:
            _running.discard(key)


def _yahoo_symbol(item: dict) -> str | None:
    pid = item.get("product_id") or ""
    return pid[3:] if pid.startswith("yf:") else None


def build(items: list[dict]) -> dict:
    owned = {s for s in (_yahoo_symbol(i) for i in items) if s} | {i["symbol"] for i in items if i.get("symbol")}
    # Point de départ : les produits au meilleur signal / score
    bases = sorted(
        (i for i in items if _yahoo_symbol(i) and i.get("product_type") not in ("TURBO", "WARRANT")),
        key=lambda i: (i.get("last_signal") == "ACHAT", i.get("last_score") or 0), reverse=True,
    )[:MAX_BASES]

    votes: dict[str, list[str]] = {}
    for it in bases:
        sym = _yahoo_symbol(it)
        peers = report._peers(sym)
        if not peers and "." in sym:  # cotation européenne sans résultat : on essaie le ticker de base
            peers = report._peers(sym.split(".")[0])
        for peer in peers[:PEERS_PER_BASE]:
            if peer not in owned:
                votes.setdefault(peer, []).append(it["name"] or sym)

    ranked = sorted(votes, key=lambda s: len(votes[s]), reverse=True)[:MAX_CANDIDATES]
    scored = []
    for sym in ranked:
        snap = report._snapshot(sym)
        if snap and (snap.get("technical_score") or 0) >= MIN_SCORE:
            names = list(dict.fromkeys(votes[sym]))
            close_to = ", ".join(n.rstrip(".") for n in names[:2])
            scored.append({**snap, "kind": "similar",
                           "reason": f"Proche de {close_to} (dans ta watchlist) — {report._why(snap)}."})
    scored.sort(key=lambda s: s.get("technical_score") or 0, reverse=True)
    out = scored[:MAX_SUGGESTIONS]

    # Diversification : un ETF monde si la watchlist n'en contient aucun
    if not any(i.get("product_type") == "ETF" for i in items):
        world = next((w for w in report.WORLD_ALT if w not in owned), None)
        snap = report._snapshot(world) if world else None
        if snap:
            out.append({**snap, "kind": "diversification",
                        "reason": "Diversification : ta watchlist ne contient pas d'ETF ; un ETF monde répartit "
                                  f"le risque sur plus de 1 000 sociétés — {report._why(snap)}."})

    message = None
    if not out:
        message = "Aucun produit similaire n'est en tendance favorable pour l'instant."
    elif not scored and bases:
        message = "Aucun produit similaire n'est en tendance favorable pour l'instant ; voici une piste de diversification."
    return {"items": out, "message": message, "based_on": [b["name"] for b in bases],
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
