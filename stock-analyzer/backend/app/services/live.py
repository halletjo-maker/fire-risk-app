"""Cours rapides (toutes les 5 min) et alerte « forte variation du jour ».

L'analyse complète (score, signal, stop) reste toutes les 15 min : ici, seuls le cours et la variation
du jour des watchlists personnelles et des positions réelles sont mis à jour, ce qui est léger.
Alerte : une notification quand un titre suivi ou détenu bouge d'au moins MOVE_PCT % sur la journée,
une fois par jour et par titre au plus, et pas de nouvelle alerte tant que le cours n'a pas bougé
depuis la dernière (Bourse fermée le week-end : la variation du vendredi reste affichée).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..database import get_conn
from . import market

logger = logging.getLogger(__name__)

MOVE_PCT = 5.0
SAME_PRICE = 0.005  # cours identique à ±0,5 % de la dernière alerte : pas de nouvelle alerte
TZ = ZoneInfo("Europe/Brussels")
TRADED_TODAY: set[str] = set()  # produits dont le dernier cours date d'aujourd'hui (Bourse ouverte)


def _today() -> str:
    return datetime.now(TZ).date().isoformat()


def traded_on(q: dict, today: str) -> bool:
    """Le cours date-t-il de la séance du jour ? Sans heure connue : oui en semaine."""
    t = q.get("time")
    if t:
        return str(t)[:10] == today
    return date.fromisoformat(today).weekday() < 5


def _tracked() -> list[str]:
    with get_conn() as conn:
        wl = [r[0] for r in conn.execute(
            "SELECT DISTINCT i.product_id FROM watchlist_items i JOIN watchlists w ON w.id = i.watchlist_id "
            "WHERE w.kind = 'manual' AND i.product_id IS NOT NULL")]
        held = [r[0] for r in conn.execute(
            "SELECT product_id FROM holding_tx GROUP BY user_id, product_id "
            "HAVING SUM(CASE kind WHEN 'BUY' THEN qty ELSE -qty END) > 1e-9")]
    return sorted(set(wl) | set(held))


def fast_prices(product_ids: list[str] | None = None) -> int:
    """Cours et variation du jour, sans recalculer l'analyse. Renvoie le nombre de produits mis à jour.
    Tâche planifiée : quand toutes les Bourses sont fermées (nuit, week-end), seules les cryptos."""
    from . import world
    from .paper import CRYPTO_SYMBOL

    done, today = 0, _today()
    ids = product_ids
    if ids is None:
        ids = _tracked()
        if world.open_zones() == {"crypto"}:
            ids = [p for p in ids if CRYPTO_SYMBOL.search(p)]
    for pid in ids:
        try:
            data = market.get_quote(pid)
        except Exception:
            logger.info("Cours rapide impossible : %s", pid)
            continue
        q = (data or {}).get("quote") or {}
        if not q.get("price"):
            continue
        (TRADED_TODAY.add if traded_on(q, today) else TRADED_TODAY.discard)(pid)
        with get_conn() as conn:
            # Heure de mise à jour avancée (sauf produit pas encore analysé : il reste « en cours »)
            conn.execute("UPDATE watchlist_items SET last_price = ?, last_change_pct = ?, last_refresh_at = "
                         "CASE WHEN last_refresh_at IS NULL THEN NULL ELSE datetime('now') END WHERE product_id = ?",
                         (q["price"], q.get("change_pct"), pid))
            conn.execute("UPDATE holding_quotes SET price = ?, change_pct = ?, refreshed_at = datetime('now') "
                         "WHERE product_id = ?", (q["price"], q.get("change_pct"), pid))
        done += 1
    return done


def _moves() -> dict[int, dict[str, dict]]:
    """Par utilisateur : ses titres suivis ou détenus qui bougent fortement aujourd'hui."""
    out: dict[int, dict[str, dict]] = {}
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT w.user_id, i.product_id, i.name, i.symbol, i.last_price AS price, i.last_change_pct AS change_pct "
            "FROM watchlist_items i JOIN watchlists w ON w.id = i.watchlist_id "
            "WHERE w.kind = 'manual' AND ABS(i.last_change_pct) >= ? "
            "UNION "
            "SELECT t.user_id, t.product_id, MAX(t.name), MAX(t.symbol), q.price, q.change_pct "
            "FROM holding_tx t JOIN holding_quotes q ON q.product_id = t.product_id "
            "WHERE ABS(q.change_pct) >= ? GROUP BY t.user_id, t.product_id "
            "HAVING SUM(CASE t.kind WHEN 'BUY' THEN t.qty ELSE -t.qty END) > 1e-9",
            (MOVE_PCT, MOVE_PCT)).fetchall()
    for r in rows:
        out.setdefault(r["user_id"], {}).setdefault(r["product_id"], dict(r))
    return out


def check_moves(today: str | None = None, traded: set[str] | None = None) -> int:
    """Une notification groupée par utilisateur. Renvoie le nombre de titres signalés.
    Seulement pour les titres cotés aujourd'hui : la nuit et le week-end, la variation affichée est
    celle de la veille et ne doit pas déclencher de nouvelle alerte."""
    from . import push

    today = today or _today()
    traded = TRADED_TODAY if traded is None else traded
    sent = 0
    for uid, moves in _moves().items():
        fresh = []
        with get_conn() as conn:
            for pid, m in moves.items():
                if pid not in traded:
                    continue
                last = conn.execute("SELECT day, price FROM move_alerts WHERE user_id = ? AND product_id = ? "
                                    "ORDER BY day DESC LIMIT 1", (uid, pid)).fetchone()
                if last and (last["day"] == today or (last["price"] and m["price"]
                                                      and abs(m["price"] / last["price"] - 1) < SAME_PRICE)):
                    continue
                conn.execute("INSERT OR REPLACE INTO move_alerts (user_id, product_id, day, price) VALUES (?, ?, ?, ?)",
                             (uid, pid, today, m["price"]))
                fresh.append(m)
        if not fresh:
            continue
        fresh.sort(key=lambda m: -abs(m["change_pct"]))
        parts = [f"{m['name'] or m['symbol']} {m['change_pct']:+.1f} %".replace(".", ",") for m in fresh]
        title = ("📈 " if fresh[0]["change_pct"] > 0 else "📉 ") + (
            f"{fresh[0]['name'] or fresh[0]['symbol']} bouge fortement" if len(fresh) == 1
            else f"{len(fresh)} titres bougent fortement")
        push.notify_later(uid, "alerts", title, " · ".join(parts) + " aujourd'hui", "/")
        sent += len(fresh)
    return sent
