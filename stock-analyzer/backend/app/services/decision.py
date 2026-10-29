"""Module 6 — Décision par onglets ACHAT / VENTE.

Score global = Fondamental × 0,35 + Technique × 0,45 + Sentiment × 0,20
    ≥ 7,5      → ✅ CONDITIONS FAVORABLES
    5 à 7,4    → ⚠️ PRUDENCE
    < 5        → ❌ CONDITIONS DÉFAVORABLES (+ avertissement fort)

Onglet VENTE (pour qui détient déjà le produit) : score de vente = 10 − score global,
mêmes seuils. Si une analyse n'est pas applicable (ex. fondamental d'un indice), les
poids des autres sont répartis à proportion et l'interface le signale.
"""
from __future__ import annotations

WEIGHTS = {"fundamental": 0.35, "technical": 0.45, "sentiment": 0.20}
LABELS = {"fundamental": "Fondamental", "technical": "Technique", "sentiment": "Sentiment"}
FAVORABLE, CAUTION = 7.5, 5.0

LEVELS = {
    "FAVORABLE": {"icon": "✅", "label": "CONDITIONS FAVORABLES"},
    "PRUDENCE": {"icon": "⚠️", "label": "PRUDENCE"},
    "DEFAVORABLE": {"icon": "❌", "label": "CONDITIONS DÉFAVORABLES"},
}


def _labels(lvl: str, suffix: str) -> dict:
    base = LEVELS[lvl]
    label = base["label"] if lvl == "PRUDENCE" else f"{base['label']} {suffix}"
    return {"icon": base["icon"], "label": label}


def level(score: float) -> str:
    return "FAVORABLE" if score >= FAVORABLE else "PRUDENCE" if score >= CAUTION else "DEFAVORABLE"


def signal(score: float | None) -> str | None:
    """Pastille des watchlists : 🟢 ACHAT · 🟡 NEUTRE · 🔴 VENTE."""
    if score is None:
        return None
    return "ACHAT" if score >= FAVORABLE else "VENTE" if score < CAUTION else "NEUTRE"


def _r(x: float) -> float:
    return round(x + 1e-9, 1)


# ---------------------------------------------------------------- phrases
FUNDAMENTAL_PHRASES = {
    # (bon, moyen, faible) selon la nature du produit
    "stock": ("fondamentaux solides", "fondamentaux corrects", "fondamentaux fragiles"),
    "etf": ("ETF de qualité (frais, taille, diversification)", "ETF de qualité moyenne", "ETF peu attractif (frais, taille ou levier)"),
    "derivative": ("produit peu risqué (barrière éloignée, levier modéré)", "produit au risque moyen",
                   "produit risqué (barrière proche, levier élevé ou spread important)"),
    "crypto": ("crypto majeure et liquide", "crypto de taille moyenne", "crypto petite ou peu liquide"),
}


def _fundamental_kind(fundamental: dict | None) -> str:
    keys = {c.get("key") for c in (fundamental or {}).get("criteria", [])}
    if "ter" in keys:
        return "etf"
    if keys & {"barrier", "leverage", "spread"}:
        return "derivative"
    if "mcap" in keys:
        return "crypto"
    return "stock"


def _fundamental_phrase(score: float, kind: str = "stock") -> tuple[str, int]:
    good, mid, bad = FUNDAMENTAL_PHRASES[kind]
    if score >= 7.5:
        return good, 1
    if score >= 5:
        return mid, 0
    return bad, -1


def _technical_phrase(score: float, mm: dict | None, inverse: bool) -> tuple[str, int]:
    tone = 1 if score >= 6 else -1 if score < 4.5 else 0
    if inverse:
        return ("sous-jacent orienté à la baisse, favorable au put" if tone > 0 else
                "sous-jacent orienté à la hausse, défavorable au put" if tone < 0 else
                "tendance du sous-jacent indécise"), tone
    if mm:
        if mm.get("cross"):
            up = mm["cross"]["direction"] == "HAUSSIER"
            return ("retournement haussier récent (le prix vient de repasser au-dessus de la MM100)" if up else
                    "cassure récente de la MM100 à la baisse"), (1 if up else -1)
        if mm.get("above"):
            return "tendance de fond haussière (prix au-dessus de la MM100)", max(tone, 0) or 1
        return "tendance de fond baissière (prix sous la MM100)", min(tone, 0) or -1
    return ("signaux techniques positifs" if tone > 0 else "signaux techniques négatifs" if tone < 0 else
            "signaux techniques mitigés"), tone


def _sentiment_phrase(score: float) -> tuple[str, int]:
    if score >= 6:
        return "actualité favorable", 1
    if score <= 4:
        return "actualité défavorable", -1
    return "actualité neutre", 0


# ---------------------------------------------------------------- calcul
def compute(fundamental: dict | None, technical: dict | None, sentiment: dict | None) -> dict:
    parts = {"fundamental": fundamental, "technical": technical, "sentiment": sentiment}
    scores = {k: (v or {}).get("score") for k, v in parts.items()}
    available = {k: s for k, s in scores.items() if s is not None}
    if not available:
        return {"available": False, "message": "Aucune analyse disponible pour calculer une décision."}

    total_w = sum(WEIGHTS[k] for k in available)
    components = []
    for k in WEIGHTS:
        s = scores[k]
        w = WEIGHTS[k] / total_w if s is not None else 0
        components.append({
            "key": k, "label": LABELS[k], "score": s,
            "weight": round(w, 3), "nominal_weight": WEIGHTS[k],
            "contribution": round(s * w, 2) if s is not None else None,
        })
    global_score = _r(sum(c["contribution"] for c in components if c["contribution"] is not None))
    missing = [LABELS[k] for k in WEIGHTS if scores[k] is None]

    # Points d'appui / de vigilance (lecture « achat »)
    mm = (technical or {}).get("mm100")
    inverse = bool((technical or {}).get("inverse"))
    phrases = []
    if scores["technical"] is not None:
        phrases.append(_technical_phrase(scores["technical"], mm, inverse))
    if scores["fundamental"] is not None:
        phrases.append(_fundamental_phrase(scores["fundamental"], _fundamental_kind(fundamental)))
    if scores["sentiment"] is not None:
        phrases.append(_sentiment_phrase(scores["sentiment"]))
    pros = [p for p, tone in phrases if tone > 0]
    cons = [p for p, tone in phrases if tone < 0]
    neutral = [p for p, tone in phrases if tone == 0]

    notes = []
    if missing:
        notes.append(f"Non applicable : {', '.join(missing)}. Poids répartis sur les autres analyses.")
    f, t = scores["fundamental"], scores["technical"]
    if f is not None and t is not None and abs(f - t) >= 3:
        fs, ts = f"{f:.1f}".replace(".", ","), f"{t:.1f}".replace(".", ",")
        notes.append(
            f"Fondamentaux ({fs}/10) et tendance ({ts}/10) divergent : "
            + ("le marché sanctionne la valeur malgré ses fondamentaux — attendre un retour au-dessus "
               "de la MM100 avant d'acheter." if f > t else
               "le cours monte plus vite que ne le justifient les fondamentaux — mouvement possiblement spéculatif.")
        )
    events = (sentiment or {}).get("events") or []
    if any(e.get("type") == "Earnings Date" and e.get("days", 99) <= 2 for e in events):
        notes.append("Résultats trimestriels dans moins de 48 h : le cours peut fortement bouger.")

    buy_level = level(global_score)
    sell_score = _r(10 - global_score)
    sell_level = level(sell_score)

    buy_summary = {
        "FAVORABLE": "Les analyses convergent : le contexte est favorable à un achat.",
        "PRUDENCE": "Le contexte est mitigé : acheter éventuellement par petites tranches, avec un stop-loss.",
        "DEFAVORABLE": "Le contexte est défavorable : un achat maintenant irait à contre-courant.",
    }[buy_level]
    sell_summary = {
        "FAVORABLE": "Les signaux de faiblesse dominent : alléger ou vendre la position est cohérent.",
        "PRUDENCE": "Signaux partagés : conserver mais protéger la position par un stop-loss.",
        "DEFAVORABLE": "Pas de raison technique ni fondamentale de vendre : la position peut être conservée.",
    }[sell_level]
    buy_warning = None
    if buy_level == "DEFAVORABLE":
        buy_warning = (
            "⚠️ AVERTISSEMENT : score global inférieur à 5/10. Acheter maintenant expose à un risque "
            "de perte élevé. Si vous décidez malgré tout d'investir, limitez la taille de la position "
            "et placez un stop-loss dès l'achat."
        )

    return {
        "available": True,
        "score": global_score,
        "components": components,
        "missing": missing,
        "signal": signal(global_score),
        "buy": {"score": global_score, "level": buy_level, **_labels(buy_level, "À L'ACHAT"),
                "summary": buy_summary, "warning": buy_warning, "pros": pros, "cons": cons, "neutral": neutral},
        "sell": {"score": sell_score, "level": sell_level, **_labels(sell_level, "À LA VENTE"),
                 "summary": sell_summary, "pros": cons, "cons": pros, "neutral": neutral},
        "notes": notes,
        "thresholds": {"favorable": FAVORABLE, "caution": CAUTION},
    }
