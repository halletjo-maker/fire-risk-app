"""Frais réels d'un ordre chez Saxo Banque (niveau Bronze, tarifs du 1er octobre 2025) + TOB belge.

- Courtage actions/ETF : 0,08 % avec un minimum selon la Bourse (2 € Euronext, 3 € Xetra et Milan,
  0,12 % min. 5 € Madrid/Dublin/Vienne, 1 $ aux États-Unis…). Minimums en devise convertis ici en euros
  approximatifs (ce sont de petits montants).
- Turbos Saxo : 1 € par ordre (9 € pour les turbos d'autres émetteurs).
- Change : 0,25 % pour un titre en devise étrangère.
- TOB : 0,35 % (actions, turbos, plafond 1 600 €), 0,12 % (ETF, plafond 1 300 €). Hypothèse : ETF non
  enregistrés en Belgique en capitalisation (sinon 1,32 %) ; cryptos via ETN : 0,35 %.
"""
from __future__ import annotations

COURTAGE = 0.0008
FX = 0.0025
MIN_EUR = {"EUR": 2.0, "USD": 0.9, "GBP": 3.5, "GBp": 3.5, "GBX": 3.5, "CHF": 3.2, "JPY": 5.0, "HKD": 1.8,
           "AUD": 1.8, "CAD": 3.4, "SEK": 0.9, "DKK": 1.35, "NOK": 0.85, "SGD": 2.1}
PLACES_12 = (".MC", ".IR", ".VI")             # Madrid, Dublin, Vienne : 0,12 % min. 5 €
PLACES_MIN3 = (".DE", ".F", ".MI", ".HE")      # Xetra/Francfort, Milan, Helsinki : min. 3 € (Francfort 5 €)
TURBO_SAXO = 1.0
TOB = {"ACTION": (0.0035, 1600.0), "ETF": (0.0012, 1300.0), "TURBO": (0.0035, 1600.0),
       "WARRANT": (0.0035, 1600.0), "CRYPTO": (0.0035, 1600.0)}


def order_cost(amount_eur: float, currency: str | None = "EUR", product_type: str | None = "ACTION",
               symbol: str | None = None) -> float:
    """Frais totaux en euros d'un ordre d'achat ou de vente de `amount_eur`."""
    kind = (product_type or "ACTION").upper()
    ccy = currency or "EUR"
    sym = (symbol or "").upper()
    if kind in ("TURBO", "WARRANT"):
        courtage = TURBO_SAXO
    else:
        rate, minimum = COURTAGE, MIN_EUR.get(ccy, 3.0)
        if sym.endswith(PLACES_12):
            rate, minimum = 0.0012, 5.0
        elif sym.endswith(".F"):
            minimum = 5.0
        elif sym.endswith(PLACES_MIN3):
            minimum = 3.0
        courtage = max(minimum, amount_eur * rate)
    fx = amount_eur * FX if ccy.upper() not in ("EUR",) else 0.0
    tob_rate, cap = TOB.get(kind, TOB["ACTION"])
    tob = min(cap, amount_eur * tob_rate)
    return round(courtage + fx + tob, 2)
