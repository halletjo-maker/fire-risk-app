"""Module 2 — recherche, cours et (premier niveau d') analyse d'un produit."""
from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Query

from ..database import get_conn
from ..services import fundamentals as fundamentals_service
from ..services import market
from ..services import sentiment as sentiment_service
from ..services import technical as technical_service

router = APIRouter(tags=["analyse"])


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=80, description="Nom, ticker, ISIN ou mot-clé")) -> dict:
    """Propositions de produits (autocomplétion)."""
    return market.search(q)


@router.get("/quote")
def quote(
    id: str = Query(..., description="Identifiant renvoyé par /search (ex. yf:NOW)"),
    isin: str | None = None,
) -> dict:
    data = market.get_quote(id, isin=isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Cours indisponible sur toutes les sources")
    return data


@router.get("/analyze")
def analyze(
    q: str = Query(..., min_length=1, max_length=80, description="Nom, ticker, ISIN ou mot-clé"),
    id: str | None = Query(None, description="Produit précis choisi dans les propositions"),
    isin: str | None = None,
    x_user_email: str | None = Header(default=None),
) -> dict:
    result = market.analyze(q.strip(), product_id=id, isin=isin)
    if result["status"] == "ok":
        _save_history(x_user_email, q.strip(), result)
    return result


def _save_history(email: str | None, query: str, result: dict) -> None:
    product, quote = result["product"], result["quote"]
    with get_conn() as conn:
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email or "",)).fetchone()
        conn.execute(
            "INSERT INTO analysis_history (user_id, query, symbol, name, product_type, price, sources) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user["id"] if user else None,
                query,
                product.get("symbol") or product.get("isin"),
                product.get("name"),
                product.get("type"),
                quote.get("price"),
                json.dumps(result.get("sources", [])),
            ),
        )


@router.get("/fundamentals")
def fundamentals(
    id: str = Query(..., description="Identifiant renvoyé par /search ou /analyze"),
    isin: str | None = None,
) -> dict:
    """Module 3 — analyse fondamentale adaptée au type de produit (score /10)."""
    data = market.get_quote(id, isin=isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Produit indisponible sur toutes les sources")
    return {
        "product": data["product"],
        "fundamentals": fundamentals_service.analyze(data["product"], data["quote"], data.get("derivative")),
    }


@router.get("/technical")
def technical(
    id: str = Query(..., description="Identifiant renvoyé par /search ou /analyze"),
    isin: str | None = None,
) -> dict:
    """Module 4 — analyse technique (MM100 en critère principal) + données du graphique."""
    data = market.get_quote(id, isin=isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Produit indisponible sur toutes les sources")
    return {
        "product": data["product"],
        "technical": technical_service.analyze(data["product"], data["quote"], data.get("derivative")),
    }


@router.get("/sentiment")
def sentiment(
    id: str = Query(..., description="Identifiant renvoyé par /search ou /analyze"),
    isin: str | None = None,
) -> dict:
    """Module 5 — actualités (72 h), sentiment par titre, événements à venir, score /10."""
    data = market.get_quote(id, isin=isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Produit indisponible sur toutes les sources")
    product, derivative = data["product"], data.get("derivative")
    extra, events_symbol = None, None
    if product["type"] == "ETF":  # l'actualité d'un ETF = celle de son indice
        f = fundamentals_service.analyze(product, data["quote"])
        extra = {"index": next((i["display"] for i in f.get("info", []) if i["label"] == "Indice suivi"), None)}
    elif product["type"] in ("TURBO", "WARRANT") and derivative:
        under = technical_service._underlying_product(derivative)
        events_symbol = under["symbol"] if under and under["id"].startswith("yf:") else None
    elif id.startswith("yf:") and product["type"] == "ACTION":
        events_symbol = id[3:]
    return {
        "product": product,
        "sentiment": sentiment_service.analyze(product, derivative, extra, events_symbol),
    }
