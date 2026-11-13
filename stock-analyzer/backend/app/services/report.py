"""Module 7 — Rapport justificatif.

- Résumé exécutif (3 phrases)
- Forces / faiblesses (critères les mieux et les moins bien notés des trois analyses)
- Position vs MM100 en langage clair
- Stop-loss proposés : sous le support technique, −5 %, −8 %, −12 % (+ niveau conseillé selon la volatilité)
- 3 alternatives : même secteur, ETF sectoriel, valeur défensive
- Sources utilisées + horodatage + avertissement MiFID II
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import analysis, technical
from .decision import FUNDAMENTAL_PHRASES, _fundamental_kind
from .fundamentals import num, pct
from .sentiment import clean_name
from .sources import boursorama, cache, yahoo
from .sources.http import fetch_text

logger = logging.getLogger(__name__)

CACHE_TTL = 15 * 60
STOP_PCTS = (5, 8, 12)

# ETF sectoriels « MSCI World » en euros (XETRA) selon le secteur Yahoo
SECTOR_ETF = {
    "Technology": "XDWT.DE", "Healthcare": "XDWH.DE", "Financial Services": "XDWF.DE",
    "Energy": "XDW0.DE", "Industrials": "XDWI.DE", "Basic Materials": "XDWM.DE",
    "Consumer Defensive": "XDWS.DE", "Consumer Cyclical": "XDWC.DE", "Utilities": "XDWU.DE",
    "Communication Services": "XWTS.DE", "Real Estate": "IWDP.AS",
}
WORLD_ETF = "IWDA.AS"
WORLD_ALT = ["IWDA.AS", "VWCE.DE"]  # MSCI World puis FTSE All-World
# Valeurs défensives (consommation de base, santé, services aux collectivités) cotées en euros
DEFENSIVE = ["AD.AS", "SAN.PA", "IBE.MC", "UNA.AS", "ELI.BR"]

DISCLAIMER = (
    "Ce rapport est généré automatiquement à partir de données publiques (Yahoo Finance, "
    "Boursorama, Google Finance, justETF, CoinGecko, Google News) qui peuvent être incomplètes, "
    "différées ou erronées. Il constitue une aide à la réflexion et non un conseil en "
    "investissement personnalisé au sens de la directive européenne MiFID II : il ne tient "
    "compte ni de votre situation financière, ni de vos objectifs, ni de votre tolérance au risque. "
    "Les performances passées ne préjugent pas des performances futures. Les produits à effet "
    "de levier (turbos, warrants) peuvent entraîner la perte totale du capital investi. "
    "Avant toute décision, consultez un conseiller agréé (FSMA en Belgique)."
)


# ---------------------------------------------------------------- outils
def _price(v, cur):
    return f"{num(v, 2 if v and abs(v) >= 1 else 4)} {cur or ''}".strip() if v is not None else "—"


def _atr_pct(chart: list[dict], n: int = 14) -> float | None:
    """Volatilité moyenne quotidienne (ATR 14) en % du dernier cours."""
    rows = [r for r in chart if None not in (r.get("high"), r.get("low"), r.get("close"))]
    if len(rows) < n + 1 or not rows[-1]["close"]:
        return None
    trs = []
    for prev, cur in zip(rows[-n - 1:-1], rows[-n:]):
        trs.append(max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]), abs(cur["low"] - prev["close"])))
    return sum(trs) / n / rows[-1]["close"] * 100


# ---------------------------------------------------------------- résumé
def executive_summary(full: dict) -> list[str]:
    p, d = full["product"], full["decision"]
    t, f, s = full["technical"], full["fundamentals"], full["sentiment"]
    name = f"{p['name']} ({p.get('symbol') or p.get('isin') or ''})".replace(" ()", "")
    buy = d["buy"]
    lead = {"FAVORABLE": "des conditions favorables à l'achat", "PRUDENCE": "un contexte qui appelle à la prudence",
            "DEFAVORABLE": "des conditions défavorables à l'achat"}[buy["level"]]
    s1 = f"{name} obtient un score global de {num(d['score'], 1)}/10, ce qui traduit {lead}."

    mm = t.get("mm100") if t.get("applicable") else None
    under = f" de {clean_name(t['analysed']['name'])}" if p["type"] in ("TURBO", "WARRANT") else ""
    if mm:
        if mm.get("cross"):
            trend = ("vient de repasser au-dessus" if mm["cross"]["direction"] == "HAUSSIER" else "vient de passer sous")
            trend = f"le cours{under} {trend} sa moyenne mobile 100 jours (écart {pct(mm['distance_pct'], 1, sign=True)})"
        else:
            trend = (f"le cours{under} est {'au-dessus' if mm['above'] else 'en dessous'} de sa moyenne mobile "
                     f"100 jours ({pct(mm['distance_pct'], 1, sign=True)}), tendance de fond "
                     f"{'haussière' if mm['above'] else 'baissière'}")
    else:
        trend = "la tendance technique n'a pas pu être évaluée"
    if f.get("applicable") and f.get("score") is not None:
        kind = _fundamental_kind(f)
        good, mid, bad = FUNDAMENTAL_PHRASES[kind]
        phrase = good if f["score"] >= 7.5 else mid if f["score"] >= 5 else bad
        if kind == "stock":
            phrase = "les " + phrase.replace("fondamentaux ", "fondamentaux sont ")
        else:
            phrase = f"côté produit : {phrase}"
        s2 = f"Sur le plan technique, {trend} ; {phrase} ({num(f['score'], 1)}/10)."
    else:
        s2 = f"Sur le plan technique, {trend}."

    if s.get("applicable"):
        tone = {"Positif": "favorable", "Neutre": "neutre", "Négatif": "défavorable"}.get(s.get("verdict"), "neutre")
        s3 = f"L'actualité des 72 dernières heures est {tone} ({num(s['score'], 1)}/10)"
        earnings = next((e for e in s.get("events", []) if e["type"] == "Earnings Date"), None)
        s3 += f", et des résultats sont attendus le {datetime.fromisoformat(earnings['date']).strftime('%d/%m/%Y')}." if earnings else "."
    else:
        s3 = "Aucune actualité exploitable n'a été trouvée."
    return [s1, s2, s3]


# ---------------------------------------------------------------- forces / faiblesses
def strengths_weaknesses(full: dict, limit: int = 4) -> tuple[list[dict], list[dict]]:
    items = []
    for key, label in (("fundamentals", "Fondamental"), ("technical", "Technique")):
        for c in full[key].get("criteria", []) or []:
            if c.get("score") is not None:
                items.append({"area": label, "label": c["label"].replace("★ ", ""), "display": c["display"],
                              "score": c["score"], "comment": c["comment"]})
    s = full["sentiment"]
    if s.get("applicable") and s.get("items"):
        items.append({"area": "Sentiment", "label": "Actualité (72 h)",
                      "display": f"{s['counts']['positif']} 🟢 · {s['counts']['neutre']} 🟡 · {s['counts']['negatif']} 🔴",
                      "score": s["score"], "comment": f"Sentiment {s['verdict'].lower()} sur {len(s['items'])} titres."})
    # Pour un put, les critères techniques sont lus sur le sous-jacent : on les inverse
    if full["technical"].get("inverse"):
        for it in items:
            if it["area"] == "Technique":
                it["score"] = round(10 - it["score"], 1)
                it["comment"] += " (lu à l'envers pour un put)"
    strengths = sorted([i for i in items if i["score"] >= 7], key=lambda i: -i["score"])[:limit]
    weaknesses = sorted([i for i in items if i["score"] <= 4], key=lambda i: i["score"])[:limit]
    return strengths, weaknesses


# ---------------------------------------------------------------- MM100
def mm100_text(full: dict) -> str:
    t = full["technical"]
    mm = t.get("mm100") if t.get("applicable") else None
    if not mm:
        return "La moyenne mobile 100 jours n'est pas disponible (historique trop court ou indisponible)."
    cur = t.get("currency") or ""
    subject = clean_name(t["analysed"]["name"]) if full["product"]["type"] in ("TURBO", "WARRANT") else t["analysed"]["name"]
    base = (f"La moyenne mobile 100 jours (MM100) de {subject} vaut {_price(mm['value'], cur)} ; "
            f"c'est le prix moyen payé sur les 100 dernières séances. ")
    if mm.get("cross"):
        when = "aujourd'hui" if mm["cross"]["sessions_ago"] == 0 else f"il y a {mm['cross']['sessions_ago']} séance(s)"
        if mm["cross"]["direction"] == "HAUSSIER":
            base += (f"Le cours l'a franchie à la hausse {when} : c'est souvent le signe d'un retournement "
                     "de tendance favorable, à confirmer dans les prochains jours.")
        else:
            base += (f"Le cours est passé dessous {when} : signal de dégradation de la tendance de fond. "
                     "Beaucoup d'investisseurs attendent un retour au-dessus avant d'acheter.")
    elif mm["above"]:
        base += (f"Le cours se situe {pct(mm['distance_pct'], 1)} au-dessus : les acheteurs dominent sur le moyen terme.")
        if mm["distance_pct"] > 15:
            base += " L'écart est important : un retour vers la moyenne (correction) est possible."
    else:
        base += (f"Le cours se situe {pct(abs(mm['distance_pct']), 1)} en dessous : les vendeurs dominent sur le "
                 "moyen terme. Un achat maintenant parie sur un retournement qui n'est pas encore confirmé.")
    if mm.get("slope_pct") is not None:
        base += f" La MM100 elle-même est {'orientée à la hausse' if mm['slope_pct'] > 0 else 'orientée à la baisse'}."
    if t.get("inverse"):
        base += " Pour un turbo put, une tendance baissière du sous-jacent est favorable."
    return base


# ---------------------------------------------------------------- stop-loss
def stop_losses(full: dict) -> dict:
    p, q, t, d = full["product"], full["quote"], full["technical"], full.get("derivative")
    price, cur = q.get("price"), p.get("currency")
    if not price:
        return {"levels": [], "recommended": None, "notes": []}
    levels, notes = [], []
    levels_t = (t.get("levels") or {}) if t.get("applicable") else {}
    atr = _atr_pct(t.get("chart") or []) if t.get("applicable") else None

    if p["type"] in ("TURBO", "WARRANT") and d:
        # Le stop technique se place sur le sous-jacent puis se traduit en prix du turbo
        strike, parity = d.get("strike"), d.get("parity")
        put = d.get("direction") == "PUT"
        level = levels_t.get("resistance") if put else levels_t.get("support")
        if level and strike and parity:
            trigger = level * (1.01 if put else 0.99)
            turbo_px = ((strike - trigger) if put else (trigger - strike)) / parity
            if 0 < turbo_px < price:
                levels.append({"key": "support", "label": f"{'Résistance' if put else 'Support'} du sous-jacent",
                               "price": round(turbo_px, 4), "distance_pct": round((turbo_px / price - 1) * 100, 1),
                               "detail": f"si {clean_name(t['analysed']['name'])} {'dépasse' if put else 'casse'} {_price(trigger, t.get('currency'))}"})
        if d.get("barrier_distance_pct") is not None:
            notes.append(f"La barrière désactivante est à {pct(d['barrier_distance_pct'], 1)} du sous-jacent : "
                         "le stop-loss doit se déclencher bien avant pour éviter la perte totale.")
        if d.get("leverage") and atr:
            atr *= d["leverage"]  # le turbo amplifie les variations du sous-jacent
        if d.get("leverage"):
            notes.append(f"Avec un levier de × {num(d['leverage'], 1)}, une variation de 5 % du turbo correspond à "
                         f"environ {pct(5 / d['leverage'], 1)} du sous-jacent.")
    else:
        support = levels_t.get("support")
        if support and support < price:
            stop = support * 0.99  # 1 % sous le support pour éviter les faux signaux
            levels.append({"key": "support", "label": "Sous le support technique", "price": round(stop, 4),
                           "distance_pct": round((stop / price - 1) * 100, 1),
                           "detail": f"support à {_price(support, cur)}, stop placé 1 % en dessous"})

    for x in STOP_PCTS:
        levels.append({"key": f"pct{x}", "label": f"−{x} %", "price": round(price * (1 - x / 100), 4),
                       "distance_pct": -float(x), "detail": None})

    # Stop conseillé : le support s'il est à une distance raisonnable, sinon le % adapté à la volatilité
    recommended = None
    sup = next((lv for lv in levels if lv["key"] == "support"), None)
    if sup and -12 <= sup["distance_pct"] <= -3:
        recommended = "support"
        reason = (f"Le niveau technique ({sup['label'].lower()}) est à une distance raisonnable : "
                  "le franchir invaliderait le scénario.")
    else:
        target = 2 * atr if atr else 8
        recommended = min((f"pct{x}" for x in STOP_PCTS), key=lambda k: abs(int(k[3:]) - target))
        what = "du produit" if p["type"] in ("TURBO", "WARRANT") else "du cours"
        reason = (f"Volatilité moyenne {what} de {pct(atr, 1)} par jour : un stop à {recommended[3:]} % laisse respirer "
                  "le cours sans exposer à une perte trop lourde." if atr else "Stop intermédiaire par défaut.")
        if atr and target > 12:
            notes.append(f"Très volatil (≈ {pct(atr, 1)} par jour) : même un stop à −12 % peut être "
                         "touché en une seule séance. Réduisez la taille de la position.")
        if sup and sup["distance_pct"] < -12:
            notes.append("Le niveau technique est éloigné (plus de 12 %) : stop en pourcentage préféré.")
    for lv in levels:
        lv["recommended"] = lv["key"] == recommended
    return {"levels": levels, "recommended": recommended, "reason": reason, "atr_pct": round(atr, 2) if atr else None,
            "currency": cur, "notes": notes}


# ---------------------------------------------------------------- alternatives
def _peers(symbol: str) -> list[str]:
    text = fetch_text(f"https://query2.finance.yahoo.com/v6/finance/recommendationsbysymbol/{symbol}")
    try:
        return [x["symbol"] for x in json.loads(text)["finance"]["result"][0]["recommendedSymbols"]]
    except (TypeError, ValueError, KeyError, IndexError):
        return []


def _snapshot(symbol: str) -> dict | None:
    """Cours + position vs MM100 d'un candidat (analyse technique en cache 15 min)."""
    q = yahoo.quote(symbol)
    if not q:
        return None
    product = {"id": f"yf:{symbol}", "symbol": symbol, "name": q["name"], "type": q["type"], "currency": q["currency"]}
    t = technical.analyze(product, q)
    mm = t.get("mm100") if t.get("applicable") else None
    return {"id": product["id"], "symbol": symbol, "name": q["name"], "type": q["type"], "currency": q["currency"],
            "price": q["price"], "change_pct": q.get("change_pct"), "technical_score": t.get("score"),
            "mm100_status": mm["status"] if mm else None, "mm100_distance_pct": mm["distance_pct"] if mm else None}


def _best(symbols: list[str], exclude: set[str], limit: int = 3) -> dict | None:
    snaps = [s for s in (_snapshot(x) for x in [y for y in symbols if y not in exclude][:limit]) if s]
    if not snaps:
        return None
    return max(snaps, key=lambda s: (s["technical_score"] or 0))


def _why(snap: dict) -> str:
    if snap.get("mm100_status") == "AU-DESSUS":
        return f"au-dessus de sa MM100 ({pct(snap['mm100_distance_pct'], 1, sign=True)})"
    if snap.get("mm100_status") == "CROISEMENT":
        return "vient de croiser sa MM100"
    if snap.get("mm100_status") == "EN-DESSOUS":
        return f"sous sa MM100 ({pct(snap['mm100_distance_pct'], 1, sign=True)}), à surveiller"
    return "tendance non évaluée"


def alternatives(full: dict) -> list[dict]:
    p, f, t = full["product"], full["fundamentals"], full["technical"]
    symbol = p.get("symbol") if p["id"].startswith("yf:") else None
    analysed = t.get("analysed") or {}
    base_symbol = symbol or (analysed.get("symbol") if analysed.get("id", "").startswith("yf:") else None)
    exclude = {s for s in (symbol, base_symbol) if s}
    sector = next((i["display"].split(" · ")[0] for i in f.get("info", []) if i["label"] == "Secteur"), None)
    if not sector and base_symbol and p["type"] in ("ACTION", "TURBO", "WARRANT"):
        sector = (yahoo.info(base_symbol) or {}).get("sector")
        if not sector:  # Yahoo souvent limité : on lit le secteur sur Boursorama
            listing = boursorama.find_listing(base_symbol)
            sector = boursorama.sector(listing["id"][3:]) if listing else None
    out = []

    def add(role, title, snap, reason):
        if snap:
            out.append({"role": role, "title": title, **snap, "reason": f"{reason} — {_why(snap)}."})

    kind = p["type"]
    if kind in ("TURBO", "WARRANT") and base_symbol:
        add("same", "Le sous-jacent en direct (sans levier)", _snapshot(base_symbol),
            "Même pari, sans risque de désactivation ni effet de levier")
    elif base_symbol:
        label = {"ETF": "ETF comparable", "CRYPTO": "Autre crypto majeure", "INDICE": "Indice ou ETF proche"}.get(kind, "Même secteur")
        add("same", label, _best(_peers(base_symbol), exclude), "Alternative proche identifiée par Yahoo Finance")

    if kind == "CRYPTO":
        etf = "BTCE.DE" if symbol and not symbol.startswith("BTC") else WORLD_ETF
        add("sector", "Version cotée en bourse" if etf == "BTCE.DE" else "ETF monde diversifié", _snapshot(etf),
            "Exposition via un produit coté sur XETRA" if etf == "BTCE.DE" else "Diversification sur plus de 1 000 sociétés")
    else:
        etf = SECTOR_ETF.get(sector or "")
        if etf and etf not in exclude:
            add("sector", f"ETF sectoriel ({sector})", _snapshot(etf), "Tout le secteur au niveau mondial, en euros, frais réduits")
        else:
            taken = exclude | {o["symbol"] for o in out}
            world = next((w for w in WORLD_ALT if w not in taken), None)
            if world:
                add("sector", "ETF monde diversifié", _snapshot(world),
                    "Diversification sur plus de 1 000 sociétés de tous les secteurs")

    add("defensive", "Valeur défensive", _best(DEFENSIVE, exclude | {o["symbol"] for o in out}, limit=len(DEFENSIVE)),
        "Activité peu sensible à la conjoncture (consommation de base, santé, énergie régulée)")
    return out


# ---------------------------------------------------------------- sources
def sources_used(full: dict) -> list[dict]:
    seen, out = set(), []

    def add(name, module, ok=True):
        if name not in seen and ok:
            seen.add(name)
            out.append({"name": name, "module": module})

    for s in [{"name": full.get("quote_source")}] if full.get("quote_source") else []:
        add(s["name"], "Cours")
    for key, module in (("fundamentals", "Fondamental"), ("technical", "Technique"), ("sentiment", "Actualités")):
        for s in full[key].get("sources", []) or []:
            add(s["name"], module, s.get("ok"))
    return out


# ---------------------------------------------------------------- point d'entrée
def build(product_id: str, isin: str | None = None) -> dict | None:
    key = f"report:{product_id}"
    cached = cache.get(key, CACHE_TTL)
    if cached:
        return cached
    full = analysis.run(product_id, isin=isin)
    if full is None:
        return None
    if not full["decision"].get("available"):
        return {"available": False, "product": full["product"], "message": "Données insuffisantes pour un rapport."}
    from . import market
    q = market.get_quote(product_id, isin=isin) or {}
    full["quote_source"] = q.get("source")
    strengths, weaknesses = strengths_weaknesses(full)
    try:
        alts = alternatives(full)
    except Exception:
        logger.exception("Alternatives indisponibles pour %s", product_id)
        alts = []
    report = {
        "available": True,
        "product": full["product"],
        "price": full["quote"].get("price"),
        "decision": {k: full["decision"][k] for k in ("score", "signal", "components", "notes")} | {
            "buy": {k: full["decision"]["buy"][k] for k in ("level", "icon", "label")},
            "sell": {k: full["decision"]["sell"][k] for k in ("score", "level", "icon", "label")},
        },
        "summary": executive_summary(full),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "mm100": mm100_text(full),
        "stop_loss": stop_losses(full),
        "alternatives": alts,
        "sources": sources_used(full),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
    }
    cache.put(key, report, source="report")
    return report
