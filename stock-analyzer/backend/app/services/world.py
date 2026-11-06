"""Liste « Monde 500 + cryptos » : les plus grosses sociétés des marchés accessibles depuis la
Belgique, réparties ≈ 1/3 Amériques, 1/3 Europe, 1/3 Asie-Pacifique, plus 20 grandes cryptos.

Composition : filtre d'actions de Yahoo Finance, pays par pays, sur la Bourse principale, en
devise locale, sans certificats (CDR/SDR), obligations ni doubles cotations. Si Yahoo ne
répond pas, une liste de référence enregistrée (data/world500.json) est utilisée.
Les zones servent au calendrier : chaque zone est mise à jour pendant ses heures d'ouverture.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "world500.json"

# Les sociétés américaines viennent de la liste Nasdaq (qui indique le pays de la société) : elles
# sont exclues des autres Bourses (Apple cotée à Zurich ou Francfort…). Puis ordre de priorité en
# cas de double cotation : marchés d'origine d'abord, Francfort (cotations étrangères) en dernier.
REGIONS = [
    # pays, Bourses Yahoo, devises de cotation, quota, zone, devise des comptes exigée (sinon None)
    ("jp", ["JPX"], {"JPY"}, 75, "asia", None),
    ("hk", ["HKG"], {"HKD"}, 45, "asia", None),
    ("au", ["ASX"], {"AUD"}, 36, "asia", None),
    ("sg", ["SES"], {"SGD"}, 10, "asia", None),
    ("nl", ["AMS"], {"EUR"}, 15, "europe", None),
    ("be", ["BRU"], {"EUR"}, 5, "europe", None),
    ("fr", ["PAR"], {"EUR"}, 30, "europe", None),
    ("es", ["MCE"], {"EUR"}, 10, "europe", "EUR"),
    ("it", ["MIL"], {"EUR"}, 10, "europe", "EUR"),
    ("ch", ["EBS"], {"CHF"}, 20, "europe", None),
    ("gb", ["LSE"], {"GBp", "GBP"}, 30, "europe", None),
    ("se", ["STO"], {"SEK"}, 8, "europe", None),
    ("dk", ["CPH"], {"DKK"}, 6, "europe", None),
    ("fi", ["HEL"], {"EUR"}, 3, "europe", None),
    ("ca", ["TOR"], {"CAD"}, 27, "americas", None),
    ("de", ["GER"], {"EUR"}, 30, "europe", "EUR"),
]
US_QUOTA = 140  # sociétés américaines : liste Nasdaq (pays « United States »), traitées en premier
CRYPTOS = ["BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "ADA", "TRX", "LINK", "AVAX",
           "XLM", "DOT", "LTC", "BCH", "SHIB", "UNI", "NEAR", "ATOM", "HBAR", "ETC"]
CRYPTO_NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "XRP": "XRP", "BNB": "BNB", "SOL": "Solana", "DOGE": "Dogecoin",
                "ADA": "Cardano", "TRX": "TRON", "LINK": "Chainlink", "AVAX": "Avalanche", "XLM": "Stellar",
                "DOT": "Polkadot", "LTC": "Litecoin", "BCH": "Bitcoin Cash", "SHIB": "Shiba Inu", "UNI": "Uniswap",
                "NEAR": "NEAR Protocol", "ATOM": "Cosmos", "HBAR": "Hedera", "ETC": "Ethereum Classic"}

_JUNK = re.compile(r"%|\bCDR\b|\bSDR\b|\bETF\b|\bETC\b|\bETN\b|\bwarrant|\bpref|\bnotes?\b|\bbond\b|\b\d{2}/\d{2}\b", re.I)
_SUFFIX_WORDS = {
    "inc", "incorporated", "corp", "corporation", "plc", "ag", "sa", "se", "nv", "ltd", "limited", "co", "company",
    "holdings", "holding", "group", "the", "class", "ord", "adr", "spa", "ab", "asa", "oyj", "as", "kgaa", "n", "v",
    "s", "a", "b", "c", "de", "et", "cie", "plc.", "reit", "tbk", "bhd", "pjsc", "sab", "cv", "and", "&",
    "capital", "stock", "shares", "share", "common", "ordinary",
}


def company_key(name: str) -> str:
    """Nom normalisé pour repérer une même société cotée à plusieurs endroits."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in _SUFFIX_WORDS]
    return " ".join(words[:3])


def _screen(region: str, exchanges: list[str], size: int) -> list[dict]:
    import yfinance as yf
    from yfinance import EquityQuery as Q

    q = Q("and", [Q("eq", ["region", region]), Q("is-in", ["exchange", *exchanges]),
                  Q("gt", ["intradaymarketcap", 5e8])])
    last = None
    for attempt in range(4):  # Yahoo limite parfois les requêtes : on réessaie
        try:
            return yf.screen(q, size=size, sortField="intradaymarketcap", sortAsc=False).get("quotes", [])
        except Exception as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Filtre Yahoo indisponible ({region}) : {last}")


def us_members(rows: list[dict], size: int = US_QUOTA) -> list[dict]:
    """Plus grosses sociétés américaines (hors ADR de sociétés étrangères) d'après Nasdaq."""
    from .screens import _NOT_STOCK, _cap, clean_name

    best: dict[str, dict] = {}
    for r in rows:
        sym, name = (r.get("symbol") or "").strip(), r.get("name") or ""
        if r.get("country") != "United States" or not sym or "^" in sym or _NOT_STOCK.search(name) or _cap(r) <= 0:
            continue
        key = company_key(clean_name(name))
        if key and (key not in best or _cap(r) > _cap(best[key])):
            best[key] = r
    chosen = sorted(best.values(), key=_cap, reverse=True)[:size]
    return [{"symbol": r["symbol"].strip().replace("/", "-"), "name": clean_name(r["name"]), "region": "us",
             "zone": "americas", "currency": "USD", "type": "ACTION"} for r in chosen]


def build_live() -> list[dict]:
    """Composition à jour (≈ 40 s). Lève RuntimeError si Nasdaq ou Yahoo ne répond pas."""
    from .screens import fetch_universe

    members = us_members(fetch_universe())
    seen: set[str] = {company_key(m["name"]) for m in members}
    us_tickers = {m["symbol"] for m in members}
    for region, exchanges, currencies, quota, zone, reporting in REGIONS:
        # Même capitalisation pour deux lignes d'une société : la ligne au ticker le plus court d'abord
        quotes = sorted(_screen(region, exchanges, 250),
                        key=lambda x: (-(x.get("marketCap") or 0), len(x.get("symbol") or "")))
        kept = 0
        for x in quotes:
            name = (x.get("longName") or x.get("shortName") or "").strip()
            sym = x.get("symbol") or ""
            if (x.get("quoteType") != "EQUITY" or x.get("currency") not in currencies or not name
                    or _JUNK.search(name) or _JUNK.search(x.get("shortName") or "")
                    or (reporting and x.get("financialCurrency") != reporting)):
                continue
            key = company_key(name)
            if not key or key in seen or sym.split(".")[0] in us_tickers:  # autre classe ou double cotation
                continue
            seen.add(key)
            if region == "ch":  # lignes secondaires de la Bourse suisse (NOVNEE, ABBNE) → ligne principale
                sym = re.sub(r"(N)E{1,2}\.SW$", r"\1.SW", sym)
            members.append({"symbol": sym, "name": name, "region": region, "zone": zone,
                            "currency": x["currency"], "type": "ACTION"})
            kept += 1
            if kept >= quota:
                break
        time.sleep(1)
    members += crypto_members()
    if len(members) < 400:
        raise RuntimeError(f"Composition incomplète ({len(members)} titres)")
    return members


def crypto_members() -> list[dict]:
    return [{"symbol": f"{c}-EUR", "name": CRYPTO_NAMES[c], "region": "crypto", "zone": "crypto",
             "currency": "EUR", "type": "CRYPTO"} for c in CRYPTOS]


def load_snapshot() -> list[dict]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["members"]


def members(live: bool = True) -> list[dict]:
    if live:
        try:
            return build_live()
        except Exception as exc:
            logger.warning("Composition mondiale : liste de référence utilisée (%s)", exc)
    return load_snapshot()


# ── Heures d'ouverture (heure de Bruxelles, marges incluses) ────────────────
ZONE_HOURS = {
    "asia": (0, 0, 10, 30),       # Tokyo, Hong Kong, Sydney, Singapour
    "europe": (8, 45, 18, 0),
    "americas": (14, 15, 22, 30),  # New York, Toronto (décalages d'heure d'été inclus)
}


def open_zones(now: datetime | None = None) -> set[str]:
    now = now or datetime.now(ZoneInfo("Europe/Brussels"))
    zones = {"crypto"}
    if now.weekday() < 5:
        minutes = now.hour * 60 + now.minute
        for zone, (h1, m1, h2, m2) in ZONE_HOURS.items():
            if h1 * 60 + m1 <= minutes <= h2 * 60 + m2:
                zones.add(zone)
    return zones
