"""justETF (scraping) — fiche des ETF européens (UCITS) : TER, indice, taille, positions."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .http import fetch_text
from .parsing import fr_number

logger = logging.getLogger(__name__)

SOURCE = "justETF"
URL = "https://www.justetf.com/fr/etf-profile.html"


def profile(isin: str) -> dict | None:
    html = fetch_text(URL, params={"isin": isin})
    if not html:
        return None
    try:
        return parse_profile(html)
    except Exception:
        logger.exception("Fiche justETF illisible : %s", isin)
        return None


def _header_value(soup, key: str) -> str | None:
    wrap = soup.select_one(f'[data-testid="etf-profile-header_{key}-wrapper"]')
    if not wrap:
        return None
    val = wrap.select_one(".val") or (wrap.find_all("div", recursive=False) or [None])[-1]
    return " ".join(val.get_text(" ", strip=True).split()) if val else None


def parse_profile(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    ter = _header_value(soup, "ter")
    if ter is None:
        return None
    index_el = soup.select_one('[data-testid="tl_etf-basics_value_index-name"]')
    size = _header_value(soup, "fund-size")  # « EUR 133 172 M »
    size_value = fr_number(re.sub(r"^[A-Z]{3}\s*", "", size or ""))
    text = " ".join(soup.get_text(" ", strip=True).split())
    ytd = re.search(r"Année en cours\s+([-+]?\d+(?:,\d+)?)%", text)
    return {
        "ter_pct": fr_number(ter),
        "index": " ".join(index_el.get_text(" ", strip=True).split()) if index_el else None,
        "fund_size": size_value,
        "fund_size_currency": (size or "")[:3] if size and re.match(r"^[A-Z]{3}", size) else None,
        "holdings": int(fr_number(_header_value(soup, "holdings")) or 0) or None,
        "replication": _header_value(soup, "replication"),
        "distribution": _header_value(soup, "distribution-policy"),
        "inception": _header_value(soup, "inception-date"),
        "ytd_pct": fr_number(ytd.group(1)) if ytd else None,
        "source": SOURCE,
    }
