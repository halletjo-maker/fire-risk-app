"""Portefeuille fictif : le programme achète et vend seul avec un capital virtuel.

Règles (appliquées après chaque mise à jour des cours de la watchlist choisie) :
- Ventes, vérifiées d'abord :
  · stop-loss touché (le stop monte avec le plus haut atteint depuis l'achat : gains protégés) ;
  · objectif de vente atteint ;
  · signal de la watchlist passé à 🔴 VENTE.
- Achats : produits au signal 🟢 ACHAT dont le cours est dans la zone d'achat affichée
  (≈ : tout de suite ; ≤ : cours au niveau du repli ; ≥ : cours repassé au-dessus du seuil),
  meilleur score d'abord, au plus `max_positions` lignes d'environ 1/`max_positions` du
  portefeuille chacune, en actions entières (cryptos : quantités fractionnées). Pas de rachat d'un
  titre vendu depuis moins de 5 jours.
- Filtre de marché : aucun nouvel achat quand l'ETF MSCI World est sous sa MM100 (marché mondial
  baissier) ; les ventes continuent. Repris dès que l'ETF repasse au-dessus.
- Frais estimés : 0,1 % du montant, 1 € minimum par ordre. Cours en devise convertis en euros.
Aucun ordre réel n'est passé : c'est une simulation.
"""
from __future__ import annotations

import logging
import math
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
STOP_MIN_PCT, STOP_MAX_PCT = 3.0, 12.0
FX_TTL = 3600
QUOTE_TTL = 15 * 60

_lock = threading.Lock()


def fee(amount_eur: float) -> float:
    return round(max(FEE_MIN, amount_eur * FEE_RATE), 2)


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


def _entry_ok(it: dict) -> bool:
    price, buy, kind = it["last_price"], it["buy_price"], it["buy_kind"]
    if not price or not buy or not it["stop_price"] or it["stop_price"] >= price:
        return False
    if kind == "≈":
        return True
    if kind == "≤":
        return price <= buy * 1.005
    if kind == "≥":
        return price >= buy
    return False


def run(portfolio_id: int) -> dict:
    """Applique les règles une fois. Renvoie le nombre d'achats et de ventes."""
    with _lock, get_conn() as conn:
        pf = conn.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if pf is None:
            return {"buys": 0, "sells": 0}
        cash, fees = pf["cash"], pf["fees_paid"]
        items = [dict(r) for r in conn.execute(
            "SELECT symbol, product_id, name, product_type, last_price, last_score, last_signal, buy_price, buy_kind, "
            "sell_price, stop_price, currency FROM watchlist_items WHERE watchlist_id = ?",
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
            stop = max(pos["stop"], high * (1 - pos["stop_pct"] / 100))
            reason = None
            if price <= stop:
                reason = "Stop-loss touché" if stop <= pos["entry_price"] else "Stop suiveur touché (gains protégés)"
            elif pos["target"] and price >= pos["target"]:
                reason = "Objectif de vente atteint"
            elif it and it["last_signal"] == "VENTE":
                reason = "Signal passé à VENTE"
            if reason:
                proceeds = pos["qty"] * price / fx
                f = fee(proceeds)
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
            (i for i in items if i["last_signal"] == "ACHAT" and i["symbol"] not in open_syms
             and i["symbol"] not in cooldown and _entry_ok(i)),
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
            raw_qty = (budget - fee(budget)) * fx / price
            # Cryptos : achat fractionné (un bitcoin coûte bien plus qu'une ligne) ; actions : entières
            qty = math.floor(raw_qty * 1e6) / 1e6 if it.get("product_type") == "CRYPTO" else math.floor(raw_qty)
            if qty <= 0 or qty * price / fx < MIN_ORDER_EUR / 2:
                continue
            cost = qty * price / fx
            f = fee(cost)
            if cost + f > cash:
                continue
            stop_pct = min(STOP_MAX_PCT, max(STOP_MIN_PCT, (1 - it["stop_price"] / price) * 100))
            target = it["sell_price"] if it["sell_price"] and it["sell_price"] > price * 1.02 \
                else price * (1 + max(5.0, stop_pct * 1.5) / 100)
            conn.execute(
                "INSERT INTO portfolio_positions (portfolio_id, symbol, product_id, name, currency, qty, entry_price, "
                "entry_fx, entry_fee, entry_score, target, stop, stop_pct, high, last_price, last_fx) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (portfolio_id, it["symbol"], it["product_id"], it["name"], it["currency"] or "EUR", qty, price, fx, f,
                 it["last_score"], rnd(target), rnd(price * (1 - stop_pct / 100)), round(stop_pct, 2),
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
    if buys or sells:
        logger.info("Portefeuille fictif %s : %s achat(s), %s vente(s)", portfolio_id, buys, sells)
        from . import push
        push.notify_later(pf["user_id"], "trades", f"{pf['name']} : {buys + sells} opération{'s' if buys + sells > 1 else ''}",
                          " · ".join(events), "/")
    return {"buys": buys, "sells": sells}


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
