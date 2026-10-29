"""Priorité 1 — Yahoo Finance via yfinance (actions, ETF, crypto, indices)."""
from __future__ import annotations

import logging
import warnings

import yfinance as yf

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # erreurs gérées ici
warnings.filterwarnings("ignore", module="yfinance")

SOURCE = "Yahoo Finance"

TYPE_MAP = {
    "EQUITY": "ACTION",
    "ETF": "ETF",
    "MUTUALFUND": "AUTRE",
    "CRYPTOCURRENCY": "CRYPTO",
    "INDEX": "INDICE",
    "CURRENCY": "AUTRE",
    "FUTURE": "AUTRE",
}


def search(query: str, limit: int = 8) -> list[dict]:
    try:
        quotes = yf.Search(query, max_results=limit, news_count=0, raise_errors=False).quotes
    except Exception as exc:
        logger.info("Recherche Yahoo impossible (%s) : %s", query, exc)
        return []
    results = []
    for q in quotes or []:
        symbol = q.get("symbol")
        if not symbol or q.get("quoteType") not in TYPE_MAP:
            continue
        results.append(
            {
                "id": f"yf:{symbol}",
                "symbol": symbol,
                "name": q.get("longname") or q.get("shortname") or symbol,
                "type": TYPE_MAP[q["quoteType"]],
                "exchange": q.get("exchDisp") or q.get("exchange"),
                "exchange_code": q.get("exchange"),
                "source": SOURCE,
            }
        )
    return results


def quote(symbol: str) -> dict | None:
    """Cours actuel. La variation est calculée sur l'historique journalier
    (la « clôture veille » renvoyée directement par Yahoo est parfois fausse)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d", auto_adjust=False, raise_errors=False)
        meta = ticker.history_metadata or {}
    except Exception as exc:
        logger.info("Cours Yahoo impossible (%s) : %s", symbol, exc)
        return None
    if hist is None or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None

    price = meta.get("regularMarketPrice") or float(closes.iloc[-1])
    market_time = meta.get("regularMarketTime")
    last_bar_is_today = (
        market_time is not None and closes.index[-1].date() == market_time.date()
    )
    if last_bar_is_today and len(closes) >= 2:
        prev_close = float(closes.iloc[-2])
    elif not last_bar_is_today:
        prev_close = float(closes.iloc[-1])
    else:
        prev_close = None
    change = price - prev_close if prev_close else None
    volume = meta.get("regularMarketVolume")
    if not volume and "Volume" in hist:
        volume = int(hist["Volume"].iloc[-1] or 0)

    instrument = meta.get("instrumentType")
    return {
        "symbol": symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "type": TYPE_MAP.get(instrument, "AUTRE"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "exchange_code": meta.get("exchangeName"),
        "currency": meta.get("currency"),
        "price": round(float(price), 6),
        "prev_close": round(prev_close, 6) if prev_close else None,
        "change": round(change, 6) if change is not None else None,
        "change_pct": round(change / prev_close * 100, 2) if change is not None else None,
        "volume": int(volume) if volume else None,
        "time": market_time.isoformat() if market_time is not None else None,
        "source": SOURCE,
    }


def info(symbol: str) -> dict | None:
    """Fiche détaillée Yahoo (fondamentaux). Souvent limitée en fréquence : None si refus."""
    try:
        data = yf.Ticker(symbol).info
    except Exception as exc:
        logger.info("Fiche Yahoo impossible (%s) : %s", symbol, exc)
        return None
    # Une réponse refusée contient seulement quelques clés techniques
    if not data or len(data) < 10 or not (data.get("quoteType") or data.get("longName")):
        return None
    return data


def next_earnings(symbol: str):
    """Date des prochains résultats trimestriels (datetime.date) ou None."""
    try:
        cal = yf.Ticker(symbol).calendar or {}
    except Exception:
        return None
    dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
    return dates[0] if dates else None


def ytd_return(symbol: str) -> float | None:
    """Performance depuis le 1er janvier, en %, calculée sur l'historique."""
    try:
        hist = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False, raise_errors=False)
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    closes = hist["Close"].dropna()
    year = closes.index[-1].year
    before = closes[closes.index.year < year]
    if before.empty:
        return None
    return round((float(closes.iloc[-1]) / float(before.iloc[-1]) - 1) * 100, 2)
