"""Cours d'achat et de vente potentiels d'un produit (affichés dans les watchlists).

Règles simples, lisibles et fondées sur l'analyse technique (MM100 = critère principal) :
- Tendance haussière (cours au-dessus de la MM100) : achat sur repli vers le plus proche
  appui sous le cours (support ou MM100). Si le cours y est déjà (moins de 1,5 %) : achat ≈ cours.
- Tendance baissière (cours sous la MM100) : achat seulement après un retour au-dessus
  de la MM100 (seuil = MM100 + 1 % pour confirmer).
- Vente potentielle (objectif) : la prochaine résistance si elle laisse au moins 2 % de marge,
  sinon un objectif tiré de la volatilité (3 × la variation moyenne quotidienne, 5 % minimum).
Non calculé pour les turbos et warrants (le levier et la barrière changent tout).
"""
from __future__ import annotations

NEAR_PCT = 1.5        # écart sous lequel on considère la zone d'achat atteinte
CONFIRM_PCT = 1.0     # marge au-dessus de la MM100 pour confirmer un retour haussier
MIN_MARGIN_PCT = 2.0  # marge minimale entre l'achat et une résistance
MIN_TARGET_PCT = 5.0


def _atr_pct(chart: list[dict], n: int = 14) -> float | None:
    from .report import _atr_pct  # import local : report importe beaucoup de sources

    return _atr_pct(chart, n)


def compute(full: dict) -> dict | None:
    p, q, t = full.get("product") or {}, full.get("quote") or {}, full.get("technical") or {}
    price = q.get("price")
    if p.get("type") in ("TURBO", "WARRANT") or not price or not t.get("applicable"):
        return None
    levels, mm = t.get("levels") or {}, t.get("mm100") or {}
    support, resistance, m100 = levels.get("support"), levels.get("resistance"), mm.get("value")
    above = mm.get("above") if mm else None

    # ── Achat ──────────────────────────────────────────────────────────────
    if above is False and m100:
        buy, kind = m100 * (1 + CONFIRM_PCT / 100), "≥"
        buy_note = "Achat si le cours repasse au-dessus de la MM100 (tendance redevenue haussière)"
    else:
        floors = [(v, n) for v, n in ((m100, "la MM100"), (support, "le support")) if v and v < price]
        if floors:
            buy, name = max(floors)
            kind = "≤"
            buy_note = f"Achat sur repli vers {name}"
            if (price - buy) / price * 100 < NEAR_PCT:
                buy, kind = price, "≈"
                buy_note = f"Zone d'achat atteinte : le cours est proche de {name}"
        else:
            buy, kind, buy_note = price, "≈", "Pas d'appui identifié sous le cours : achat au cours actuel"

    # ── Vente (objectif) ───────────────────────────────────────────────────
    ref = max(price, buy)
    if resistance and resistance > ref * (1 + MIN_MARGIN_PCT / 100):
        sell, sell_note = resistance, "Objectif : la prochaine résistance"
    else:
        atr = _atr_pct(t.get("chart") or [])
        gain = max(MIN_TARGET_PCT, 3 * atr) if atr else 8.0
        sell, sell_note = ref * (1 + gain / 100), f"Objectif estimé d'après la volatilité (+{gain:.0f} %)"

    return {
        "buy_price": round(buy, 4), "buy_kind": kind, "buy_note": buy_note,
        "sell_price": round(sell, 4), "sell_note": sell_note,
    }
