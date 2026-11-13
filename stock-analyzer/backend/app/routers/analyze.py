"""Module 2 — recherche, cours et (premier niveau d') analyse d'un produit."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_conn
from ..deps import current_user
from ..services import analysis as analysis_service
from ..services import fundamentals as fundamentals_service
from ..services import market
from ..services import report as report_service
from ..services import technical as technical_service

router = APIRouter(tags=["analyse"], dependencies=[Depends(current_user)])


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
    user: dict = Depends(current_user),
) -> dict:
    result = market.analyze(q.strip(), product_id=id, isin=isin)
    if result["status"] == "ok":
        _save_history(user["id"], q.strip(), result)
    return result


def _save_history(uid: int, query: str, result: dict) -> None:
    product, quote = result["product"], result["quote"]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO analysis_history (user_id, query, symbol, name, product_type, price, sources) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uid,
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
    return {"product": data["product"], "sentiment": analysis_service.sentiment_for(data)}


@router.get("/decision")
def decision(
    id: str = Query(..., description="Identifiant renvoyé par /search ou /analyze"),
    isin: str | None = None,
    user: dict = Depends(current_user),
) -> dict:
    """Module 6 — score global et décision ACHAT / VENTE."""
    full = analysis_service.run(id, isin=isin)
    if full is None:
        raise HTTPException(status_code=503, detail="Produit indisponible sur toutes les sources")
    d = full["decision"]
    if d.get("available"):
        _save_scores(user["id"], full)
    return {"product": full["product"], "decision": d}


def _save_scores(uid: int, full: dict) -> None:
    """Complète la ligne d'historique de l'analyse (ou en crée une)."""
    product, d = full["product"], full["decision"]
    symbol = product.get("symbol") or product.get("isin")
    scores = {c["key"]: c["score"] for c in d["components"]}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM analysis_history WHERE user_id IS ? AND symbol IS ? "
            "AND created_at >= datetime('now', '-2 hours') ORDER BY id DESC LIMIT 1",
            (uid, symbol),
        ).fetchone()
        values = (scores["fundamental"], scores["technical"], scores["sentiment"], d["score"], d["buy"]["level"])
        if row:
            conn.execute(
                "UPDATE analysis_history SET score_fundamental = ?, score_technical = ?, score_sentiment = ?, "
                "score_global = ?, verdict = ? WHERE id = ?",
                (*values, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO analysis_history (user_id, query, symbol, name, product_type, price, "
                "score_fundamental, score_technical, score_sentiment, score_global, verdict) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uid, symbol or "", symbol, product.get("name"), product.get("type"),
                 full["quote"].get("price"), *values),
            )


@router.get("/report")
def report(
    id: str = Query(..., description="Identifiant renvoyé par /search ou /analyze"),
    isin: str | None = None,
) -> dict:
    """Module 7 — rapport justificatif (résumé, forces/faiblesses, MM100, stop-loss, alternatives)."""
    data = report_service.build(id, isin=isin)
    if data is None:
        raise HTTPException(status_code=503, detail="Produit indisponible sur toutes les sources")
    return data
