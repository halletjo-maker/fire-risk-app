"""Module 4 — Analyse technique → score /10.

★ Critère principal : position du prix par rapport à la moyenne mobile 100 jours (MM100).
Compléments : MM50, MM200, RSI 14, MACD (12, 26, 9), Bollinger (20, 2), volume vs moyenne
20 jours, supports et résistances.

Le score est donné du point de vue d'un ACHAT du produit. Pour un turbo/warrant PUT,
l'analyse porte sur le sous-jacent et le score est inversé (10 − score) : un sous-jacent
haussier est défavorable à un put.
"""
from __future__ import annotations

import logging
import math

import pandas as pd
import pandas_ta as ta
import warnings

warnings.filterwarnings("ignore", module="pandas_ta")

from .fundamentals import crit, num, pct, tier, verdict
from .sources import boursorama, cache, yahoo

logger = logging.getLogger(__name__)

CACHE_TTL = 15 * 60
CHART_BARS = 260  # ≈ 1 an de séances
CROSS_WINDOW = 5  # un croisement de la MM100 dans les 5 dernières séances = « CROISEMENT »


# ---------------------------------------------------------------- données
def load_history(product: dict) -> tuple[pd.DataFrame | None, list[dict]]:
    """Historique journalier : Yahoo d'abord, Boursorama en secours."""
    pid = product["id"]
    sources = []
    df = None
    if pid.startswith("yf:"):
        df = yahoo.history(pid[3:], period="2y")
        sources.append({"name": yahoo.SOURCE, "ok": df is not None})
        if df is None:
            listing = boursorama.find_listing(pid[3:], kinds=("ACTION", "ETF", "INDICE"))
            df = boursorama.history(listing["id"][3:]) if listing else None
            sources.append({"name": boursorama.SOURCE, "ok": df is not None})
    elif pid.startswith("bo:"):
        df = boursorama.history(pid[3:])
        sources.append({"name": boursorama.SOURCE, "ok": df is not None})
    return df, sources


# ---------------------------------------------------------------- indicateurs
def indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    out["m50"] = ta.sma(close, 50)
    out["m100"] = ta.sma(close, 100)
    out["m200"] = ta.sma(close, 200)
    out["rsi"] = ta.rsi(close, 14)
    macd = ta.macd(close, 12, 26, 9)
    if macd is not None:
        out["macd"], out["hist"], out["sig"] = macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]
    bb = ta.bbands(close, 20, 2)
    if bb is not None:
        out["bbl"], out["bbm"], out["bbu"], out["bbp"] = bb.iloc[:, 0], bb.iloc[:, 1], bb.iloc[:, 2], bb.iloc[:, 4]
    out["vol20"] = out["volume"].rolling(20).mean()
    return out


def _val(x) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def mm100_status(d: pd.DataFrame) -> dict | None:
    """AU-DESSUS ✅ | EN-DESSOUS ❌ | CROISEMENT ⚡ (dans les 5 dernières séances)."""
    sub = d[["close", "m100"]].dropna()
    if sub.empty:
        return None
    above = sub["close"] > sub["m100"]
    last = sub.iloc[-1]
    distance = float((last["close"] / last["m100"] - 1) * 100)
    cross = None
    recent = above.iloc[-(CROSS_WINDOW + 1):]
    for i in range(len(recent) - 1, 0, -1):
        if recent.iloc[i] != recent.iloc[i - 1]:
            cross = {"direction": "HAUSSIER" if recent.iloc[i] else "BAISSIER", "sessions_ago": len(recent) - 1 - i}
            break
    m100 = sub["m100"]
    slope = float((m100.iloc[-1] / m100.iloc[-11] - 1) * 100) if len(m100) > 11 else None
    status = "CROISEMENT" if cross else ("AU-DESSUS" if above.iloc[-1] else "EN-DESSOUS")
    return {
        "status": status,
        "above": bool(above.iloc[-1]),
        "distance_pct": round(distance, 2),
        "value": round(float(last["m100"]), 4),
        "cross": cross,
        "slope_pct": round(slope, 2) if slope is not None else None,
    }


def supports_resistances(d: pd.DataFrame, price: float, window: int = 5, lookback: int = 130) -> dict:
    """Plus proches pivots (plus bas / plus hauts locaux) sous et au-dessus du prix."""
    sub = d.iloc[-lookback:]
    lows, highs = sub["low"], sub["high"]
    pivots_low = [lows.iloc[i] for i in range(window, len(sub) - window)
                  if lows.iloc[i] == lows.iloc[i - window:i + window + 1].min()]
    pivots_high = [highs.iloc[i] for i in range(window, len(sub) - window)
                   if highs.iloc[i] == highs.iloc[i - window:i + window + 1].max()]
    below = [p for p in pivots_low if p < price]
    above = [p for p in pivots_high if p > price]
    support = max(below) if below else (float(lows.iloc[-60:].min()) if float(lows.iloc[-60:].min()) < price else None)
    resistance = min(above) if above else (float(highs.iloc[-60:].max()) if float(highs.iloc[-60:].max()) > price else None)
    return {
        "support": round(float(support), 4) if support is not None else None,
        "resistance": round(float(resistance), 4) if resistance is not None else None,
        "support_distance_pct": round(float(support / price - 1) * 100, 2) if support else None,
        "resistance_distance_pct": round(float(resistance / price - 1) * 100, 2) if resistance else None,
    }


# ---------------------------------------------------------------- score
def score_criteria(d: pd.DataFrame, mm: dict | None) -> list[dict]:
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    price = float(last["close"])
    criteria = []

    # 1 ★ MM100 — critère principal (poids 35)
    if mm:
        dist = mm["distance_pct"]
        if mm["cross"]:
            up = mm["cross"]["direction"] == "HAUSSIER"
            s = 8 if up else 2.5
            when = "aujourd'hui" if mm["cross"]["sessions_ago"] == 0 else f"il y a {mm['cross']['sessions_ago']} séance(s)"
            comment = (f"⚡ Le prix vient de repasser au-dessus de la MM100 ({when}) : signal d'achat."
                       if up else f"⚡ Le prix vient de casser la MM100 à la baisse ({when}) : signal de vente.")
        elif mm["above"]:
            s = tier(dist, [(10, 8.5), (20, 7.5)], 6)
            comment = ("Tendance de fond haussière : le prix est au-dessus de sa MM100." if dist < 20 else
                       "Au-dessus de la MM100 mais très éloigné : risque de correction.")
        else:
            s = tier(dist, [(-15, 1.5), (-5, 2)], 3.5)
            comment = "Tendance de fond baissière : le prix est sous sa MM100."
        if mm["slope_pct"] is not None:
            s += 0.5 if mm["slope_pct"] > 0 else -0.5
            comment += " La MM100 monte." if mm["slope_pct"] > 0 else " La MM100 baisse."
        icon = {"AU-DESSUS": "✅", "EN-DESSOUS": "❌", "CROISEMENT": "⚡"}[mm["status"]]
        criteria.append(crit("mm100", "★ Position vs MM100", dist,
                             f"{icon} {mm['status']} · {pct(dist, 1, sign=True)}",
                             max(0, min(10, s)), 35, comment))
    else:
        criteria.append(crit("mm100", "★ Position vs MM100", None, "—", None, 35,
                             "Historique trop court (moins de 100 séances)."))

    # 2 Alignement des moyennes MM50 / MM200 (poids 15)
    m50, m200 = _val(last.get("m50")), _val(last.get("m200"))
    if m50 and m200:
        m100 = _val(last.get("m100"))
        if price > m50 > (m100 or m50) > m200:
            s, comment, display = 9, "Toutes les moyennes sont alignées à la hausse.", "Haussier"
        elif m50 > m200:
            s, comment, display = 7, "MM50 au-dessus de la MM200 : tendance positive.", "Plutôt haussier"
        elif price > m50:
            s, comment, display = 5, "MM50 sous la MM200 mais le prix se reprend.", "En reprise"
        else:
            s, comment, display = 3, "MM50 sous la MM200 : tendance négative.", "Baissier"
        criteria.append(crit("trend", "Tendance (MM50 / MM200)", round(m50 / m200 - 1, 4), display, s, 15, comment))
    elif m50:
        s = 7 if price > m50 else 3.5
        criteria.append(crit("trend", "Tendance (MM50)", None, "Au-dessus" if price > m50 else "En dessous", s, 15,
                             "MM200 indisponible (historique court)."))

    # 3 RSI 14 (poids 15)
    rsi = _val(last.get("rsi"))
    if rsi is not None:
        s = tier(rsi, [(30, 6), (45, 5), (60, 7), (70, 7.5)], 3.5)
        comment = ("Survente : rebond technique possible." if rsi < 30 else
                   "Momentum faible." if rsi < 45 else "Momentum sain." if rsi < 70 else
                   "Surachat : risque de repli à court terme.")
        criteria.append(crit("rsi", "RSI (14)", rsi, num(rsi, 1), s, 15, comment))

    # 4 MACD (poids 15)
    macd, sig = _val(last.get("macd")), _val(last.get("sig"))
    hist, hist_prev = _val(last.get("hist")), _val(prev.get("hist"))
    if macd is not None and sig is not None:
        rising = hist is not None and hist_prev is not None and hist > hist_prev
        crossed = hist is not None and hist_prev is not None and (hist > 0) != (hist_prev > 0)
        if macd > sig:
            s = 8 if rising else 7
            comment = "MACD au-dessus de son signal : dynamique positive."
            display = "Haussier"
        else:
            s = 4.5 if rising else 3
            comment = "MACD sous son signal : dynamique négative." + (" Elle s'atténue." if rising else "")
            display = "Baissier"
        if crossed:
            comment = ("Croisement haussier du MACD aujourd'hui." if hist > 0 else "Croisement baissier du MACD aujourd'hui.")
        criteria.append(crit("macd", "MACD (12, 26, 9)", macd - sig, display, s, 15, comment))

    # 5 Bollinger (poids 10)
    bbp = _val(last.get("bbp"))
    if bbp is not None:
        s = 4 if bbp > 1 else 7 if bbp >= 0.5 else 5 if bbp >= 0 else 5.5
        comment = ("Au-dessus de la bande haute : excès à la hausse." if bbp > 1 else
                   "Dans la moitié haute des bandes." if bbp >= 0.5 else
                   "Dans la moitié basse des bandes." if bbp >= 0 else
                   "Sous la bande basse : excès à la baisse, rebond possible.")
        criteria.append(crit("bollinger", "Bandes de Bollinger (20, 2)", bbp, f"{num(bbp * 100, 0)} % de la bande", s, 10, comment))

    # 6 Volume vs moyenne 20 jours (poids 10)
    vol, vol20 = _val(last.get("volume")), _val(last.get("vol20"))
    if vol and vol20:
        ratio = vol / vol20
        up_day = price >= float(prev["close"])
        if ratio >= 1.5:
            s = 8.5 if up_day else 3
            comment = ("Hausse accompagnée de forts volumes : mouvement confirmé." if up_day else
                       "Baisse sur forts volumes : pression vendeuse marquée.")
        else:
            s, comment = 6, "Volumes dans la normale."
        criteria.append(crit("volume", "Volume vs moyenne 20 jours", ratio, f"× {num(ratio, 2)}", s, 10, comment))
    return criteria


def quick_summary(df: pd.DataFrame) -> dict | None:
    """Analyse technique à partir d'un historique déjà chargé (listes larges, sans cache ni sous-jacent)."""
    if df is None or len(df) < 30:
        return None
    d = indicators(df)
    price = float(d["close"].iloc[-1])
    mm = mm100_status(d)
    scored = [c for c in score_criteria(d, mm) if c["score"] is not None]
    total_w = sum(c["weight"] for c in scored)
    score = sum(c["score"] * c["weight"] for c in scored) / total_w if total_w else None
    closes = d["close"].dropna()
    change = float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100) if len(closes) > 1 else None
    return {
        "applicable": True,
        "score": round(score, 1) if score is not None else None,
        "price": round(price, 4),
        "change_pct": round(change, 2) if change is not None else None,
        "mm100": mm,
        "levels": supports_resistances(d, price),
        "chart": chart_series(d, bars=40),  # suffisant pour la volatilité (ATR 14)
    }


# ---------------------------------------------------------------- graphique
def chart_series(d: pd.DataFrame, bars: int = CHART_BARS) -> list[dict]:
    cols = ["open", "high", "low", "close", "volume", "m50", "m100", "m200", "bbu", "bbl", "rsi", "macd", "sig", "hist"]
    out = []
    for ts, row in d.iloc[-bars:].iterrows():
        item = {"t": ts.strftime("%Y-%m-%d")}
        for c in cols:
            v = _val(row.get(c))
            item[c] = round(v, 4) if v is not None else None
        out.append(item)
    return out


# ---------------------------------------------------------------- point d'entrée
def _underlying_product(derivative: dict) -> dict | None:
    """Turbo / warrant : retrouve le sous-jacent (ex. « LVMH » → MC.PA)."""
    from . import market  # import local : évite une importation circulaire

    name = derivative.get("underlying")
    if not name:
        return None
    found = market.search(name)
    candidates = [c for c in found["candidates"] if c["type"] in ("ACTION", "INDICE", "ETF", "CRYPTO")]
    euro = [c for c in candidates if c.get("exchange_code") in ("PAR", "AMS", "BRU", "GER", "MIL")]
    best = (euro or candidates or [None])[0]
    return best


def analyze(product: dict, quote: dict, derivative: dict | None = None) -> dict:
    key = f"tech:{product['id']}"
    cached = cache.get(key, CACHE_TTL)
    if cached:
        return cached

    target, inverse, note = product, False, None
    if product.get("type") in ("TURBO", "WARRANT"):
        under = _underlying_product(derivative or {}) if derivative else None
        if under is None:
            return _unavailable("Sous-jacent introuvable : analyse technique impossible pour ce produit.")
        target = under
        inverse = (derivative or {}).get("direction") == "PUT"
        note = (f"Analyse réalisée sur le sous-jacent {under['name']} ({under.get('symbol') or ''})."
                + (" Turbo PUT : le score est inversé (un sous-jacent baissier lui est favorable)." if inverse else ""))

    try:
        df, sources = load_history(target)
        if df is None or len(df) < 30:
            return _unavailable("Historique de cours indisponible.", sources)
        d = indicators(df)
        price = float(d["close"].iloc[-1])
        mm = mm100_status(d)
        criteria = score_criteria(d, mm)
        scored = [c for c in criteria if c["score"] is not None]
        total_w = sum(c["weight"] for c in scored)
        raw = sum(c["score"] * c["weight"] for c in scored) / total_w if total_w else None
        score = (10 - raw) if (raw is not None and inverse) else raw
        levels = supports_resistances(d, price)
        last = d.iloc[-1]
        result = {
            "applicable": True,
            "score": round(score, 1) if score is not None else None,
            "underlying_score": round(raw, 1) if inverse and raw is not None else None,
            "verdict": verdict(score),
            "inverse": inverse,
            "analysed": {"name": target.get("name"), "symbol": target.get("symbol"), "id": target["id"]},
            "price": round(price, 4),
            "mm100": mm,
            "levels": levels,
            "averages": {k: _val(last.get(k)) and round(_val(last.get(k)), 4) for k in ("m50", "m100", "m200")},
            "criteria": criteria,
            "chart": chart_series(d),
            "sources": sources,
            "notes": [n for n in [note] if n] + ([] if len(df) >= 200 else ["Historique court : MM200 indisponible."]),
            "currency": target.get("currency") or product.get("currency"),
        }
    except Exception:
        logger.exception("Analyse technique impossible pour %s", product.get("id"))
        return _unavailable("Analyse technique momentanément indisponible.")
    cache.put(key, result, source="technical")
    return result


def _unavailable(message: str, sources: list | None = None) -> dict:
    return {"applicable": False, "score": None, "verdict": None, "criteria": [], "chart": [],
            "mm100": None, "levels": {}, "sources": sources or [], "notes": [message]}
