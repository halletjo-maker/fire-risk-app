"""Mes vraies positions : achats et ventes encodés à la main, plus-values et taxe belge estimée.

Règles de la taxe sur les plus-values (loi d'avril 2026, d'après les publications des banques ;
c'est une estimation, pas un calcul officiel) :
- 10 % sur les plus-values réalisées à partir du 1er janvier 2026 ;
- titres achetés avant 2026 : regroupés au prix moyen pondéré ; base = valeur au 31/12/2025, ou le prix
  d'achat moyen s'il est plus élevé, pour les ventes jusqu'au 31/12/2030 ;
- titres achetés à partir de 2026 : FIFO (les plus anciens sont vendus en premier) ;
- frais de courtage et TOB non déductibles ; montants convertis en euros au cours du jour de l'opération ;
- moins-values déduites des plus-values de la même année seulement ;
- franchise de 10 000 € par personne et par an (+ jusqu'à 1 000 € par année non utilisée, 5 ans au plus).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from ..database import get_conn
from .sources import cache, yahoo

logger = logging.getLogger(__name__)

START = "2026-01-01"
REF_DAY = "2025-12-31"
RATE = 0.10
FRANCHISE = 10_000.0
CARRY_PER_YEAR, CARRY_YEARS = 1_000.0, 5
HIST_COST_UNTIL = 2030  # prix d'achat réel utilisable s'il est plus élevé, pour les ventes jusqu'à cette année
STOP_NEAR = 1.03        # alerte « approche du stop » à 3 % au-dessus du stop


# ── Cours historiques ────────────────────────────────────────────────────────
def _pence(currency: str | None) -> bool:
    return (currency or "") in ("GBp", "GBX")


def close_on(symbol: str, day: str) -> float | None:
    """Dernière clôture connue à cette date (ou juste avant : week-end, jour férié)."""
    key = f"close:{symbol}:{day}"
    hit = cache.get(key, 365 * 24 * 3600)
    if hit is not None:
        return hit or None
    d = date.fromisoformat(day)
    try:
        hist = yahoo.yf.Ticker(symbol).history(start=(d - timedelta(days=10)).isoformat(),
                                               end=(d + timedelta(days=1)).isoformat(), interval="1d",
                                               auto_adjust=False, raise_errors=False)
        closes = hist["Close"].dropna() if hist is not None and "Close" in hist else None
        value = float(closes.iloc[-1]) if closes is not None and len(closes) else None
    except Exception as exc:
        logger.info("Cours historique impossible (%s, %s) : %s", symbol, day, exc)
        return None
    if value is not None:
        cache.put(key, value, source="Yahoo Finance")
    return value


def fx_on(currency: str | None, day: str) -> float | None:
    """Unités de la devise pour 1 € à cette date (1 pour l'euro ; pence = livre × 100)."""
    ccy = (currency or "EUR").strip()
    if ccy.upper() == "EUR":
        return 1.0
    base = "GBP" if _pence(ccy) else ccy.upper()
    rate = close_on(f"EUR{base}=X", day)
    if rate is None:
        return None
    return rate * 100 if _pence(ccy) else rate


# ── Calcul ──────────────────────────────────────────────────────────────────
def _transactions(conn, user_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM holding_tx WHERE user_id = ? ORDER BY day, id", (user_id,))]


def _refs(conn, user_id: int) -> dict:
    return {r["product_id"]: dict(r) for r in conn.execute(
        "SELECT * FROM holding_refs WHERE user_id = ?", (user_id,))}


def compute(transactions: list[dict], refs: dict, quotes: dict) -> dict:
    """Positions ouvertes, ventes réalisées (avec la plus-value fiscale) et bilan par année."""
    products: dict[str, dict] = {}
    realized = []
    problems = []
    for t in transactions:
        p = products.setdefault(t["product_id"], {
            "product_id": t["product_id"], "symbol": t["symbol"], "name": t["name"], "currency": t["currency"],
            "pre_qty": 0.0, "pre_cost": 0.0, "pre_ccy": 0.0, "lots": [], "fees": 0.0, "realized_eur": 0.0})
        eur = t["qty"] * t["price"] / (t["fx"] or 1)
        p["fees"] += t["fees_eur"] or 0
        if t["kind"] == "BUY":
            if t["day"] < START:
                p["pre_qty"] += t["qty"]
                p["pre_cost"] += eur
                p["pre_ccy"] += t["qty"] * t["price"]
            else:
                p["lots"].append({"qty": t["qty"], "unit": eur / t["qty"], "ccy": t["price"], "day": t["day"]})
            continue
        # Vente : d'abord le groupe « avant 2026 », puis les lots FIFO
        left, unit_price = t["qty"], eur / t["qty"]
        year = int(t["day"][:4])
        ref = refs.get(t["product_id"])
        while left > 1e-9:
            if p["pre_qty"] > 1e-9:
                take = min(left, p["pre_qty"])
                hist_unit = p["pre_cost"] / p["pre_qty"]
                if t["day"] < START:
                    tax_unit = None  # vente avant 2026 : pas concernée par la taxe
                elif ref and ref.get("ref_price") and ref.get("ref_fx"):
                    ref_unit = ref["ref_price"] / ref["ref_fx"]
                    tax_unit = max(ref_unit, hist_unit) if year <= HIST_COST_UNTIL else ref_unit
                else:
                    tax_unit = hist_unit
                    problems.append(f"{p['name']} : valeur au 31/12/2025 manquante, prix d'achat utilisé à la place.")
                cost_unit = hist_unit
                p["pre_ccy"] -= p["pre_ccy"] / p["pre_qty"] * take
                p["pre_cost"] -= hist_unit * take
                p["pre_qty"] -= take
            elif p["lots"]:
                lot = p["lots"][0]
                take = min(left, lot["qty"])
                tax_unit = cost_unit = lot["unit"]
                lot["qty"] -= take
                if lot["qty"] <= 1e-9:
                    p["lots"].pop(0)
            else:
                problems.append(f"{p['name']} : vente du {t['day']} plus grande que la quantité achetée.")
                break
            p["realized_eur"] += (unit_price - cost_unit) * take
            if tax_unit is not None:
                realized.append({"tx_id": t["id"], "day": t["day"], "year": year, "product_id": t["product_id"],
                                 "name": p["name"], "qty": take, "proceeds": unit_price * take,
                                 "basis": tax_unit * take, "gain": (unit_price - tax_unit) * take})
            left -= take

    positions = []
    for p in products.values():
        qty = p["pre_qty"] + sum(l["qty"] for l in p["lots"])
        if qty <= 1e-9:
            continue
        cost = p["pre_cost"] + sum(l["qty"] * l["unit"] for l in p["lots"])
        cost_ccy = p["pre_ccy"] + sum(l["qty"] * l["ccy"] for l in p["lots"])
        ref = refs.get(p["product_id"]) or {}
        ref_unit = ref["ref_price"] / ref["ref_fx"] if ref.get("ref_price") and ref.get("ref_fx") else None
        pre_tax_unit = None
        if p["pre_qty"] > 1e-9:
            hist_unit = p["pre_cost"] / p["pre_qty"]
            pre_tax_unit = max(ref_unit, hist_unit) if ref_unit else hist_unit
        tax_basis = (pre_tax_unit or 0) * p["pre_qty"] + sum(l["qty"] * l["unit"] for l in p["lots"])
        q = quotes.get(p["product_id"]) or {}
        value = qty * q["price"] / q["fx"] if q.get("price") and q.get("fx") else None
        positions.append({
            "product_id": p["product_id"], "symbol": p["symbol"], "name": p["name"], "currency": p["currency"],
            "qty": round(qty, 8), "cost_eur": round(cost, 2), "avg_price": round(cost_ccy / qty, 4),
            "fees_eur": round(p["fees"], 2), "value_eur": round(value, 2) if value is not None else None,
            "pnl_eur": round(value - cost - p["fees"], 2) if value is not None else None,
            "pnl_pct": round((value - cost - p["fees"]) / cost * 100, 2) if value is not None and cost else None,
            "tax_gain_eur": round(value - tax_basis, 2) if value is not None else None,
            "pre2026_qty": round(p["pre_qty"], 8) if p["pre_qty"] > 1e-9 else 0,
            "ref_price": ref.get("ref_price"), "ref_missing": p["pre_qty"] > 1e-9 and not ref_unit,
            "price": q.get("price"), "change_pct": q.get("change_pct"), "stop_price": q.get("stop_price"),
            "sell_price": q.get("sell_price"), "signal": q.get("signal"), "refreshed_at": q.get("refreshed_at"),
            "realized_eur": round(p["realized_eur"], 2),
        })
    positions.sort(key=lambda x: -(x["value_eur"] or x["cost_eur"]))
    return {"positions": positions, "realized": realized, "years": tax_years(realized),
            "problems": sorted(set(problems))}


def tax_years(realized: list[dict], today: date | None = None) -> list[dict]:
    """Bilan par année : plus-values, moins-values, franchise (avec report) et taxe estimée.
    Report : chaque année où la franchise de base n'est pas entièrement utilisée crée un crédit
    (1 000 € au plus), utilisable pendant 5 ans et consommé quand il sert."""
    today = today or date.today()
    last = max([today.year] + [r["year"] for r in realized])
    out, credits = [], []  # credits : [année, montant restant]
    for year in range(2026, last + 1):
        rows = [r for r in realized if r["year"] == year]
        gains = sum(r["gain"] for r in rows if r["gain"] > 0)
        losses = sum(r["gain"] for r in rows if r["gain"] < 0)
        net = gains + losses
        valid = [c for c in credits if year - CARRY_YEARS <= c[0] < year and c[1] > 0]
        carry = min(CARRY_PER_YEAR * CARRY_YEARS, sum(c[1] for c in valid))
        franchise = FRANCHISE + carry
        taxable = max(0.0, net - franchise)
        need = min(carry, max(0.0, net - FRANCHISE))  # crédits consommés, les plus anciens d'abord
        for c in valid:
            used = min(need, c[1])
            c[1] -= used
            need -= used
        credits.append([year, min(CARRY_PER_YEAR, max(0.0, FRANCHISE - max(0.0, net)))])
        out.append({"year": year, "gains": round(gains, 2), "losses": round(losses, 2), "net": round(net, 2),
                    "franchise": round(franchise, 2), "carry": round(carry, 2),
                    "franchise_left": round(max(0.0, franchise - max(0.0, net)), 2),
                    "taxable": round(taxable, 2), "tax": round(taxable * RATE, 2), "sales": len(rows)})
    return out


def quotes_for(conn, product_ids: list[str]) -> dict:
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    return {r["product_id"]: dict(r) for r in conn.execute(
        f"SELECT * FROM holding_quotes WHERE product_id IN ({marks})", product_ids)}


def summary(user_id: int) -> dict:
    with get_conn() as conn:
        txs = _transactions(conn, user_id)
        refs = _refs(conn, user_id)
        quotes = quotes_for(conn, sorted({t["product_id"] for t in txs}))
    data = compute(txs, refs, quotes)
    pos = data["positions"]
    valued = [p for p in pos if p["value_eur"] is not None]
    data["totals"] = {
        "value_eur": round(sum(p["value_eur"] for p in valued), 2),
        "cost_eur": round(sum(p["cost_eur"] for p in pos), 2),
        "pnl_eur": round(sum(p["pnl_eur"] for p in valued), 2),
        "fees_eur": round(sum(p["fees_eur"] for p in pos), 2),
        "tax_gain_eur": round(sum(p["tax_gain_eur"] for p in valued), 2),
        "missing_quotes": len(pos) - len(valued),
    }
    data["transactions"] = list(reversed(txs))
    data["rules"] = {"rate": RATE, "franchise": FRANCHISE}
    return data


# ── Encodage ─────────────────────────────────────────────────────────────────
def add_transaction(user_id: int, tx: dict) -> dict:
    fx = tx.get("fx") or fx_on(tx["currency"], tx["day"])
    if not fx:
        raise ValueError(f"Taux de change {tx['currency']}/EUR introuvable pour le {tx['day']} : indique-le à la main.")
    with get_conn() as conn:
        if tx["kind"] == "SELL":
            held = sum(r["qty"] if r["kind"] == "BUY" else -r["qty"] for r in conn.execute(
                "SELECT kind, qty FROM holding_tx WHERE user_id = ? AND product_id = ? AND day <= ?",
                (user_id, tx["product_id"], tx["day"])))
            if tx["qty"] > held + 1e-9:
                raise ValueError(f"Tu ne détenais que {held:g} titre(s) à cette date.")
        tid = conn.execute(
            "INSERT INTO holding_tx (user_id, product_id, symbol, name, currency, kind, day, qty, price, fx, fees_eur) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, tx["product_id"], tx.get("symbol"), tx["name"], tx["currency"], tx["kind"], tx["day"],
             tx["qty"], tx["price"], fx, tx.get("fees_eur") or 0)).lastrowid
    if tx["kind"] == "BUY" and tx["day"] < START:
        ensure_ref(user_id, tx["product_id"], tx.get("symbol"), tx["currency"])
    return {"id": tid, "fx": fx}


def ensure_ref(user_id: int, product_id: str, symbol: str | None, currency: str | None) -> None:
    """Valeur au 31/12/2025 (cours de clôture) pour les titres achetés avant 2026, si Yahoo la connaît."""
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM holding_refs WHERE user_id = ? AND product_id = ? AND ref_price IS NOT NULL",
                        (user_id, product_id)).fetchone():
            return
    price = close_on(symbol, REF_DAY) if symbol and product_id.startswith("yf:") else None
    fx = fx_on(currency, REF_DAY)
    if price and fx:
        set_ref(user_id, product_id, price, fx, "Yahoo Finance (clôture du 31/12/2025)")


def set_ref(user_id: int, product_id: str, price: float, fx: float, source: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO holding_refs (user_id, product_id, ref_price, ref_fx, source) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT(user_id, product_id) DO UPDATE SET ref_price = excluded.ref_price, "
                     "ref_fx = excluded.ref_fx, source = excluded.source", (user_id, product_id, price, fx, source))


# ── Cours et alertes (planificateur) ────────────────────────────────────────
def refresh_quotes() -> int:
    """Cours, stop-loss et objectif des titres détenus (analyse complète, comme les watchlists)."""
    from . import analysis, paper, targets

    with get_conn() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT product_id FROM holding_tx GROUP BY user_id, product_id "
            "HAVING SUM(CASE kind WHEN 'BUY' THEN qty ELSE -qty END) > 1e-9")]
    done = 0
    for pid in sorted(set(ids)):
        try:
            full = analysis.run(pid)
        except Exception:
            logger.exception("Position : analyse impossible (%s)", pid)
            continue
        if not full:
            continue
        q, d = full["quote"], full["decision"]
        lv = targets.compute(full) or {}
        fx = paper.fx_rate((full.get("product") or {}).get("currency"))
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO holding_quotes (product_id, price, change_pct, fx, stop_price, sell_price, signal, score, "
                "refreshed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) ON CONFLICT(product_id) DO UPDATE SET "
                "price = excluded.price, change_pct = excluded.change_pct, fx = excluded.fx, "
                "stop_price = excluded.stop_price, sell_price = excluded.sell_price, signal = excluded.signal, "
                "score = excluded.score, refreshed_at = excluded.refreshed_at",
                (pid, q.get("price"), q.get("change_pct"), fx, lv.get("stop_price"), lv.get("sell_price"),
                 d.get("signal") if d.get("available") else None, d.get("score") if d.get("available") else None))
        done += 1
    return done


def check_alerts(today: str | None = None) -> int:
    """Une alerte par jour au plus et par titre : approche du stop, stop touché, objectif atteint."""
    from . import push
    from .mail import sender

    today = today or date.today().isoformat()
    with get_conn() as conn:
        users = [dict(r) for r in conn.execute(
            "SELECT DISTINCT u.id, u.email FROM users u JOIN holding_tx t ON t.user_id = u.id")]
    sent = 0
    for u in users:
        for p in summary(u["id"])["positions"]:
            price, stop, target = p["price"], p["stop_price"], p["sell_price"]
            if not price:
                continue
            kind = ("stop" if stop and price <= stop else "near" if stop and price <= stop * STOP_NEAR
                    else "target" if target and price >= target else None)
            if not kind:
                continue
            with get_conn() as conn:
                fresh = conn.execute("INSERT OR IGNORE INTO holding_alerts (user_id, product_id, kind, day) "
                                     "VALUES (?, ?, ?, ?)", (u["id"], p["product_id"], kind, today)).rowcount
            if not fresh:
                continue
            cur = p["currency"] or ""
            title = {"stop": f"🔴 {p['name']} : stop-loss touché",
                     "near": f"🟠 {p['name']} approche de son stop-loss",
                     "target": f"🎯 {p['name']} : objectif de vente atteint"}[kind]
            body = (f"Cours {price:g} {cur} · stop {stop:g} {cur}" if kind in ("stop", "near") and stop
                    else f"Cours {price:g} {cur} · objectif {target:g} {cur}")
            text = (f"{title}\n\n{body}\nTa position : {p['qty']:g} titre(s), "
                    f"{'plus' if (p['pnl_eur'] or 0) >= 0 else 'moins'}-value latente {p['pnl_eur'] or 0:+.2f} €.\n\n"
                    "Rien n'est vendu automatiquement : c'est à toi de décider chez ton courtier.\n"
                    "Aide à la décision automatisée, pas un conseil en investissement.\n")
            sender.send(u["email"], title, text)
            push.notify_later(u["id"], "alerts", title, body, "/")
            sent += 1
    return sent

