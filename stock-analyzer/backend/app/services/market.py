"""Module 2 — identification d'un produit et récupération de son cours.

Ordre des sources (fallback automatique et silencieux) :
    1. Yahoo Finance   (actions, ETF, crypto, indices)
    2. Google Finance  (secours pour le prix et la variation)
    3. Boursorama      (turbos, warrants, et dernier secours)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from .sources import boursorama, cache, google_finance, yahoo

logger = logging.getLogger(__name__)

SEARCH_TTL = 30 * 60  # 30 min
QUOTE_TTL = 60  # 1 min

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
TICKER_RE = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-=]{0,11}$")
DERIVATIVE_WORDS = {"turbo", "turbos", "warrant", "warrants", "mini", "call", "put", "bonus", "certificat"}

TYPE_LABELS = {
    "ACTION": "Action",
    "ETF": "ETF",
    "TURBO": "Turbo",
    "WARRANT": "Warrant",
    "CRYPTO": "Crypto",
    "INDICE": "Indice",
    "AUTRE": "Autre",
}


# ---------------------------------------------------------------- identification
def is_valid_isin(code: str) -> bool:
    """Format + clé de contrôle (algorithme de Luhn sur les lettres converties)."""
    code = code.upper()
    if not ISIN_RE.match(code):
        return False
    digits = "".join(str(int(c, 36)) for c in code[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(code[-1])


def query_kind(query: str) -> str:
    """'isin' | 'ticker' | 'nom' — indicatif, affiché dans l'interface."""
    q = query.strip()
    if is_valid_isin(q.upper()):
        return "isin"
    if ISIN_RE.match(q.upper()):  # forme d'ISIN mais clé de contrôle fausse
        return "nom"
    if " " not in q and TICKER_RE.match(q.upper()) and (q.isupper() or len(q) <= 5 or "." in q or q.startswith("^")):
        return "ticker"
    return "nom"


def _wants_derivatives(query: str) -> bool:
    return bool(set(query.lower().split()) & DERIVATIVE_WORDS)


# ---------------------------------------------------------------- recherche
def search(query: str, limit: int = 8) -> dict:
    query = " ".join(query.split())
    kind = query_kind(query)
    key = f"search:{query.lower()}"
    cached = cache.get(key, SEARCH_TTL)
    if cached:
        return cached

    sources: list[dict] = []
    derivatives = _wants_derivatives(query)
    yf_results: list[dict] = []
    if not derivatives:
        yf_results = yahoo.search(query.upper() if kind == "isin" else query, limit=limit)
        sources.append({"name": yahoo.SOURCE, "ok": bool(yf_results)})
        if kind == "isin":
            for c in yf_results[:1]:
                c["isin"] = query.upper()
        yf_results = _prefer_euro_crypto(yf_results)

    bo_results: list[dict] = []
    if derivatives or not yf_results:
        bo_results = boursorama.search(query.upper() if kind == "isin" else query, limit=limit)
        sources.append({"name": boursorama.SOURCE, "ok": bool(bo_results)})
        if yf_results:  # éviter les doublons d'actions déjà trouvées sur Yahoo
            known = {c["symbol"].split(".")[0].upper() for c in yf_results}
            bo_results = [
                c for c in bo_results
                if c["type"] in {"TURBO", "WARRANT", "AUTRE"} or (c.get("symbol") or "").upper() not in known
            ]

    if derivatives:  # « turbo lvmh » : les turbos / warrants d'abord
        bo_results.sort(key=lambda c: c["type"] not in {"TURBO", "WARRANT"})
    candidates = (bo_results + yf_results) if derivatives else (yf_results + bo_results)
    for c in candidates:
        c["type_label"] = TYPE_LABELS.get(c["type"], c["type"])
    result = {"query": query, "query_kind": kind, "candidates": candidates[:limit], "sources": sources}
    if candidates:
        cache.put(key, result, source="+".join(s["name"] for s in sources if s["ok"]))
    return result


def _prefer_euro_crypto(results: list[dict]) -> list[dict]:
    """Crypto cotée en USD → propose d'abord la paire en EUR (BTC-USD → BTC-EUR)."""
    out: list[dict] = []
    symbols = {c["symbol"] for c in results}
    for c in results:
        if c["type"] == "CRYPTO" and c["symbol"].endswith("-USD"):
            eur = c["symbol"][:-4] + "-EUR"
            if eur not in symbols:
                out.append({**c, "id": f"yf:{eur}", "symbol": eur,
                            "name": re.sub(r"\bUSD\b", "EUR", c["name"])})
                symbols.add(eur)
        out.append(c)
    return out


# ---------------------------------------------------------------- cours
def get_quote(product_id: str, isin: str | None = None) -> dict | None:
    """Cours d'un produit identifié par 'yf:SYMBOLE' ou 'bo:/chemin/boursorama'."""
    key = f"quote:{product_id}"
    cached = cache.get(key, QUOTE_TTL)
    if cached:
        return cached

    tried: list[dict] = []
    data = None
    if product_id.startswith("yf:"):
        symbol = product_id[3:]
        data = yahoo.quote(symbol)
        tried.append({"name": yahoo.SOURCE, "ok": data is not None})
        if data is None:
            data = google_finance.quote(symbol)
            tried.append({"name": google_finance.SOURCE, "ok": data is not None})
            if data:
                data["type"] = data.get("type") or _type_from_symbol(symbol)
        if data is None:
            data = _boursorama_fallback(symbol)
            tried.append({"name": boursorama.SOURCE, "ok": data is not None})
    elif product_id.startswith("bo:"):
        data = boursorama.quote(product_id[3:])
        tried.append({"name": boursorama.SOURCE, "ok": data is not None})
    else:
        return None

    if data is None:
        return None

    derivative = data.pop("derivative", None)
    data.pop("exchange_code", None)
    data["isin"] = data.get("isin") or isin
    data["type"] = data.get("type") or "AUTRE"
    data["type_label"] = TYPE_LABELS.get(data["type"], data["type"])
    data["id"] = product_id
    source = data.pop("source")
    result = {
        "product": {k: data.get(k) for k in ("id", "symbol", "isin", "name", "type", "type_label", "exchange", "currency")},
        "quote": {k: data.get(k) for k in ("price", "prev_close", "change", "change_pct", "volume", "time")},
        "derivative": derivative,
        "source": source,
        "sources": tried,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    cache.put(key, result, source=source)
    return result


def _type_from_symbol(symbol: str) -> str:
    if symbol.startswith("^"):
        return "INDICE"
    if re.search(r"-(USD|EUR|GBP|CHF)$", symbol):
        return "CRYPTO"
    return "ACTION"


def _boursorama_fallback(symbol: str) -> dict | None:
    """Dernier recours : retrouve le produit sur Boursorama via son code."""
    base = symbol.split(".")[0].lstrip("^")
    for c in boursorama.search(base, limit=5):
        if (c.get("symbol") or "").upper() == base.upper():
            data = boursorama.quote(c["id"][3:])
            if data:
                data["symbol"] = symbol
                data["exchange"] = data.get("exchange") or c.get("exchange")
                return data
    return None


# ---------------------------------------------------------------- analyse (Module 2)
def analyze(query: str, product_id: str | None = None, isin: str | None = None) -> dict:
    """Identifie le produit puis récupère son cours. Les scores arrivent aux Modules 3 à 6."""
    found = search(query) if not product_id else None
    if found is not None:
        if not found["candidates"]:
            return {
                "query": query,
                "query_kind": query_kind(query),
                "status": "not_found",
                "message": "Aucun produit trouvé. Essaie le ticker (ex. NOW), le code ISIN ou le nom complet.",
                "sources": found["sources"],
            }
        best = found["candidates"][0]
        product_id, isin = best["id"], best.get("isin")

    data = get_quote(product_id, isin=isin)
    if data is None:
        return {
            "query": query,
            "query_kind": query_kind(query),
            "status": "unavailable",
            "message": "Produit trouvé mais cours indisponible sur toutes les sources pour le moment.",
            "sources": [],
        }
    return {
        "query": query,
        "query_kind": query_kind(query),
        "status": "ok",
        "message": "Scores et recommandation disponibles à partir des Modules 3 à 6.",
        **data,
        "alternatives": [c for c in (found or {}).get("candidates", [])[1:6]],
        "scores": None,
    }
