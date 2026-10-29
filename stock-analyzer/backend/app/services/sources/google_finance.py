"""Priorité 2 — Google Finance (scraping) : prix et variation du jour.

Les classes CSS de Google changent souvent : on lit le texte de la page
(« ServiceNow 108,80 $US arrow_downward -27,22% ( -40,70 ) Aujourd'hui »).
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .http import fetch_text
from .parsing import fr_number

logger = logging.getLogger(__name__)

SOURCE = "Google Finance"
URL = "https://www.google.com/finance/quote/{code}"

# Suffixe Yahoo → code de place Google
SUFFIX_EXCHANGE = {
    "BR": "EBR", "PA": "EPA", "AS": "AMS", "DE": "ETR", "F": "FRA", "L": "LON",
    "MI": "BIT", "MC": "BME", "SW": "SWX", "LS": "ELI", "TO": "TSE", "VI": "VIE",
    "CO": "CPH", "ST": "STO", "HE": "HEL", "OL": "OSL",
}
# Place Yahoo (actions US) → code Google
US_EXCHANGE = {
    "NYQ": "NYSE", "NYSE": "NYSE", "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
    "NASDAQ": "NASDAQ", "PCX": "NYSEARCA", "ASE": "NYSEAMERICAN", "BTS": "BATS",
}
INDICES = {
    "^FCHI": "PX1:INDEXEURO", "^BFX": "BEL20:INDEXEURO", "^GDAXI": "DAX:INDEXDB",
    "^STOXX50E": "SX5E:INDEXSTOXX", "^GSPC": ".INX:INDEXSP", "^DJI": ".DJI:INDEXDJX",
    "^IXIC": ".IXIC:INDEXNASDAQ", "^AEX": "AEX:INDEXEURO", "^FTSE": "UKX:INDEXFTSE",
}

_PRICE_RE = re.compile(
    r"(?P<price>\d[\d\u00a0\u202f.,]*)\s*(?P<cur>\$US|\$|€|EUR|USD|£|GBX|CHF|CAD)?\s*"
    r"arrow_(?P<dir>upward|downward)\s*(?P<pct>[-+−]?\d+(?:[.,]\d+)?)\s*%"
)


def google_code(symbol: str, exchange_code: str | None = None) -> list[str]:
    """Codes Google à essayer pour un symbole Yahoo."""
    if symbol in INDICES:
        return [INDICES[symbol]]
    if symbol.startswith("^"):
        return []
    if "-" in symbol and symbol.split("-")[-1] in {"USD", "EUR", "GBP", "CHF"}:
        return [symbol]  # crypto, ex. BTC-EUR
    if "." in symbol:
        base, suffix = symbol.rsplit(".", 1)
        exch = SUFFIX_EXCHANGE.get(suffix.upper())
        return [f"{base}:{exch}"] if exch else []
    if exchange_code and exchange_code.upper() in US_EXCHANGE:
        return [f"{symbol}:{US_EXCHANGE[exchange_code.upper()]}"]
    return [f"{symbol}:NASDAQ", f"{symbol}:NYSE", f"{symbol}:NYSEARCA"]


def quote(symbol: str, exchange_code: str | None = None) -> dict | None:
    for code in google_code(symbol, exchange_code):
        html = fetch_text(URL.format(code=code), params={"hl": "fr"})
        if not html:
            continue
        result = parse_quote_page(html, anchor=code)
        if result:
            result["symbol"] = symbol
            return result
    return None


def parse_quote_page(html: str, anchor: str | None = None) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    title = " ".join((soup.title.get_text(strip=True) if soup.title else "").split())
    name = title.split(" - Google")[0]
    if " pour " in name:
        name = name.rsplit(" pour ", 1)[1]
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip() or None
    # On garde les espaces insécables : ce sont les séparateurs de milliers (« 7 970,00 »).
    text = re.sub(r"[ \t\r\n]+", " ", soup.get_text(" ", strip=True))
    # Le haut de page contient un bandeau d'autres cours : on part du bloc principal.
    start = -1
    for marker in (anchor, "Ajouter à la liste"):
        if marker:
            start = text.find(marker)
            if start >= 0:
                break
    m = _PRICE_RE.search(text, max(start, 0))
    if not m:
        return None
    price = fr_number(m.group("price"))
    pct = fr_number(m.group("pct"))
    if price is None or pct is None:
        return None
    if m.group("dir") == "downward" and pct > 0:
        pct = -pct
    prev_close = price / (1 + pct / 100) if pct > -100 else None
    volume_m = re.search(r"Volume\s+(\d[\d,.\s]*\s?(?:k|M|Md)?)\b", text)
    cur = {"$US": "USD", "$": "USD", "€": "EUR", "£": "GBP"}.get(m.group("cur"), m.group("cur"))
    return {
        "symbol": None,
        "name": name,
        "type": None,
        "exchange": None,
        "currency": cur,
        "price": price,
        "prev_close": round(prev_close, 6) if prev_close else None,
        "change": round(price - prev_close, 6) if prev_close else None,
        "change_pct": pct,
        "volume": int(fr_number(volume_m.group(1))) if volume_m else None,
        "time": None,
        "source": SOURCE,
    }
