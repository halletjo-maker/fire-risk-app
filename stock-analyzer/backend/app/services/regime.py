"""Repère MSCI World : courbe de comparaison et filtre de marché des portefeuilles fictifs.

Filtre de marché : quand l'ETF MSCI World clôture sous sa moyenne mobile 100 jours (MM100),
le marché mondial est en tendance baissière → les portefeuilles fictifs n'ouvrent plus de
nouvelles lignes (les ventes continuent normalement). Les achats reprennent dès que l'ETF
repasse au-dessus. Si le repère est indisponible, rien n'est bloqué.
"""
from __future__ import annotations

from .sources import cache, yahoo

SYMBOL, LABEL = "IWDA.AS", "ETF MSCI World"
TTL = 3600
MM = 100


def closes() -> list[tuple[str, float]]:
    """Clôtures journalières sur ~1 an [(AAAA-MM-JJ, cours)], en cache 1 h."""
    key = f"bench:{SYMBOL}"
    data = cache.get(key, TTL)
    if data is None:
        df = yahoo.history(SYMBOL, period="1y")
        data = [] if df is None else [[ts.strftime("%Y-%m-%d"), float(c)] for ts, c in df["close"].dropna().items()]
        if data:
            cache.put(key, data, source="Yahoo Finance")
    return [(d, c) for d, c in data or []]


def regime() -> dict:
    """{'available', 'ok' (achats autorisés), 'price', 'mm100', 'distance_pct', 'label'}."""
    series = closes()
    if len(series) < MM:
        return {"available": False, "ok": True, "label": LABEL}
    price = series[-1][1]
    mm100 = sum(c for _, c in series[-MM:]) / MM
    return {"available": True, "ok": price >= mm100, "price": round(price, 2), "mm100": round(mm100, 2),
            "distance_pct": round((price / mm100 - 1) * 100, 2), "label": LABEL, "day": series[-1][0]}


def indexed(days: list[str], start_day: str, base_value: float) -> list[float | None]:
    """Valeur qu'aurait eue `base_value` placé dans l'ETF le `start_day`, pour chaque jour de `days`."""
    series = closes()
    if not series:
        return [None] * len(days)

    def close_on(day: str) -> float | None:
        last = None
        for d, c in series:
            if d > day:
                break
            last = c
        return last

    base = close_on(start_day) or series[0][1]
    out = []
    for day in days:
        c = close_on(day)
        out.append(round(base_value * c / base, 2) if c else None)
    return out
