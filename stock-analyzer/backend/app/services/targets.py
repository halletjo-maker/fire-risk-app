"""Cours d'achat et de vente potentiels d'un produit (affichés dans les watchlists).

Règles simples, lisibles et fondées sur l'analyse technique (MM100 = critère principal) :
- Tendance haussière (cours au-dessus de la MM100) : achat sur repli vers le plus proche
  appui sous le cours (support ou MM100). Si le cours y est déjà (moins de 1,5 %) : achat ≈ cours.
- Tendance baissière (cours sous la MM100) : achat seulement après un retour au-dessus
  de la MM100 (seuil = MM100 + 1 % pour confirmer).
- Vente potentielle (objectif) : la prochaine résistance si elle laisse au moins 2 % de marge,
  sinon un objectif tiré de la volatilité (3 × la variation moyenne quotidienne, 5 % minimum).
- Stop-loss : 1 % sous le support s'il est entre −3 % et −12 %, sinon 2 × la volatilité
  quotidienne (entre −3 % et −12 %, −8 % sans historique).
Non calculé pour les turbos et warrants (le levier et la barrière changent tout).
"""
from __future__ import annotations

NEAR_PCT = 1.5        # écart sous lequel on considère la zone d'achat atteinte
CONFIRM_PCT = 1.0     # marge au-dessus de la MM100 pour confirmer un retour haussier
MIN_MARGIN_PCT = 2.0  # marge minimale entre l'achat et une résistance
MIN_TARGET_PCT = 5.0
STOP_MIN_PCT, STOP_MAX_PCT = 3.0, 12.0  # stop entre −3 % et −12 % du cours d'achat


def rnd(x: float) -> float:
    """Arrondi lisible qui garde les très petits prix (ex. 0,000004 € pour certaines cryptos)."""
    return round(x, 4) if abs(x) >= 1 else float(f"{x:.6g}")


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
    atr = _atr_pct(t.get("chart") or [])
    if resistance and resistance > ref * (1 + MIN_MARGIN_PCT / 100):
        sell, sell_note = resistance, "Objectif : la prochaine résistance"
    else:
        gain = max(MIN_TARGET_PCT, 3 * atr) if atr else 8.0
        sell, sell_note = ref * (1 + gain / 100), f"Objectif estimé d'après la volatilité (+{gain:.0f} %)"

    # ── Stop-loss (sous le cours d'achat) ──────────────────────────────────
    stop_pct = min(STOP_MAX_PCT, max(STOP_MIN_PCT, 2 * atr)) if atr else 8.0
    sup_stop = support * 0.99 if support and support < ref else None
    if sup_stop and STOP_MIN_PCT <= (1 - sup_stop / ref) * 100 <= STOP_MAX_PCT:
        stop, stop_note = sup_stop, "Stop 1 % sous le support"
    else:
        stop, stop_note = ref * (1 - stop_pct / 100), f"Stop à −{stop_pct:.0f} % (selon la volatilité)"

    return {
        "buy_price": rnd(buy), "buy_kind": kind, "buy_note": buy_note,
        "sell_price": rnd(sell), "sell_note": sell_note,
        "stop_price": rnd(stop), "stop_note": stop_note,
    }
