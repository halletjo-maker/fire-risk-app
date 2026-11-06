"""Portefeuille fictif de turbos Call open-end (sans date limite), simulés à partir du sous-jacent.

Règles retenues en novembre 2026 après un test sur 10 ans (~100 grandes actions et 5 indices,
2016-2026) : les turbos Call seuls, levier 2, stop suiveur de 15 % sur le sous-jacent, ont rapporté
≈ +20 %/an avec une pire chute de −41 % ; ajouter des Put, même seulement sur les indices, faisait
tomber le résultat à ≈ +8 %/an pour une pire chute de −65 %. Biais : sociétés qui ont réussi,
marché surtout haussier, turbos simulés.

Modèle d'un turbo Call open-end (type « BEST », barrière = niveau de financement) :
- niveau de financement à l'achat F = cours × (1 − 1/levier) : levier 2 → F = la moitié du cours ;
- F monte chaque jour avec le coût de financement (≈ 3 %/an, hypothèse) ;
- prix du turbo (parité 1, en devise du sous-jacent) = cours du sous-jacent − F ;
- si le sous-jacent touche F, le turbo est désactivé et ne vaut plus rien (knock-out).
Frais : 1 € par ordre (turbos Saxo), TOB 0,35 %, plus un écart achat/vente de l'émetteur de 0,25 %.

Règles :
- Achat : même signal que les actions (🟢 ACHAT au-dessus de la MM200, meilleur score d'abord),
  filtre de marché (pas d'achat quand le MSCI World est sous sa MM100), au plus `max_positions` lignes.
- Vente : sous-jacent 15 % sous son plus haut depuis l'achat, tendance de fond baissière (sous une
  MM200 qui baisse), ou barrière touchée.
Aucun ordre réel n'est passé : c'est une simulation.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .costs import order_cost

LEVERAGE = 2.0
FINANCING = 0.03      # coût de financement annuel (hypothèse : taux + marge de l'émetteur)
SPREAD = 0.0025       # écart achat/vente de l'émetteur, par opération (hypothèse)
TRAIL_PCT = 15.0      # stop suiveur sur le sous-jacent
MIN_ORDER_EUR = 50.0


def _days_since(sql_ts: str | None) -> float:
    if not sql_ts:
        return 0.0
    t = datetime.fromisoformat(sql_ts.replace(" ", "T"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 86400)


def financing_level(pos: dict) -> float:
    """Niveau de financement (= barrière) aujourd'hui : il monte avec le coût de financement."""
    return pos["financing"] * (1 + FINANCING * _days_since(pos.get("entry_at")) / 365)


def price(underlying: float, level: float) -> float:
    """Prix d'un turbo Call (parité 1) : valeur intrinsèque, jamais négative."""
    return max(0.0, underlying - level)


def buy(budget_eur: float, underlying: float, fx: float, leverage: float = LEVERAGE) -> dict:
    """Achat pour `budget_eur` (frais compris). Renvoie quantité, prix, barrière et frais en €."""
    f = order_cost(budget_eur, "EUR", "TURBO")
    spread = (budget_eur - f) * SPREAD
    level = underlying * (1 - 1 / leverage)
    unit = underlying - level
    qty = round((budget_eur - f - spread) * fx / unit, 4)
    return {"qty": qty, "price": unit, "financing": level, "fee": round(f + spread, 2),
            "cost": round(qty * unit / fx + f + spread, 2)}


def sell_fee(gross_eur: float) -> float:
    """Frais de vente en € : écart de l'émetteur + 1 € + TOB."""
    if gross_eur <= 0:
        return 0.0
    spread = gross_eur * SPREAD
    return round(spread + order_cost(gross_eur - spread, "EUR", "TURBO"), 2)
