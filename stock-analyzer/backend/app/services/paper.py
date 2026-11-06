"""Portefeuille fictif : le programme achète et vend seul avec un capital virtuel.

Règles revues en novembre 2026 avec le test sur 10 ans (services/backtest.py, variante « rules ») :
achat dès le signal 🟢 ACHAT au-dessus de la MM200 (sans attendre de repli), pas d'objectif de vente
(on laisse courir les gains), stop suiveur à 15 % sous le plus haut, vente quand la tendance de fond
se retourne (cours sous une MM200 qui baisse).


Règles (appliquées après chaque mise à jour des cours de la watchlist choisie) :
- Ventes, vérifiées d'abord :
  · stop suiveur touché : 15 % sous le plus haut atteint depuis l'achat (gains protégés) ;
  · tendance de fond baissière : cours sous une MM200 qui baisse (garde-fou de la watchlist).
  Pas d'objectif de vente : on laisse courir les gains.
- Achats : produits au signal 🟢 ACHAT dont le cours est au-dessus de la MM200, tout de suite
  (sans attendre de repli), meilleur score d'abord, au plus `max_positions` lignes d'environ 1/`max_positions` du
  portefeuille chacune, en actions entières (cryptos : quantités fractionnées). Pas de rachat d'un
  titre vendu depuis moins de 5 jours.
- Filtre de marché : aucun nouvel achat quand l'ETF MSCI World est sous sa MM100 (marché mondial
  baissier) ; les ventes continuent. Repris dès que l'ETF repasse au-dessus.
- Frais réels Saxo (niveau Bronze) : courtage 0,08 % (min. 2 € Euronext, 1 $ USA…), change 0,25 % pour
  une devise, plus la TOB (0,35 % actions, 0,12 % ETF). Cours en devise convertis en euros.
Aucun ordre réel n'est passé : c'est une simulation.
"""
from __future__ import annotations

import logging
import math
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from ..database import get_conn
from . import regime
from .sources import cache, yahoo
from .targets import rnd

logger = logging.getLogger(__name__)

FEE_RATE = 0.001
FEE_MIN = 1.0
COOLDOWN_DAYS = 5
MIN_ORDER_EUR = 100.0
STOP_MIN_PCT, STOP_MAX_PCT = 3.0, 12.0  # stop conseillé des watchlists (affichage)
TRAIL_PCT = 15.0  # stop suiveur des portefeuilles fictifs : 15 % sous le plus haut atteint depuis l'achat
FX_TTL = 3600
QUOTE_TTL = 15 * 60

_lock = threading.Lock()


def fee(amount_eur: float, currency: str | None = "EUR", product_type: str | None = "ACTION",
        symbol: str | None = None) -> float:
    """Frais réels Saxo Bronze + TOB (services/costs.py)."""
    from .costs import order_cost
    return order_cost(amount_eur, currency, product_type, symbol)


def fx_rate(currency: str | None) -> float | None:
    """Unités de `currency` pour 1 € (ex. USD ≈ 1,08). GBp (pence) = GBP × 100."""
    ccy = (currency or "EUR").strip()
    if ccy.upper() == "EUR":
        return 1.0
    pence = ccy in ("GBp", "GBX")
    base = "GBP" if pence else ccy.upper()
    key = f"fx:{base}"
    rate = cache.get(key, FX_TTL)
    if rate is None:
        q = yahoo.quote(f"EUR{base}=X")
        rate = q.get("price") if q else None
        if rate:
            cache.put(key, rate, source="Yahoo Finance")
    if not rate:
        return None
    return rate * 100 if pence else rate


def _quote_price(symbol: str) -> float | None:
    """Cours d'un titre détenu qui n'est plus dans la watchlist."""
    key = f"pq:{symbol}"
    price = cache.get(key, QUOTE_TTL)
    if price is None:
        q = yahoo.quote(symbol)
        price = q.get("price") if q else None
        if price:
            cache.put(key, price, source="Yahoo Finance")
    return price


def _today() -> str:
    return datetime.now(ZoneInfo("Europe/Brussels")).strftime("%Y-%m-%d")


def run(portfolio_id: int) -> dict:
    """Applique les règles une fois. Renvoie le nombre d'achats et de ventes."""
    with _lock, get_conn() as conn:
        pf = conn.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if pf is None:
            return {"buys": 0, "sells": 0}
        cash, fees = pf["cash"], pf["fees_paid"]
        items = [dict(r) for r in conn.execute(
            "SELECT symbol, product_id, name, product_type, last_price, last_score, last_signal, buy_price, buy_kind, "
            "sell_price, stop_price, currency, above_m200, guard FROM watchlist_items WHERE watchlist_id = ?",
            (pf["watchlist_id"],))] if pf["watchlist_id"] else []
        by_sym = {i["symbol"]: i for i in items}
        positions = [dict(r) for r in conn.execute(
            "SELECT * FROM portfolio_positions WHERE portfolio_id = ? AND status = 'OPEN'", (portfolio_id,))]
        sells = buys = 0
        events: list[str] = []
        # Données réseau récupérées avant toute écriture (la base n'est pas verrouillée pendant ce temps)
        currencies = {p["currency"] for p in positions} | {i["currency"] for i in items if i["last_signal"] == "ACHAT"}
        rates = {c: fx_rate(c) for c in currencies}
        market = regime.regime()  # filtre de marché (MSCI World vs sa MM100)
        quotes = {p["symbol"]: _quote_price(p["symbol"]) for p in positions
                  if not (by_sym.get(p["symbol"]) or {}).get("last_price")}

        # ── 1. Ventes ──────────────────────────────────────────────────────
        held_value = 0.0
        for pos in positions:
            it = by_sym.get(pos["symbol"])
            price = (it or {}).get("last_price") or quotes.get(pos["symbol"])
            fx = rates.get(pos["currency"]) or pos["last_fx"] or pos["entry_fx"]
            if not price:
                held_value += pos["qty"] * (pos["last_price"] or pos["entry_price"]) / (pos["last_fx"] or pos["entry_fx"])
                continue
            high = max(pos["high"] or pos["entry_price"], price)
            stop = high * (1 - TRAIL_PCT / 100)  # stop suiveur, aussi pour les lignes achetées avant ces règles
            reason = None
            if price <= stop:
                reason = "Stop-loss touché" if stop <= pos["entry_price"] else "Stop suiveur touché (gains protégés)"
            elif it and it.get("guard") == 1:
                reason = "Tendance de fond baissière (sous une MM200 qui baisse)"
            if reason:
                proceeds = pos["qty"] * price / fx
                ptype = "CRYPTO" if CRYPTO_SYMBOL.search(pos["symbol"] or "") else "ACTION"
                f = fee(proceeds, pos["currency"], ptype, pos["symbol"])
                cost = pos["qty"] * pos["entry_price"] / pos["entry_fx"] + pos["entry_fee"]
                cash += proceeds - f
                fees += f
                conn.execute(
                    "UPDATE portfolio_positions SET status = 'CLOSED', exit_price = ?, exit_fx = ?, exit_fee = ?, "
                    "exit_at = datetime('now'), exit_reason = ?, pnl_eur = ?, high = ?, stop = ?, last_price = ?, "
                    "last_fx = ? WHERE id = ?",
                    (price, fx, f, reason, round(proceeds - f - cost, 2), high, stop, price, fx, pos["id"]))
                pos["status"] = "CLOSED"
                sells += 1
                gain = (proceeds - f) / cost * 100 - 100 if cost else 0
                events.append(f"Vente {pos['name'] or pos['symbol']} ({f'{gain:+.1f}'.replace('.', ',')} %) : {reason.lower()}")
            else:
                conn.execute("UPDATE portfolio_positions SET high = ?, stop = ?, last_price = ?, last_fx = ? WHERE id = ?",
                             (high, stop, price, fx, pos["id"]))
                held_value += pos["qty"] * price / fx
        open_syms = {p["symbol"] for p in positions if p["status"] == "OPEN"}

        # ── 2. Achats ──────────────────────────────────────────────────────
        cooldown = {r["symbol"] for r in conn.execute(
            "SELECT symbol FROM portfolio_positions WHERE portfolio_id = ? AND status = 'CLOSED' "
            f"AND exit_at > datetime('now', '-{COOLDOWN_DAYS} days')", (portfolio_id,))}
        slot = (cash + held_value) / pf["max_positions"]
        candidates = sorted(
            (i for i in items if i["last_signal"] == "ACHAT" and i.get("above_m200") == 1 and i["last_price"]
             and i["symbol"] not in open_syms and i["symbol"] not in cooldown),
            key=lambda i: i["last_score"] or 0, reverse=True)
        note = None
        if not market["ok"]:  # marché mondial en tendance baissière : pas de nouvelle ligne
            dist = f"{market['distance_pct']:+.1f}".replace(".", ",")
            note = (f"Achats suspendus : le {market['label']} est sous sa MM100 ({dist} %). "
                    "Les ventes continuent normalement.")
            candidates = []
        for it in candidates:
            if len(open_syms) >= pf["max_positions"]:
                break
            budget = min(slot, cash)
            if budget < MIN_ORDER_EUR:
                break
            fx = rates.get(it["currency"])
            if not fx:
                continue
            price = it["last_price"]
            ptype = it.get("product_type") or "ACTION"
            raw_qty = (budget - fee(budget, it["currency"], ptype, it["symbol"])) * fx / price
            # Cryptos : achat fractionné (un bitcoin coûte bien plus qu'une ligne) ; actions : entières
            qty = math.floor(raw_qty * 1e6) / 1e6 if it.get("product_type") == "CRYPTO" else math.floor(raw_qty)
            if qty <= 0 or qty * price / fx < MIN_ORDER_EUR / 2:
                continue
            cost = qty * price / fx
            f = fee(cost, it["currency"], ptype, it["symbol"])
            if cost + f > cash:
                continue
            stop_pct, target = TRAIL_PCT, None  # pas d'objectif : on laisse courir les gains
            conn.execute(
                "INSERT INTO portfolio_positions (portfolio_id, symbol, product_id, name, currency, qty, entry_price, "
                "entry_fx, entry_fee, entry_score, target, stop, stop_pct, high, last_price, last_fx) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (portfolio_id, it["symbol"], it["product_id"], it["name"], it["currency"] or "EUR", qty, price, fx, f,
                 it["last_score"], target, rnd(price * (1 - stop_pct / 100)), round(stop_pct, 2),
                 price, price, fx))
            cash -= cost + f
            fees += f
            held_value += cost
            open_syms.add(it["symbol"])
            buys += 1
            events.append(f"Achat {it['name'] or it['symbol']} ({round(cost)} €)")

        # ── 3. Valeur du jour ──────────────────────────────────────────────
        conn.execute("UPDATE portfolios SET cash = ?, fees_paid = ?, last_note = ?, last_run_at = datetime('now') "
                     "WHERE id = ?", (round(cash, 2), round(fees, 2), note, portfolio_id))
        conn.execute(
            "INSERT INTO portfolio_values (portfolio_id, day, value_eur) VALUES (?, ?, ?) "
            "ON CONFLICT(portfolio_id, day) DO UPDATE SET value_eur = excluded.value_eur",
            (portfolio_id, _today(), round(cash + held_value, 2)))
    try:
        refresh_share_trends(portfolio_id)
    except Exception:
        logger.exception("Rachats d'actions : mise à jour impossible (portefeuille %s)", portfolio_id)
    if buys or sells:
        logger.info("Portefeuille fictif %s : %s achat(s), %s vente(s)", portfolio_id, buys, sells)
        from . import push
        push.notify_later(pf["user_id"], "trades", f"{pf['name']} : {buys + sells} opération{'s' if buys + sells > 1 else ''}",
                          " · ".join(events), "/")
    return {"buys": buys, "sells": sells}


CRYPTO_SYMBOL = re.compile(r"-(EUR|USD|USDT|GBP|CHF)$")


def refresh_share_trends(portfolio_id: int) -> int:
    """Rachats d'actions des lignes ouvertes (comptes annuels Yahoo, revus au plus une fois par mois)."""
    from . import fundamentals
    from .sources import yahoo

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, symbol FROM portfolio_positions WHERE portfolio_id = ? AND status = 'OPEN' AND "
            "(shares_checked_at IS NULL OR shares_checked_at < datetime('now', '-30 days'))", (portfolio_id,)).fetchall()
    done = 0
    for r in rows:
        trend = None
        if not CRYPTO_SYMBOL.search(r["symbol"] or ""):
            try:
                st = fundamentals.share_trend(yahoo.financials(r["symbol"]))
                trend = st["pct_per_year"] if st else None
            except Exception:
                logger.exception("Rachats d'actions illisibles : %s", r["symbol"])
        with get_conn() as conn:
            conn.execute("UPDATE portfolio_positions SET shares_trend = ?, shares_checked_at = datetime('now') "
                         "WHERE id = ?", (trend, r["id"]))
        done += 1
    return done


def run_all() -> int:
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM portfolios")]
    for pid in ids:
        try:
            run(pid)
        except Exception:
            logger.exception("Portefeuille fictif %s : simulation impossible", pid)
    return len(ids)


def summary(conn, pf) -> dict:
    """Valeur, performance et lignes ouvertes (valorisées au dernier cours connu)."""
    open_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM portfolio_positions WHERE portfolio_id = ? AND status = 'OPEN' ORDER BY entry_at", (pf["id"],))]
    invested = 0.0
    for p in open_rows:
        fx = p["last_fx"] or p["entry_fx"]
        p["value_eur"] = round(p["qty"] * (p["last_price"] or p["entry_price"]) / fx, 2)
        p["cost_eur"] = round(p["qty"] * p["entry_price"] / p["entry_fx"] + p["entry_fee"], 2)
        p["pnl_eur"] = round(p["value_eur"] - p["cost_eur"], 2)
        p["pnl_pct"] = round(p["pnl_eur"] / p["cost_eur"] * 100, 2) if p["cost_eur"] else None
        trend = p.get("shares_trend")
        p["buyback"] = trend is not None and trend <= -1.0  # même seuil que fundamentals.BUYBACK_PCT
        invested += p["value_eur"]
    value = round(pf["cash"] + invested, 2)
    wl = conn.execute("SELECT id, name, kind FROM watchlists WHERE id = ?", (pf["watchlist_id"],)).fetchone() \
        if pf["watchlist_id"] else None
    return {
        "id": pf["id"], "name": pf["name"], "created_at": pf["created_at"], "last_run_at": pf["last_run_at"],
        "note": pf["last_note"] if "last_note" in pf.keys() else None,
        "watchlist": dict(wl) if wl else None,
        "initial_cash": pf["initial_cash"], "cash": round(pf["cash"], 2), "invested": round(invested, 2),
        "value": value, "pnl_eur": round(value - pf["initial_cash"], 2),
        "pnl_pct": round((value / pf["initial_cash"] - 1) * 100, 2), "fees_paid": pf["fees_paid"],
        "max_positions": pf["max_positions"], "open_count": len(open_rows), "positions": open_rows,
    }
