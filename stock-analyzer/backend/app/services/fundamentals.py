"""Module 3 — Analyse fondamentale adaptée au type de produit → score /10.

Chaque critère reçoit une note de 0 à 10 et un poids. Le score fondamental est la
moyenne pondérée des critères disponibles (un critère sans donnée est ignoré et
la couverture est indiquée). Les seuils sont volontairement simples et lisibles.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

from .sources import boursorama, cache, coingecko, google_finance, justetf, yahoo

logger = logging.getLogger(__name__)

CACHE_TTL = 6 * 3600  # les fondamentaux bougent peu

MAJOR_ISSUERS = (
    "SOCIETE GENERALE", "BNP", "VONTOBEL", "CITI", "UNICREDIT", "ING", "GOLDMAN",
    "MORGAN STANLEY", "HSBC", "COMMERZBANK", "DEUTSCHE BANK", "UBS", "J.P. MORGAN",
    "JP MORGAN", "BARCLAYS", "NATIXIS", "LEONTEQ", "DZ BANK", "SOCGEN",
)
LEVERAGED_ETF = re.compile(r"\b(\d(?:[.,]\d)?x|short|leveraged|lev|daily|bear|bull|inverse|ultra)\b", re.I)


# ---------------------------------------------------------------- outils
def tier(value: float, steps: list[tuple[float, float]], top: float) -> float:
    """Première note dont la borne est strictement supérieure à la valeur."""
    for limit, note in steps:
        if value < limit:
            return note
    return top


def num(v: float | None, d: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def pct(v: float | None, d: int = 1, sign: bool = False) -> str:
    if v is None:
        return "—"
    s = num(abs(v), d)
    prefix = "+" if sign and v > 0 else "−" if v < 0 else ""
    return f"{prefix}{s} %"


def big(v: float | None, currency: str | None = None) -> str:
    if v is None:
        return "—"
    cur = f" {currency}" if currency else ""
    if abs(v) >= 1e9:
        return f"{num(v / 1e9, 1)} Md{cur}"
    if abs(v) >= 1e6:
        return f"{num(v / 1e6, 1)} M{cur}"
    return f"{num(v, 0)}{cur}"


def crit(key, label, value, display, score, weight, comment, source=None) -> dict:
    return {
        "key": key, "label": label, "value": value, "display": display,
        "score": round(score, 1) if score is not None else None,
        "weight": weight, "comment": comment, "source": source,
    }


def first(*pairs):
    """Première valeur non nulle parmi (valeur, source)."""
    for value, source in pairs:
        if value is not None:
            return value, source
    return None, None


def verdict(score: float | None) -> str | None:
    if score is None:
        return None
    return "Solide" if score >= 7.5 else "Correct" if score >= 5 else "Fragile"


def finalize(criteria, info, sources, note=None, cap=None) -> dict:
    scored = [c for c in criteria if c["score"] is not None]
    total_w = sum(c["weight"] for c in scored)
    score = sum(c["score"] * c["weight"] for c in scored) / total_w if total_w else None
    if score is not None and cap is not None and score > cap:
        score = cap
    coverage = round(len(scored) / len(criteria), 2) if criteria else 0
    notes = [n for n in [note] if n]
    if criteria and coverage < 0.5:
        notes.append("Données partielles : score à prendre avec prudence.")
    return {
        "applicable": True,
        "score": round(score, 1) if score is not None else None,
        "verdict": verdict(score),
        "criteria": criteria,
        "info": [i for i in info if i.get("display") not in (None, "—", "")],
        "coverage": coverage,
        "sources": sources,
        "notes": notes,
    }


def not_applicable(message: str) -> dict:
    return {"applicable": False, "score": None, "verdict": None, "criteria": [], "info": [],
            "coverage": 0, "sources": [], "notes": [message]}


# ---------------------------------------------------------------- point d'entrée
def analyze(product: dict, quote: dict, derivative: dict | None = None) -> dict:
    key = f"fund:{product['id']}"
    cached = cache.get(key, CACHE_TTL)
    if cached:
        return cached
    kind = product.get("type")
    try:
        if kind == "ACTION":
            result = _stock(product, quote)
        elif kind == "ETF":
            result = _etf(product, quote)
        elif kind in ("TURBO", "WARRANT") and derivative:
            result = _derivative(product, derivative)
        elif kind == "CRYPTO":
            result = _crypto(product, quote)
        elif kind == "INDICE":
            result = not_applicable(
                "Pas d'analyse fondamentale pour un indice : le score global reposera sur "
                "l'analyse technique et le sentiment."
            )
        else:
            result = not_applicable(
                "Analyse fondamentale non disponible pour ce type de produit (certificat, fonds…)."
            )
    except Exception:
        logger.exception("Analyse fondamentale impossible pour %s", product.get("id"))
        result = not_applicable("Analyse fondamentale momentanément indisponible.")
    if result.get("applicable") and result.get("score") is not None:
        cache.put(key, result, source="fundamentals")
    return result


# ---------------------------------------------------------------- ACTION
def _stock(product: dict, quote: dict) -> dict:
    pid, price, cur = product["id"], quote.get("price"), product.get("currency")
    symbol = product.get("symbol") or ""
    sources = []

    y = yahoo.info(symbol) if pid.startswith("yf:") else None
    sources.append({"name": yahoo.SOURCE, "ok": y is not None})
    y = y or {}

    listing_path = pid[3:] if pid.startswith("bo:") else None
    if listing_path is None and symbol:
        listing = boursorama.find_listing(symbol)
        listing_path = listing["id"][3:] if listing else None
    c = boursorama.consensus(listing_path) if listing_path else None
    sources.append({"name": f"{boursorama.SOURCE} (consensus)", "ok": c is not None})
    c = c or {}

    g = {}
    if not y and pid.startswith("yf:"):
        g = google_finance.stats(symbol) or {}
        sources.append({"name": google_finance.SOURCE, "ok": bool(g)})

    criteria = []

    # 1. Valorisation — PER
    eps_based = price / c["eps_est"] if price and c.get("eps_est") else None
    per, src = first(
        (y.get("forwardPE"), yahoo.SOURCE),
        (y.get("trailingPE"), yahoo.SOURCE),
        (eps_based if c.get("eps_est", 0) and c["eps_est"] > 0 else None, boursorama.SOURCE),
        (g.get("per"), google_finance.SOURCE),
    )
    losing = (c.get("eps_est") is not None and c["eps_est"] <= 0) or (
        y.get("trailingEps") is not None and y["trailingEps"] <= 0 and not y.get("forwardPE")
    )
    if losing:
        criteria.append(crit("per", "Valorisation (PER)", None, "Bénéfice négatif", 2, 20,
                             "L'entreprise perd de l'argent : le PER n'a pas de sens.", src))
    elif per is not None:
        s = tier(per, [(8, 8), (12, 9), (16, 8), (20, 7), (25, 6), (35, 4.5), (50, 3)], 2)
        comment = ("Bon marché par rapport aux bénéfices." if per < 16 else
                   "Valorisation raisonnable." if per < 25 else
                   "Valorisation élevée : beaucoup de croissance est déjà dans le prix.")
        if per < 8:
            comment = "Très bon marché : vérifier qu'il n'y a pas de problème caché."
        criteria.append(crit("per", "Valorisation (PER)", per, num(per, 1), s, 20, comment, src))
    else:
        criteria.append(crit("per", "Valorisation (PER)", None, "—", None, 20, "Donnée indisponible."))

    # 2. Croissance du chiffre d'affaires
    growth, src = first(
        (y["revenueGrowth"] * 100 if y.get("revenueGrowth") is not None else None, yahoo.SOURCE),
        (c.get("revenue_growth_pct"), boursorama.SOURCE),
    )
    if growth is not None:
        s = tier(growth, [(-10, 2), (0, 4), (5, 5.5), (10, 7), (20, 8.5)], 9.5)
        comment = ("Chiffre d'affaires en recul." if growth < 0 else
                   "Croissance modeste." if growth < 10 else "Belle croissance.")
        criteria.append(crit("growth", "Croissance du chiffre d'affaires", growth, pct(growth, sign=True), s, 15, comment, src))
    else:
        criteria.append(crit("growth", "Croissance du chiffre d'affaires", None, "—", None, 15, "Donnée indisponible."))

    # 3. Rentabilité — marge opérationnelle
    # Priorité à la marge annuelle estimée (plus stable que le dernier trimestre publié)
    margin, src = first(
        (c.get("ebit_margin_pct"), boursorama.SOURCE),
        (y["operatingMargins"] * 100 if y.get("operatingMargins") is not None else None, yahoo.SOURCE),
        (y["profitMargins"] * 100 if y.get("profitMargins") is not None else None, yahoo.SOURCE),
    )
    if margin is not None:
        s = tier(margin, [(0, 1.5), (5, 4), (10, 5.5), (15, 7), (25, 8.5)], 9.5)
        comment = ("Activité déficitaire." if margin < 0 else "Marges faibles." if margin < 10 else
                   "Bonne rentabilité." if margin < 25 else "Rentabilité excellente.")
        criteria.append(crit("margin", "Marge opérationnelle", margin, pct(margin), s, 15, comment, src))
    else:
        criteria.append(crit("margin", "Marge opérationnelle", None, "—", None, 15, "Donnée indisponible."))

    # 4. Endettement — dette nette / EBITDA
    financial = (y.get("sector") or "") == "Financial Services"
    nd_y = None
    if y.get("ebitda") and y["ebitda"] > 0 and y.get("totalDebt") is not None:
        nd_y = (y["totalDebt"] - (y.get("totalCash") or 0)) / y["ebitda"]
    lev, src = first((nd_y, yahoo.SOURCE), (c.get("net_debt_to_ebitda"), boursorama.SOURCE))
    if financial:
        criteria.append(crit("debt", "Endettement (dette nette / EBITDA)", None, "Non pertinent", None, 15,
                             "Banque ou assurance : ce ratio ne s'applique pas."))
    elif lev is not None:
        s = tier(lev, [(0, 9.5), (1, 9), (2, 7.5), (3, 5.5), (4, 3.5)], 2)
        comment = ("Plus de trésorerie que de dettes." if lev < 0 else
                   "Endettement maîtrisé." if lev < 2 else
                   "Endettement à surveiller." if lev < 4 else "Endettement élevé.")
        display = "Trésorerie nette" if lev < 0 else f"{num(lev, 1)} ×"
        criteria.append(crit("debt", "Endettement (dette nette / EBITDA)", lev, display, s, 15, comment, src))
    else:
        criteria.append(crit("debt", "Endettement (dette nette / EBITDA)", None, "—", None, 15, "Donnée indisponible."))

    # 5. Flux de trésorerie
    if y.get("freeCashflow") is not None and y.get("marketCap"):
        fcf = y["freeCashflow"] / y["marketCap"] * 100
        s = tier(fcf, [(0, 2), (2, 5), (4, 6.5), (6, 8)], 9)
        comment = "L'entreprise consomme du cash." if fcf < 0 else (
            "Génère peu de cash par rapport à sa valeur." if fcf < 4 else "Génère beaucoup de cash.")
        criteria.append(crit("fcf", "Rendement du free cash-flow", fcf, pct(fcf), s, 10, comment, yahoo.SOURCE))
    elif c.get("cash_flow_per_share") is not None and price:
        cfy = c["cash_flow_per_share"] / price * 100
        s = tier(cfy, [(0, 2), (2, 4), (5, 6), (8, 7.5), (12, 8.5)], 9)
        criteria.append(crit("fcf", "Cash-flow par action / cours", cfy, pct(cfy), s, 10,
                             "Cash généré par action rapporté au cours.", boursorama.SOURCE))
    else:
        criteria.append(crit("fcf", "Flux de trésorerie", None, "—", None, 10, "Donnée indisponible."))

    # 6. Dividende
    y_div = None
    if y.get("dividendRate") and price:
        y_div = y["dividendRate"] / price * 100
    elif y.get("trailingAnnualDividendYield") is not None:
        y_div = y["trailingAnnualDividendYield"] * 100
    elif y.get("quoteType") == "EQUITY" and y.get("dividendRate") in (None, 0):
        y_div = 0.0
    div, src = first((y_div, yahoo.SOURCE), (c.get("dividend_yield_pct"), boursorama.SOURCE),
                     (g.get("dividend_yield_pct"), google_finance.SOURCE))
    payout = y.get("payoutRatio")
    if div is not None:
        if div == 0:
            s, comment = 5, "Pas de dividende (fréquent pour les valeurs de croissance)."
        else:
            s = tier(div, [(2, 6.5), (4, 7.5), (7, 8)], 6)
            comment = "Rendement très élevé : vérifier qu'il est soutenable." if div >= 7 else "Dividende versé."
        if payout and payout > 1:
            s, comment = 3, "Le dividende dépasse les bénéfices : risque de baisse."
        criteria.append(crit("dividend", "Rendement du dividende", div, pct(div, 2), s, 5, comment, src))
    else:
        criteria.append(crit("dividend", "Rendement du dividende", None, "—", None, 5, "Donnée indisponible."))

    # 7. Avis des analystes — potentiel + recommandation
    target, src = first((y.get("targetMeanPrice"), yahoo.SOURCE), (c.get("target_median"), boursorama.SOURCE),
                        (g.get("target_mean"), google_finance.SOURCE))
    upside = (target / price - 1) * 100 if target and price else None
    rating, _ = first((c.get("median_rating"), boursorama.SOURCE), (y.get("recommendationMean"), yahoo.SOURCE))
    n_analysts, _ = first((c.get("analysts"), None), (y.get("numberOfAnalystOpinions"), None))
    notes = []
    if upside is not None or rating is not None:
        parts = []
        if upside is not None:
            parts.append(tier(upside, [(-10, 2), (0, 4), (10, 6), (20, 7.5), (35, 8.5)], 9))
        if rating is not None:
            parts.append(max(0.0, min(10.0, 10 - (rating - 1) * 2.25)))
        s = sum(parts) / len(parts)
        label_r = None
        if rating is not None:
            label_r = ("Achat" if rating < 1.8 else "Renforcer" if rating < 2.5 else
                       "Conserver" if rating < 3.5 else "Alléger" if rating < 4.2 else "Vente")
        display = " · ".join(p for p in [
            f"objectif {num(target, 2)} {cur or ''}".strip() if target else None,
            pct(upside, sign=True) if upside is not None else None,
            f"consensus « {label_r} »" if label_r else None,
        ] if p)
        weight = 20 if (n_analysts or 0) >= 3 else 10
        comment = f"{n_analysts} analystes suivent la valeur." if n_analysts else "Avis des analystes."
        criteria.append(crit("analysts", "Avis des analystes", upside, display, s, weight, comment, src))
    else:
        criteria.append(crit("analysts", "Avis des analystes", None, "—", None, 20, "Aucun suivi d'analystes trouvé."))

    # Informations complémentaires (non notées)
    info = []
    if y.get("sector"):
        info.append({"label": "Secteur", "display": f"{y['sector']} · {y.get('industry') or ''}".strip(" ·")})
    mcap, _ = first((y.get("marketCap"), None), (g.get("market_cap"), None))
    info.append({"label": "Capitalisation", "display": big(mcap, cur)})
    if c.get("eps_est") is not None:
        info.append({"label": "BPA estimé (année en cours)", "display": f"{num(c['eps_est'], 2)} {cur or ''}".strip()})
    eps_ttm, _ = first((y.get("trailingEps"), None), (g.get("eps"), None))
    if eps_ttm is not None:
        info.append({"label": "BPA (12 derniers mois)", "display": f"{num(eps_ttm, 2)} {cur or ''}".strip()})
    if c.get("opinions"):
        o = c["opinions"]
        info.append({"label": "Opinions des analystes", "display":
                     f"{o.get('acheter', 0) + o.get('renforcer', 0)} achat · {o.get('conserver', 0)} conserver · "
                     f"{o.get('alleger', 0) + o.get('vendre', 0)} vente"})
    earnings = yahoo.next_earnings(symbol) if pid.startswith("yf:") else None
    if isinstance(earnings, datetime):
        earnings = earnings.date()
    if isinstance(earnings, date):
        days = (earnings - date.today()).days
        info.append({"label": "Prochains résultats", "display": earnings.strftime("%d/%m/%Y") +
                     (f" (dans {days} j)" if days is not None and days >= 0 else "")})
        if days is not None and 0 <= days <= 7:
            notes.append(f"Résultats trimestriels dans {days} jour(s) : forte volatilité possible.")

    return finalize(criteria, info, sources, note=" ".join(notes) or None)


# ---------------------------------------------------------------- ETF
def _etf(product: dict, quote: dict) -> dict:
    pid, symbol, cur = product["id"], product.get("symbol") or "", product.get("currency")
    sources = []
    isin = product.get("isin")
    bo_path = pid[3:] if pid.startswith("bo:") else None
    bo = None

    def load_boursorama():
        nonlocal bo_path
        if bo_path is None and symbol:
            listing = boursorama.find_listing(symbol, kinds=("ETF",))
            bo_path = listing["id"][3:] if listing else None
        return boursorama.etf_details(bo_path) if bo_path else None

    if not isin:  # l'ISIN est nécessaire pour justETF : on le lit sur Boursorama
        bo = load_boursorama()
        isin = (bo or {}).get("isin")
    j = justetf.profile(isin) if isin else None
    sources.append({"name": justetf.SOURCE, "ok": j is not None})
    if j is None and bo is None:
        bo = load_boursorama()
    if bo is not None or j is None:
        sources.append({"name": boursorama.SOURCE, "ok": bo is not None})
    y = None
    if j is None and bo is None and pid.startswith("yf:"):
        y = yahoo.info(symbol)
        sources.append({"name": yahoo.SOURCE, "ok": y is not None})
    j, bo, y = j or {}, bo or {}, y or {}

    ter, src = first((j.get("ter_pct"), justetf.SOURCE), (bo.get("ter_pct"), boursorama.SOURCE),
                     (y.get("netExpenseRatio"), yahoo.SOURCE))
    size, _ = first((j.get("fund_size"), None), (bo.get("fund_size"), None), (y.get("totalAssets"), None))
    size_cur = j.get("fund_size_currency") or bo.get("fund_size_currency") or cur
    holdings = j.get("holdings")
    ytd, ytd_src = j.get("ytd_pct"), justetf.SOURCE
    if ytd is None and pid.startswith("yf:"):  # calculée seulement si justETF ne l'a pas
        ytd, ytd_src = yahoo.ytd_return(symbol), yahoo.SOURCE
    replication = j.get("replication") or bo.get("replication")
    index = j.get("index") or bo.get("index") or y.get("category")

    criteria = []
    if ter is not None:
        s = tier(ter, [(0.1, 9.5), (0.2, 9), (0.3, 8), (0.5, 6.5), (0.8, 5)], 3)
        criteria.append(crit("ter", "Frais annuels (TER)", ter, pct(ter, 2), s, 30,
                             "Frais très bas." if ter < 0.3 else "Frais moyens." if ter < 0.8 else "Frais élevés.", src))
    else:
        criteria.append(crit("ter", "Frais annuels (TER)", None, "—", None, 30, "Donnée indisponible."))
    if size is not None:
        s = tier(size, [(50e6, 3), (100e6, 4.5), (500e6, 6), (1e9, 8)], 9)
        criteria.append(crit("size", "Taille du fonds", size, big(size, size_cur), s, 25,
                             "Petit fonds : risque de fermeture." if size < 100e6 else "Fonds de taille confortable."))
    else:
        criteria.append(crit("size", "Taille du fonds", None, "—", None, 25, "Donnée indisponible."))
    if holdings:
        s = tier(holdings, [(20, 3.5), (50, 5), (100, 7), (500, 8.5)], 9.5)
        criteria.append(crit("holdings", "Diversification (nombre de positions)", holdings, num(holdings, 0), s, 20,
                             "Très diversifié." if holdings >= 500 else "Diversification correcte." if holdings >= 50 else "Peu diversifié.",
                             justetf.SOURCE))
    else:
        criteria.append(crit("holdings", "Diversification (nombre de positions)", None, "—", None, 20, "Donnée indisponible."))
    if ytd is not None:
        s = tier(ytd, [(-10, 3), (0, 4.5), (5, 6), (10, 7), (20, 8)], 8.5)
        criteria.append(crit("ytd", "Performance depuis le 1er janvier", ytd, pct(ytd, sign=True), s, 15,
                             "Performance passée : ne préjuge pas de l'avenir.", ytd_src))
    else:
        criteria.append(crit("ytd", "Performance depuis le 1er janvier", None, "—", None, 15, "Donnée indisponible."))
    if replication:
        physical = "phys" in replication.lower()
        criteria.append(crit("replication", "Réplication", None, replication, 8 if physical else 6.5, 10,
                             "Le fonds détient réellement les titres." if physical else
                             "Réplication par contrat d'échange (swap) : risque de contrepartie limité mais présent."))

    info = [
        {"label": "Indice suivi", "display": index},
        {"label": "Distribution", "display": j.get("distribution") or bo.get("distribution")},
        {"label": "Date de lancement", "display": j.get("inception") or bo.get("inception")},
        {"label": "ISIN", "display": isin},
    ]
    note, cap = None, None
    if LEVERAGED_ETF.search(product.get("name") or ""):
        note = "ETF à effet de levier ou inverse : réservé au très court terme, pertes rapides possibles."
        cap = 4
    return finalize(criteria, info, sources, note=note, cap=cap)


# ---------------------------------------------------------------- TURBO / WARRANT
def _maturity_days(text: str | None) -> int | None:
    if not text:
        return None
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return (datetime.strptime(text.strip()[:10], fmt).date() - date.today()).days
        except ValueError:
            continue
    return None


def _derivative(product: dict, d: dict) -> dict:
    criteria = []
    dist = d.get("barrier_distance_pct")
    if dist is not None:
        s = tier(dist, [(3, 1), (5, 2.5), (10, 4.5), (15, 6), (25, 7.5), (40, 8.5)], 9)
        comment = ("Barrière très proche : risque élevé de désactivation (perte totale)." if dist < 5 else
                   "Barrière assez proche : à surveiller de près." if dist < 15 else
                   "Marge de sécurité confortable avant la barrière.")
        criteria.append(crit("barrier", "Distance à la barrière", dist, pct(dist), s, 40, comment, boursorama.SOURCE))
    days = _maturity_days(d.get("maturity"))
    if days is not None:
        s = tier(days, [(30, 2), (90, 4), (180, 6), (365, 7.5)], 8.5)
        criteria.append(crit("maturity", "Temps avant l'échéance", days, f"{days} jours", s, 30 if dist is None else 15,
                             "Échéance proche : la valeur temps fond vite." if days < 90 else "Échéance lointaine."))
    lev = d.get("leverage")
    if lev is not None:
        s = tier(lev, [(2, 9), (5, 8), (10, 6), (20, 4)], 2)
        criteria.append(crit("leverage", "Effet de levier", lev, f"× {num(lev, 2)}", s, 25,
                             "Levier modéré." if lev < 5 else "Levier élevé : gains et pertes amplifiés." if lev < 20 else
                             "Levier très élevé : très spéculatif.", boursorama.SOURCE))
    spread = d.get("spread_pct")
    if spread is not None:
        s = tier(spread, [(0.5, 9), (1, 8), (2, 6.5), (5, 4)], 2)
        criteria.append(crit("spread", "Écart achat / vente (spread)", spread, pct(spread, 2), s, 20,
                             "Coût d'entrée/sortie faible." if spread < 1 else "Écart important : coût caché à l'achat et à la vente.",
                             boursorama.SOURCE))
    issuer = (d.get("issuer") or "").upper()
    if issuer:
        major = any(name in issuer for name in MAJOR_ISSUERS)
        criteria.append(crit("issuer", "Émetteur", None, d.get("issuer"), 8 if major else 6, 15,
                             "Grand émetteur reconnu." if major else "Émetteur moins connu : vérifier sa solidité."))

    direction = {"CALL": "à la hausse", "PUT": "à la baisse"}.get(d.get("direction"), None)
    info = [
        {"label": "Sous-jacent", "display": d.get("underlying")},
        {"label": "Pari", "display": f"{d.get('underlying') or 'Le sous-jacent'} {direction}" if direction else None},
        {"label": "Échéance", "display": d.get("maturity")},
    ]
    note = ("Pour un produit à levier, ce score mesure le risque du produit lui-même. "
            f"La direction de {d.get('underlying') or 'son sous-jacent'} sera évaluée par l'analyse technique.")
    return finalize(criteria, info, [{"name": boursorama.SOURCE, "ok": True}], note=note)


# ---------------------------------------------------------------- CRYPTO
def _crypto(product: dict, quote: dict) -> dict:
    symbol = product.get("symbol") or ""
    base, _, vs = symbol.partition("-")
    cg = coingecko.market(base, vs or "eur")
    sources = [{"name": coingecko.SOURCE, "ok": cg is not None}]
    y = {}
    if cg is None and product["id"].startswith("yf:"):
        y = yahoo.info(symbol) or {}
        sources.append({"name": yahoo.SOURCE, "ok": bool(y)})
    cg = cg or {}
    cur = cg.get("currency") or product.get("currency")
    mcap, src = first((cg.get("market_cap"), coingecko.SOURCE), (y.get("marketCap"), yahoo.SOURCE))
    vol, _ = first((cg.get("volume_24h"), None), (y.get("volume24Hr"), None))

    criteria = []
    if mcap:
        s = tier(mcap, [(1e8, 2.5), (1e9, 4.5), (1e10, 6.5), (1e11, 8)], 9)
        criteria.append(crit("mcap", "Capitalisation", mcap, big(mcap, cur), s, 45,
                             "Crypto majeure, très suivie." if mcap >= 1e11 else
                             "Petite capitalisation : très spéculatif." if mcap < 1e9 else "Capitalisation moyenne.", src))
    else:
        criteria.append(crit("mcap", "Capitalisation", None, "—", None, 45, "Donnée indisponible."))
    if mcap and vol:
        ratio = vol / mcap * 100
        s = tier(ratio, [(0.5, 4), (2, 6), (5, 7.5)], 8.5)
        criteria.append(crit("liquidity", "Liquidité (volume 24 h / capitalisation)", ratio,
                             f"{big(vol, cur)} · {pct(ratio, 2)}", s, 30,
                             "Échanges abondants." if ratio >= 2 else "Échanges limités.", src))
    else:
        criteria.append(crit("liquidity", "Liquidité (volume 24 h)", None, "—", None, 30, "Donnée indisponible."))
    if cg.get("circulating_supply"):
        mx = cg.get("max_supply")
        if mx:
            ratio = cg["circulating_supply"] / mx * 100
            s = tier(ratio, [(50, 5.5), (90, 7)], 8.5)
            criteria.append(crit("supply", "Offre en circulation / offre maximale", ratio, pct(ratio), s, 25,
                                 "Offre plafonnée : peu de nouvelles unités à venir." if ratio >= 90 else
                                 "Une part importante reste à émettre (dilution possible).", coingecko.SOURCE))
        else:
            criteria.append(crit("supply", "Offre maximale", None, "Illimitée", 5, 25,
                                 "Pas de plafond d'émission : inflation possible.", coingecko.SOURCE))
    info = [
        {"label": "Rang mondial", "display": f"n° {cg['rank']}" if cg.get("rank") else None},
        {"label": "Écart au plus haut historique", "display": pct(cg.get("ath_change_pct"), sign=True) if cg.get("ath_change_pct") is not None else None},
    ]
    return finalize(criteria, info, sources,
                    note="Une crypto ne produit ni bénéfices ni dividendes : ce score mesure surtout sa taille et sa liquidité.",
                    cap=8)
