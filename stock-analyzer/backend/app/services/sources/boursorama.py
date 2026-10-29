"""Priorité 3 — Boursorama (scraping) : turbos, warrants, produits dérivés européens.

Sert aussi de secours pour les actions / ETF / indices européens.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup

from .http import fetch_text
from .parsing import fr_number

logger = logging.getLogger(__name__)

SOURCE = "Boursorama"
BASE = "https://www.boursorama.com"

LABEL_TYPES = {
    "action": "ACTION",
    "etf": "ETF",
    "etf-etn": "ETF",
    "tracker": "ETF",
    "indice": "INDICE",
    "opcvm": "AUTRE",
    "crypto": "CRYPTO",
    "devise": "AUTRE",
    "produit de bourse": "DERIVE",
}

# Champs des fiches produits dérivés (libellé Boursorama → clé interne)
DERIVATIVE_FIELDS = {
    "sous-jacent": "underlying",
    "spot": "spot",
    "barrier": "barrier",
    "barriere": "barrier",
    "barriere desactivante": "barrier",
    "strike/barrier": "strike_barrier",  # turbos « Best » : strike = barrière
    "strike 2": "_ignore",
    "strike": "strike",
    "emetteur": "issuer",
    "nature / type": "nature",
    "type": "nature",
    "effet de levier": "leverage",
    "parite": "parity",
    "sens": "direction",
    "maturite": "maturity",
    "date d'echeance": "maturity",
    "statuts": "status",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _clean(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def derivative_type(name: str, nature: str | None = None) -> str:
    """TURBO, WARRANT ou AUTRE (tracker, bonus, levier…).

    La nature lue sur la fiche fait foi ; à défaut on se base sur le nom court
    (ex. « CAC40/SGE P-WT OPEN » = turbo, « MC/SGE WT 07.26 » = warrant,
    « MC/SGE OPEN » = certificat tracker).
    """
    if nature and re.search(r"[a-zA-Z]", nature):
        n = _norm(nature)
        if "turbo" in n or "mini" in n or "best" in n:
            return "TURBO"
        if "warrant" in n:
            return "WARRANT"
        return "AUTRE"
    n = name.upper()
    if re.search(r"TURBO|MINI|TCI|SPS?OPEN|[CP]-WT|\bPW\b|\bWT OPEN\b", n):
        return "TURBO"
    if re.search(r"\bWT\b|WARRANT", n):
        return "WARRANT"
    return "AUTRE"


def search(query: str, limit: int = 10) -> list[dict]:
    html = fetch_text(f"{BASE}/recherche/ajax", params={"query": query})
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results, seen = [], set()
    for a in soup.select("a.search__list-link[href*='cours']"):
        href = a.get("href", "").split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        title = _clean(a.select_one(".search__item-title"))
        meta = [_clean(s) for s in a.select(".o-flex span.u-color-neutral:not(.c-source__bullet)")]
        label = meta[0] if meta else ""
        code = meta[1] if len(meta) > 1 else None
        market = _clean(a.select_one(".search__item-content")) or None
        kind = LABEL_TYPES.get(_norm(label), "AUTRE")
        if kind == "DERIVE":
            kind = derivative_type(title)
        is_isin = bool(code and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", code))
        price_el = a.select_one(".search__item-instrument .last")
        var_el = a.select_one(".search__item-instrument span:not(.last)")
        results.append(
            {
                "id": f"bo:{href}",
                "symbol": code if code and not is_isin else None,
                "isin": code if is_isin else None,
                "name": title,
                "type": kind,
                "exchange": None if market == "Dir Emet" else market,
                "issuer_market": market == "Dir Emet",
                "price": fr_number(_clean(price_el)),
                "change_pct": fr_number(_clean(var_el)),
                "source": SOURCE,
            }
        )
        if len(results) >= limit:
            break
    return results


def quote(path: str) -> dict | None:
    """Fiche produit Boursorama (action, ETF, indice, turbo, warrant…)."""
    if not path.startswith("/"):
        return None
    html = fetch_text(BASE + path)
    if not html:
        return None
    try:
        return parse_quote_page(html, path)
    except Exception:
        logger.exception("Fiche Boursorama illisible : %s", path)
        return None


def parse_quote_page(html: str, path: str = "") -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    face = soup.select_one(".c-faceplate")
    if face is None:
        return None

    def inst(name: str):
        return fr_number(_clean(face.select_one(f".c-instrument--{name}")))

    price = inst("last")
    if price is None:
        return None
    prev_close = inst("previousclose")
    change_pct = inst("variation")
    change = price - prev_close if prev_close else None
    if change_pct is None and change is not None and prev_close:
        change_pct = round(change / prev_close * 100, 2)

    currency_el = face.select_one(".c-faceplate__price-currency")
    currency = _clean(currency_el) or None
    isin_text = _clean(face.select_one(".c-faceplate__isin"))
    isin = next((t for t in isin_text.split() if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", t)), None)
    code = next((t for t in isin_text.split() if t != isin), None)
    name = _clean(face.select_one(".c-faceplate__company-link")) or _clean(soup.select_one("h1"))
    name = re.sub(r"^Cours\s+", "", name)

    trade_time = _clean(face.select_one(".c-instrument--last-trade-datetime"))
    iso_time = None
    if trade_time:
        try:
            iso_time = datetime.strptime(trade_time, "%d/%m/%Y %H:%M:%S").isoformat()
        except ValueError:
            pass

    # Champs « clé : valeur » de la fiche (utile pour les dérivés)
    fields: dict[str, str] = {}
    for li in soup.select("li.c-list-info__item"):
        text = _clean(li)
        normalized = _norm(text)
        for label, key in DERIVATIVE_FIELDS.items():
            if normalized.startswith(label + " ") and key not in fields:
                # valeur = texte original sans le libellé (accents conservés)
                fields[key] = " ".join(text.split()[len(label.split()):])
                break

    kind = _type_from_path(path)
    derivative = None
    if kind == "DERIVE" or fields.get("barrier") or fields.get("leverage"):
        kind = derivative_type(name, fields.get("nature"))
        derivative = _derivative(fields)

    volume = inst("totalvolume")
    return {
        "symbol": code,
        "isin": isin,
        "name": name,
        "type": kind,
        "exchange": None,
        "currency": currency,
        "price": price,
        "prev_close": prev_close,
        "change": round(change, 6) if change is not None else None,
        "change_pct": change_pct,
        "volume": int(volume) if volume else None,
        "time": iso_time,
        "derivative": derivative,
        "source": SOURCE,
    }


def _type_from_path(path: str) -> str:
    if "/produits-de-bourse/" in path:
        return "DERIVE"
    if "/trackers/" in path:
        return "ETF"
    if "/indices/" in path:
        return "INDICE"
    if "/opcvm/" in path:
        return "AUTRE"
    return "ACTION"


def _derivative(fields: dict[str, str]) -> dict:
    nature = fields.get("nature")
    spot_text = fields.get("spot")
    spot = fr_number(spot_text.split()[0]) if spot_text else None
    barrier = fr_number(fields.get("barrier") or fields.get("strike_barrier"))
    strike = fr_number(fields.get("strike") or fields.get("strike_barrier"))
    direction_text = _norm(f"{fields.get('direction', '')} {fields.get('nature', '')}")
    if "put" in direction_text or "short" in direction_text:
        direction = "PUT"
    elif "call" in direction_text or "long" in direction_text:
        direction = "CALL"
    else:
        direction = None
    distance = None
    if spot and barrier:
        # Distance (en %) que le sous-jacent doit parcourir pour toucher la barrière
        distance = (barrier - spot) / spot * 100 if direction == "PUT" else (spot - barrier) / spot * 100
        distance = round(distance, 2)
    return {
        "underlying": fields.get("underlying"),
        "nature": nature if nature and re.search(r"[a-zA-Z]", nature) else None,
        "direction": direction,
        "issuer": fields.get("issuer"),
        "spot": spot,
        "barrier": barrier,
        "strike": strike,
        "barrier_distance_pct": distance,
        "leverage": fr_number(fields.get("leverage")),
        "parity": fr_number(fields.get("parity")),
        "maturity": fields.get("maturity"),
        "status": fields.get("status"),
    }
