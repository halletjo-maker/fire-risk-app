"""Test de la méthode sur le passé (backtest).

Rejoue les règles des portefeuilles fictifs sur l'historique d'une liste de titres :
- chaque semaine : score technique (identique à l'outil), garde-fou MM200, zone d'achat,
  stop-loss et objectif (mêmes calculs que les watchlists) ;
- chaque jour : stop suiveur et objectif vérifiés à la clôture ;
- 10 lignes au plus d'environ 10 %, frais de 0,1 % (1 € minimum), 5 jours avant de racheter un titre vendu ;
- filtre de marché : pas d'achat quand l'ETF MSCI World est sous sa MM100.

Limites, affichées avec le résultat : seule l'analyse technique peut être rejouée (fondamentaux et
actualités du passé indisponibles) ; la liste est celle d'aujourd'hui (biais du survivant : les sociétés
disparues manquent, ce qui embellit les résultats) ; rendements en devise locale, sans effet de change ;
achats et ventes au cours de clôture, sans glissement.
"""
from __future__ import annotations

import json
import logging
import math
import threading
from datetime import datetime

import pandas as pd

from ..database import get_conn
from . import targets, technical
from .decision import CAUTION, FAVORABLE
from .regime import SYMBOL as BENCH_SYMBOL
from .sources import yahoo

logger = logging.getLogger(__name__)

MAX_SYMBOLS = 150
EVAL_EVERY = 5          # une évaluation par semaine de Bourse
WARMUP = 210            # séances nécessaires pour la MM200
CAPITAL = 10_000.0
MAX_POSITIONS = 10
FEE_RATE, FEE_MIN = 0.001, 1.0
COOLDOWN_DAYS = 5
STOP_MIN_PCT, STOP_MAX_PCT = 3.0, 12.0

VARIANTS = [
    {"key": "rules", "label": "Règles actuelles", "guard": True, "market": True},
    {"key": "no_guard", "label": "Sans garde-fou MM200", "guard": False, "market": True},
    {"key": "no_market", "label": "Sans filtre de marché", "guard": True, "market": False},
    {"key": "threshold", "label": "Achat dès 6,5/10 (au lieu de 7,5)", "guard": True, "market": True, "buy_min": 6.5},
]

_lock = threading.Lock()


def fee(amount: float) -> float:
    return max(FEE_MIN, amount * FEE_RATE)


# ── Étape 1 : signaux hebdomadaires de chaque titre ─────────────────────────
def weekly_signals(df: pd.DataFrame) -> dict:
    """{date: {...}} une fois par semaine : score, garde-fou, zone d'achat, stop, objectif."""
    d = technical.indicators(df)
    out = {}
    for i in range(WARMUP, len(d), EVAL_EVERY):
        sub = d.iloc[:i + 1]
        price = float(sub["close"].iloc[-1])
        if not price or math.isnan(price):
            continue
        mm = technical.mm100_status(sub)
        scored = [c for c in technical.score_criteria(sub, mm) if c["score"] is not None]
        total = sum(c["weight"] for c in scored)
        if not total:
            continue
        score = sum(c["score"] * c["weight"] for c in scored) / total
        lt = technical.long_trend(sub) or {}
        tech = {"applicable": True, "mm100": mm, "levels": technical.supports_resistances(sub, price),
                "chart": sub[["high", "low", "close"]].iloc[-20:].to_dict("records")}  # suffit pour l'ATR 14
        lv = targets.compute({"product": {"type": "ACTION"}, "quote": {"price": price}, "technical": tech}) or {}
        out[sub.index[-1].strftime("%Y-%m-%d")] = {
            "score": score, "guard": bool(lt.get("guard")), "price": price,
            "buy_price": lv.get("buy_price"), "buy_kind": lv.get("buy_kind"),
            "stop_price": lv.get("stop_price"), "sell_price": lv.get("sell_price")}
    return out


def entry_ok(s: dict) -> bool:
    """Même règle que les portefeuilles fictifs (paper._entry_ok)."""
    price, buy, kind, stop = s["price"], s["buy_price"], s["buy_kind"], s["stop_price"]
    if not price or not buy or not stop or stop >= price:
        return False
    return kind == "≈" or (kind == "≤" and price <= buy * 1.005) or (kind == "≥" and price >= buy)


# ── Étape 2 : simulation ────────────────────────────────────────────────────
def simulate(closes: dict[str, pd.Series], signals: dict[str, dict], bench: pd.Series, variant: dict) -> dict:
    dates = [ts.strftime("%Y-%m-%d") for ts in bench.index]
    bench_m100 = bench.rolling(100).mean()
    eval_days = {k for sym in signals.values() for k in sym}
    px = {sym: {ts.strftime("%Y-%m-%d"): float(v) for ts, v in s.dropna().items()} for sym, s in closes.items()}
    last_px: dict[str, float] = {}
    cash, positions, trades, curve, exposure = CAPITAL, {}, [], [], []
    cooldown: dict[str, int] = {}
    start = next((i for i, d in enumerate(dates) if d in eval_days), None)
    if start is None:
        return {}
    for i in range(start, len(dates)):
        day = dates[i]
        for sym in px:
            if day in px[sym]:
                last_px[sym] = px[sym][day]
        # Ventes : stop suiveur, objectif (chaque jour), signal VENTE (jour d'évaluation)
        for sym in list(positions):
            p, price = positions[sym], last_px.get(sym)
            if price is None:
                continue
            p["high"] = max(p["high"], price)
            p["stop"] = max(p["stop"], p["high"] * (1 - p["stop_pct"] / 100))
            sig = signals[sym].get(day)
            reason = ("stop" if price <= p["stop"] else "target" if price >= p["target"]
                      else "signal" if sig and sig["score"] < CAUTION else None)
            if reason:
                proceeds = p["qty"] * price
                f = fee(proceeds)
                cash += proceeds - f
                trades.append({"symbol": sym, "entry": p["day"], "exit": day, "reason": reason,
                               "pnl_pct": (proceeds - f) / p["cost"] * 100 - 100})
                cooldown[sym] = i
                del positions[sym]
        # Achats (jour d'évaluation)
        market_ok = not variant["market"] or (not math.isnan(bench_m100.iloc[i]) and bench.iloc[i] > bench_m100.iloc[i])
        if market_ok and len(positions) < MAX_POSITIONS:
            cands = []
            for sym, sigs in signals.items():
                s = sigs.get(day)
                if (not s or sym in positions or i - cooldown.get(sym, -99) < COOLDOWN_DAYS
                        or s["score"] < variant.get("buy_min", FAVORABLE) or (variant["guard"] and s["guard"])
                        or not entry_ok(s)):
                    continue
                cands.append((s["score"], sym, s))
            equity = cash + sum(p["qty"] * last_px.get(s, p["entry"]) for s, p in positions.items())
            for _, sym, s in sorted(cands, reverse=True):
                if len(positions) >= MAX_POSITIONS:
                    break
                budget = min(equity / MAX_POSITIONS, cash)
                qty = math.floor((budget - fee(budget)) / s["price"])
                if qty < 1:
                    continue
                cost = qty * s["price"]
                f = fee(cost)
                if cost + f > cash:
                    continue
                cash -= cost + f
                stop_pct = min(STOP_MAX_PCT, max(STOP_MIN_PCT, (1 - s["stop_price"] / s["price"]) * 100))
                target = s["sell_price"] if s["sell_price"] and s["sell_price"] > s["price"] * 1.02 \
                    else s["price"] * (1 + max(5.0, stop_pct * 1.5) / 100)
                positions[sym] = {"qty": qty, "entry": s["price"], "cost": cost + f, "day": day, "high": s["price"],
                                  "stop": s["price"] * (1 - stop_pct / 100), "stop_pct": stop_pct, "target": target}
        value = cash + sum(p["qty"] * last_px.get(s, p["entry"]) for s, p in positions.items())
        curve.append((day, value))
        exposure.append(1 - cash / value if value else 0)
    return {"curve": curve, "trades": trades, "exposure": sum(exposure) / len(exposure) if exposure else 0}


def equal_weight(closes: dict[str, pd.Series], first_day: str, dates: list[str]) -> list[tuple[str, float]]:
    """Repère : chaque titre de la liste acheté à parts égales au départ, puis gardé."""
    ref = {}
    for sym, s in closes.items():
        s = s.dropna()
        s.index = [ts.strftime("%Y-%m-%d") for ts in s.index]
        start = s[s.index >= first_day]
        if len(start):
            ref[sym] = s
    if not ref:
        return []
    out, last = [], {}
    for day in dates:
        for sym, s in ref.items():
            if day in s.index:
                last[sym] = s[day]
        vals = [last[s] / ref[s][ref[s].index >= first_day].iloc[0] for s in ref if s in last]
        if vals:
            out.append((day, CAPITAL * sum(vals) / len(vals)))
    return out


def stats(curve: list[tuple[str, float]], trades: list[dict] | None = None) -> dict:
    if len(curve) < 2:
        return {}
    values = pd.Series([v for _, v in curve], index=pd.to_datetime([d for d, _ in curve]))
    years = max((values.index[-1] - values.index[0]).days / 365.25, 0.1)
    peak = values.cummax()
    by_year = values.groupby(values.index.year).last()
    prev = values.iloc[0]
    yearly = {}
    for y, v in by_year.items():
        yearly[int(y)] = round((v / prev - 1) * 100, 1)
        prev = v
    out = {"final": round(float(values.iloc[-1]), 2),
           "total_pct": round((values.iloc[-1] / values.iloc[0] - 1) * 100, 1),
           "cagr_pct": round(((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1) * 100, 1),
           "max_drawdown_pct": round(float(((values / peak) - 1).min() * 100), 1),
           "yearly": yearly}
    if trades is not None:
        wins = [t for t in trades if t["pnl_pct"] > 0]
        out.update(trades=len(trades), win_rate_pct=round(len(wins) / len(trades) * 100) if trades else None,
                   avg_trade_pct=round(sum(t["pnl_pct"] for t in trades) / len(trades), 1) if trades else None)
    return out


def _weekly(curve: list[tuple[str, float]]) -> dict[str, float]:
    return {d: round(v, 2) for i, (d, v) in enumerate(curve) if i % 5 == 0 or i == len(curve) - 1}


# ── Lancement (tâche de fond) ───────────────────────────────────────────────
def universe(watchlist_id: int, user_id: int) -> tuple[str, list[str]]:
    with get_conn() as conn:
        wl = conn.execute("SELECT name FROM watchlists WHERE id = ? AND user_id = ?", (watchlist_id, user_id)).fetchone()
        if wl is None:
            raise ValueError("Liste introuvable")
        syms = [r["symbol"] for r in conn.execute(
            "SELECT DISTINCT symbol FROM watchlist_items WHERE watchlist_id = ? AND symbol IS NOT NULL "
            "AND (product_id LIKE 'yf:%' OR product_id IS NULL) ORDER BY position, id", (watchlist_id,))]
    if len(syms) > MAX_SYMBOLS:  # échantillon régulier de la liste
        step = len(syms) / MAX_SYMBOLS
        syms = [syms[int(i * step)] for i in range(MAX_SYMBOLS)]
    return wl["name"], syms


def start(user_id: int, watchlist_id: int, years: int) -> int:
    name, syms = universe(watchlist_id, user_id)
    if not syms:
        raise ValueError("Cette liste ne contient aucun titre testable.")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Un test est déjà en cours sur le serveur : réessaie dans quelques minutes.")
    params = {"watchlist_id": watchlist_id, "list": name, "years": years, "symbols": len(syms)}
    with get_conn() as conn:
        bid = conn.execute("INSERT INTO backtests (user_id, params, status, progress) VALUES (?, ?, 'running', 0)",
                           (user_id, json.dumps(params))).lastrowid
    threading.Thread(target=_run, args=(bid, syms, years, params), daemon=True).start()
    return bid


def _progress(bid: int, pct: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE backtests SET progress = ? WHERE id = ?", (pct, bid))


def _run(bid: int, syms: list[str], years: int, params: dict) -> None:
    try:
        result = run(syms, years, lambda pct: _progress(bid, pct))
        result["params"] = params
        status, payload = "done", json.dumps(result)
    except Exception as exc:
        logger.exception("Backtest impossible")
        status, payload = "error", json.dumps({"error": str(exc)[:300]})
    finally:
        _lock.release()
    with get_conn() as conn:
        conn.execute("UPDATE backtests SET status = ?, progress = 100, result = ?, finished_at = datetime('now') "
                     "WHERE id = ?", (status, payload, bid))


def run(syms: list[str], years: int, progress=lambda pct: None) -> dict:
    period = f"{years + 1}y"  # une année de plus pour la MM200 de départ
    hist = {}
    for k in range(0, len(syms), 40):
        hist.update(yahoo.history_many(syms[k:k + 40], period=period))
        progress(int(10 * min(1, (k + 40) / len(syms))))
    bench_df = yahoo.history(BENCH_SYMBOL, period=period)
    if bench_df is None or bench_df.empty:
        raise RuntimeError("Historique du MSCI World indisponible.")
    bench = bench_df["close"].dropna()
    signals, closes = {}, {}
    usable = [s for s, df in hist.items() if df is not None and len(df) > WARMUP + 20]
    for n, sym in enumerate(usable):
        try:
            signals[sym] = weekly_signals(hist[sym])
            closes[sym] = hist[sym]["close"]
        except Exception:
            logger.exception("Backtest : signaux impossibles pour %s", sym)
        progress(10 + int(80 * (n + 1) / max(1, len(usable))))
    results, rules_curve = {}, []
    for v in VARIANTS:
        sim = simulate(closes, signals, bench, v)
        st = stats(sim.get("curve", []), sim.get("trades", []))
        st["exposure_pct"] = round(sim.get("exposure", 0) * 100, 1)
        results[v["key"]] = {"label": v["label"], "stats": st, "curve": _weekly(sim.get("curve", []))}
        if v["key"] == "rules":
            rules_curve = sim.get("curve", [])
    first = rules_curve[0][0] if rules_curve else None
    dates = [d for d, _ in rules_curve]
    b = bench.copy()
    b.index = [ts.strftime("%Y-%m-%d") for ts in b.index]
    b = b[b.index >= first] if first else b
    bench_curve = [(d, CAPITAL * float(b[d]) / float(b.iloc[0])) for d in dates if d in b.index]
    ew = equal_weight(closes, first, dates) if first else []
    progress(100)
    return {"variants": results,
            "benchmark": {"label": "ETF MSCI World", "stats": stats(bench_curve), "curve": _weekly(bench_curve)},
            "equal_weight": {"label": "Tous les titres de la liste, achetés et gardés", "stats": stats(ew),
                             "curve": _weekly(ew)},
            "start": first, "end": dates[-1] if dates else None, "tested": len(signals), "capital": CAPITAL,
            "generated_at": datetime.now().isoformat(timespec="seconds")}


def latest(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM backtests WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if not row:
        return None
    out = {"id": row["id"], "status": row["status"], "progress": row["progress"], "created_at": row["created_at"],
           "params": json.loads(row["params"] or "{}")}
    if row["result"]:
        out["result"] = json.loads(row["result"])
    return out
