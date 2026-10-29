"""Enchaînement complet d'une analyse (réutilisé par l'API, les watchlists et les alertes)."""
from __future__ import annotations

from . import decision, fundamentals, market, sentiment, technical


def sentiment_for(data: dict) -> dict:
    """Actualités adaptées au produit : indice d'un ETF, sous-jacent d'un turbo…"""
    product, derivative = data["product"], data.get("derivative")
    extra, events_symbol = None, None
    if product["type"] == "ETF":
        f = fundamentals.analyze(product, data["quote"])
        extra = {"index": next((i["display"] for i in f.get("info", []) if i["label"] == "Indice suivi"), None)}
    elif product["type"] in ("TURBO", "WARRANT") and derivative:
        under = technical._underlying_product(derivative)
        events_symbol = under["symbol"] if under and under["id"].startswith("yf:") else None
    elif product["id"].startswith("yf:") and product["type"] == "ACTION":
        events_symbol = product["id"][3:]
    return sentiment.analyze(product, derivative, extra, events_symbol)


def run(product_id: str, isin: str | None = None) -> dict | None:
    """Analyse complète d'un produit. Chaque étape est mise en cache par son module."""
    data = market.get_quote(product_id, isin=isin)
    if data is None:
        return None
    product, quote, derivative = data["product"], data["quote"], data.get("derivative")
    f = fundamentals.analyze(product, quote, derivative)
    t = technical.analyze(product, quote, derivative)
    s = sentiment_for(data)
    return {
        "product": product,
        "quote": quote,
        "derivative": derivative,
        "fundamentals": f,
        "technical": t,
        "sentiment": s,
        "decision": decision.compute(f, t, s),
    }
