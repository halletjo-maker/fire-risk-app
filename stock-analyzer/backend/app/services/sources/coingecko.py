"""CoinGecko (API publique gratuite) — capitalisation et volume des cryptomonnaies."""
from __future__ import annotations

import json
import logging

from .http import fetch_text

logger = logging.getLogger(__name__)

SOURCE = "CoinGecko"
API = "https://api.coingecko.com/api/v3"


def _json(url: str, params: dict):
    text = fetch_text(url, params=params)
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def market(symbol: str, vs_currency: str = "eur") -> dict | None:
    """symbol = 'BTC', 'ETH'… ; renvoie capitalisation, volume 24 h, rang, offre."""
    found = _json(f"{API}/search", {"query": symbol})
    coins = [c for c in (found or {}).get("coins", []) if c.get("symbol", "").upper() == symbol.upper()]
    if not coins:
        return None
    coins.sort(key=lambda c: c.get("market_cap_rank") or 10**9)
    data = _json(f"{API}/coins/markets", {"vs_currency": vs_currency.lower(), "ids": coins[0]["id"]})
    if not data:
        return None
    d = data[0]
    return {
        "name": d.get("name"),
        "market_cap": d.get("market_cap"),
        "volume_24h": d.get("total_volume"),
        "rank": d.get("market_cap_rank"),
        "ath_change_pct": d.get("ath_change_percentage"),
        "circulating_supply": d.get("circulating_supply"),
        "max_supply": d.get("max_supply"),
        "currency": vs_currency.upper(),
        "source": SOURCE,
    }
