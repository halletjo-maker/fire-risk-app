"""Analyse d'un produit — squelette, rempli à partir du Module 2."""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(tags=["analyse"])


@router.get("/analyze")
def analyze(q: str = Query(..., min_length=1, description="Nom, ticker, ISIN ou mot-clé")) -> dict:
    return {
        "query": q.strip(),
        "status": "not_implemented",
        "message": "L'analyse sera disponible à partir du Module 2.",
        "product": None,
        "scores": None,
        "sources": [],
    }
