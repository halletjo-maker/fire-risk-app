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
        bid = fr_number(_clean(face.select_one("[data-ist-bid-price]")))
        ask = fr_number(_clean(face.select_one("[data-ist-ask-price]")))
        derivative["bid"], derivative["ask"] = bid, ask
        derivative["spread_pct"] = (
            round((ask - bid) / ((ask + bid) / 2) * 100, 2) if bid and ask and ask >= bid else None
        )

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


# ---------------------------------------------------------------- fondamentaux
def find_listing(symbol: str, kinds: tuple[str, ...] = ("ACTION",)) -> dict | None:
    """Retrouve la fiche Boursorama d'un symbole Yahoo (ex. SOLB.BR → /cours/FF11-SOLB/)."""
    base = symbol.split(".")[0].lstrip("^").upper()
    for c in search(base, limit=8):
        if c["type"] in kinds and (c.get("symbol") or "").upper() == base:
            return c
    return None


def _cells(tr) -> list[str]:
    return [" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["th", "td"])]


def consensus(path: str) -> dict | None:
    """Page « consensus » d'une action : avis des analystes, objectif, prévisions."""
    m = re.search(r"/cours/(?:[^/]+/)*([^/]+)/?$", path)
    if not m:
        return None
    html = fetch_text(f"{BASE}/cours/consensus/{m.group(1)}/")
    if not html:
        return None
    try:
        return parse_consensus(html)
    except Exception:
        logger.exception("Consensus Boursorama illisible : %s", path)
        return None


def parse_consensus(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    rows: dict[str, list[str]] = {}
    for tb in soup.select("table.c-table--generic"):
        for tr in tb.find_all("tr"):
            cells = _cells(tr)
            if len(cells) >= 2 and cells[0]:
                rows.setdefault(_norm(re.sub(r"\(\d\)|⁽\d⁾", "", cells[0])).strip(), cells[1:])
    if not rows:
        return None

    def last(label):  # dernière colonne (situation actuelle)
        return rows.get(label, [None])[-1]

    def current_year(label):  # colonne « Estimation année en cours » = 2e colonne
        vals = rows.get(label)
        return vals[1] if vals and len(vals) > 1 else None

    def pair(text):
        """« 4 262 -9% » → (4262.0, -9.0)."""
        if not text:
            return None, None
        m2 = re.match(r"^(.*?)\s+([-+]?\d+(?:,\d+)?)\s?%$", text)
        if m2:
            return fr_number(m2.group(1)), fr_number(m2.group(2))
        return fr_number(text), None

    target_text = last("historique des objectifs de cours median (en eur)") or next(
        (v[-1] for k, v in rows.items() if k.startswith("historique des objectifs de cours")), None
    )
    target = fr_number(target_text.split("Potentiel")[0]) if target_text else None
    potential = re.search(r"Potentiel\s*:\s*([-+]?\d+(?:,\d+)?)\s*%", target_text or "")
    opinions = {
        k.split(". ", 1)[-1]: int(fr_number(last(k)) or 0)
        for k in rows if re.match(r"^\d\. ", k)
    }
    revenue, revenue_growth = pair(current_year("chiffre d'affaires (en millions)"))
    ebit, _ = pair(current_year("ebit"))
    ebitda, _ = pair(current_year("ebitda"))
    net_debt, _ = pair(current_year("dette financiere nette"))
    eps, _ = pair(current_year("benefice net par action"))
    dividend, _ = pair(current_year("dividende par action"))
    yield_pct, _ = pair(current_year("rendement"))
    cfps, _ = pair(current_year("cash flow par action"))
    analysts = fr_number(last("nombre d'analystes"))
    return {
        "analysts": int(analysts) if analysts else None,
        "median_rating": fr_number(last("note mediane")),  # 1 = Acheter … 5 = Vendre
        "opinions": opinions or None,
        "target_median": target,
        "upside_pct": fr_number(potential.group(1)) if potential else None,
        "eps_est": eps,
        "dividend_est": dividend,
        "dividend_yield_pct": yield_pct,
        "revenue_est": revenue,
        "revenue_growth_pct": revenue_growth,
        "ebit_margin_pct": round(ebit / revenue * 100, 2) if ebit is not None and revenue else None,
        "net_debt_to_ebitda": round(net_debt / ebitda, 2) if net_debt is not None and ebitda and ebitda > 0 else None,
        "cash_flow_per_share": cfps,
        "source": SOURCE,
    }


def etf_details(path: str) -> dict | None:
    """Fiche tracker Boursorama : indice, actif net, frais de gestion, réplication."""
    html = fetch_text(BASE + path)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    fields: dict[str, str] = {}
    for li in soup.select("li.c-list-info__item"):
        text = _clean(li)
        for label in ("indice de reference", "actif net", "frais de gestion maximum", "replication",
                      "affectation des resultats", "date de creation"):
            if _norm(text).startswith(label) and label not in fields:
                fields[label] = text
    if not fields:
        return None
    size = fields.get("actif net", "")
    size_cur = re.search(r"\(([A-Z]{3})\)", size)
    size_val = re.search(r"\)\s*([\d\s,]+)\s*M", size)
    isin_text = _clean(soup.select_one(".c-faceplate__isin"))
    isin = next((t for t in isin_text.split() if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", t)), None)

    def value(label):
        t = fields.get(label)
        return " ".join(t.split()[len(label.split()):]) if t else None

    return {
        "isin": isin,
        "index": value("indice de reference"),
        "ter_pct": fr_number(value("frais de gestion maximum")),
        "fund_size": fr_number(size_val.group(1)) * 1e6 if size_val else None,
        "fund_size_currency": size_cur.group(1) if size_cur else None,
        "replication": value("replication"),
        "distribution": value("affectation des resultats"),
        "inception": value("date de creation"),
        "holdings": None,
        "ytd_pct": None,
        "source": SOURCE,
    }


def history(path: str, days: int = 730):
    """Historique journalier Boursorama (secours) → DataFrame open/high/low/close/volume."""
    import json

    import pandas as pd

    m = re.search(r"/cours/(?:[^/]+/)*([^/]+)/?$", path)
    if not m:
        return None
    text = fetch_text(
        f"{BASE}/bourse/action/graph/ws/GetTicksEOD",
        params={"symbol": m.group(1), "length": str(days), "period": "0", "guid": ""},
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}{path}"},
    )
    if not text:
        return None
    try:
        ticks = json.loads(text)["d"]["QuoteTab"]
    except (ValueError, KeyError, TypeError):
        return None
    if not ticks:
        return None
    df = pd.DataFrame(ticks)
    df.index = pd.to_datetime(df["d"], unit="D")  # jours depuis le 01/01/1970
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["open", "high", "low", "close", "volume"]].astype(float)


# Secteur Boursorama (français) → secteur Yahoo (anglais) par mots-clés
_SECTOR_KEYWORDS = [
    ("Technology", r"logiciel|informatique|technolog|semi-?conduct|electronique|internet"),
    ("Healthcare", r"pharma|sante|biotech|medic|hopita"),
    ("Financial Services", r"banque|assurance|financ|credit|gestion d'actifs"),
    ("Energy", r"petrol|gaz|energie|parapetro"),
    ("Utilities", r"electricite|services aux collectivites|eau\b|distribution d'energie"),
    ("Basic Materials", r"chimi|materiaux|mines|metaux|acier|papier"),
    ("Consumer Defensive", r"alimentaire|boisson|brasse|hygiene|tabac|grande distribution"),
    ("Consumer Cyclical", r"automobile|luxe|textile|loisir|habillement|distribution|hotel|voyage|biens de consommation"),
    ("Communication Services", r"telecom|media|publicite|divertissement"),
    ("Real Estate", r"immobili|fonciere"),
    ("Industrials", r"industri|aeronaut|defense|construction|transport|equipement|ingenierie"),
]


def sector(path: str) -> str | None:
    """Secteur d'une action d'après sa fiche Boursorama, traduit en secteur Yahoo."""
    html = fetch_text(BASE + path)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for li in soup.select("li.c-list-info__item"):
        text = _norm(_clean(li))
        if text.startswith("secteur"):
            for name, pattern in _SECTOR_KEYWORDS:
                if re.search(pattern, text):
                    return name
    return None
