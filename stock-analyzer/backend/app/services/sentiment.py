"""Module 5 — Actualités et sentiment → score /10.

- Les 10 actualités les plus récentes (72 h) qui citent le produit, en français et en anglais.
- Sentiment de chaque titre 🟢 🟡 🔴 par un lexique financier FR/EN transparent
  (les mots qui ont pesé sont renvoyés à l'interface), avec gestion des négations.
- Événements à venir (résultats, dividende) signalés.
- Score de sentiment /10 = 5 + 5 × moyenne pondérée (titres récents plus lourds),
  ramenée vers 5 quand il y a peu d'articles.
"""
from __future__ import annotations

import logging
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from .sources import cache, news, yahoo

logger = logging.getLogger(__name__)

CACHE_TTL = 30 * 60
WINDOW_HOURS = 72
MAX_ITEMS = 10

# ---------------------------------------------------------------- lexique
# (motif sur texte normalisé : minuscules, sans accents, apostrophes droites ; poids)
POSITIVE = [
    # français
    (r"\bhausse", 1.0), (r"\bbondi", 1.5), (r"\bs'envol|\benvol", 1.5), (r"\bgrimp", 1.0),
    (r"\bprogress", 1.0), (r"\brebond", 1.0), (r"\brecord", 1.0), (r"\bflamb", 1.5),
    (r"\bdepass\w* (les |ses )?(attentes|previsions|estimations|consensus|objectifs)", 1.5),
    (r"\bsuperieur\w* aux (attentes|previsions|estimations)", 1.5), (r"\breleve", 1.0),
    (r"\bsurperform", 1.0), (r"\ba l'achat\b|\bconseil d'achat|\bpasse a l'achat", 1.5),
    (r"\bsolide", 0.8), (r"\boptimis", 1.0), (r"\bembellie", 1.0), (r"\bdecoll", 1.0),
    (r"\bfeu vert", 1.0), (r"\bapprob", 0.8), (r"\brachat d'actions", 0.5), (r"\bplus haut", 1.0),
    (r"\bgagn", 0.8), (r"\bsucces", 1.0), (r"\baccelere", 0.8), (r"\bcroissance", 0.5),
    (r"\bbenefice\w* en hausse", 1.0), (r"\bconfian", 0.5), (r"\bdynami", 0.5),
    # anglais
    (r"\bsurg", 1.5), (r"\bsoar", 1.5), (r"\bjump", 1.2), (r"\brall(y|ies|ied)", 1.0),
    (r"\bgains?\b|\bgained\b", 0.8), (r"\bris(e|es|ing)\b|\brose\b", 0.8),
    (r"\bbeats?\b|\btops? (estimates|expectations|forecasts)", 1.5), (r"\bupgrad", 1.5),
    (r"\braise[sd]? (its |the |full-year |annual )?(guidance|forecast|outlook|target)", 1.5),
    (r"\boutperform", 1.0), (r"\bstrong", 0.8), (r"\bbullish", 1.2), (r"\bbuy rating|\brated buy", 1.0),
    (r"\bboost", 0.8), (r"\bupbeat", 1.0), (r"\boptimis", 1.0), (r"\bapprov", 0.8),
    (r"\ball-time high|\brecord high", 1.0), (r"\brebound", 1.0), (r"\brecover", 0.8),
    (r"\b(one|two|three|six|\d+)-(week|month|year) high|\bhits? (a )?(new )?high", 1.0),
    (r"\bhigher\b", 0.6), (r"\bup \d|\bmoved up", 0.8), (r"\bdans le vert", 0.8), (r"\bpropuls", 1.2),
    (r"\bsoutenu", 0.5), (r"\braise[sd]? (its |the )?(price )?target", 1.2),
]
NEGATIVE = [
    # français
    (r"\bchut", 1.2), (r"\bplong", 1.5), (r"\bdegringol", 1.5), (r"\brecul", 1.0),
    (r"\bbaiss", 0.8), (r"\bs'effondr|\beffondr", 2.0), (r"\bdecroch", 1.2), (r"\bplomb", 1.2),
    (r"\bavertissement", 1.5), (r"\babaiss", 1.2), (r"\bdecevan|\bdecoit|\bdecu\b|\bdeception", 1.2),
    (r"\binferieur\w* aux (attentes|previsions)|\ben dessous des attentes|\bmanque (les|ses) (attentes|objectifs)", 1.5),
    (r"\bn'(a|ont) pas repondu aux attentes|\bpas repondu aux attentes", 1.5),
    (r"\bpertes?\b", 1.0), (r"\bdeficit", 1.0), (r"\blicenci|\bsuppressions? d'emplois|\bplan social", 1.2),
    (r"\benquete", 1.0), (r"\bamende", 1.0), (r"\bproces\b|\bplainte|\bpoursuit", 0.8),
    (r"\bfaillite|\bredressement judiciaire", 2.0), (r"\bdegrad", 1.2),
    (r"\ba la vente\b|\bconseil de vente|\bpasse a la vente", 1.5), (r"\bsous-perform", 1.0),
    (r"\binquiet", 1.0), (r"\bcrainte|\bcraint", 1.0), (r"\bscandale|\bfraude", 1.5), (r"\bgreve", 0.8),
    (r"\bralentiss", 0.8), (r"\brecession", 1.0), (r"\bplus bas", 1.0), (r"\bdevisse", 1.5),
    (r"\btrou d'air", 1.2), (r"\betrill", 1.5), (r"\bsanction", 1.0), (r"\bpanique", 1.5),
    (r"\bsous pression", 1.0), (r"\bdifficult", 0.8), (r"\bmauvais", 1.0), (r"\bpenalis", 1.0),
    (r"\bpire\b", 1.2), (r"\bs'interroge|\binterrog", 0.5),
    # anglais
    (r"\bplung", 1.5), (r"\btumbl", 1.5), (r"\bsink|\bsank\b", 1.2), (r"\bslump", 1.5),
    (r"\bfall(s|ing)?\b|\bfell\b", 1.0), (r"\bdrops?\b|\bdropp", 1.0), (r"\bslid(e|es|ing)?\b", 1.0),
    (r"\bmiss(es|ed)?\b", 1.5), (r"\bdowngrad", 1.5),
    (r"\bcuts? (its |the |full-year )?(20\d\d )?(price )?(guidance|forecast|outlook|target|jobs)", 1.5),
    (r"\blower(s|ed)? (its |the )?(20\d\d )?(price )?(guidance|forecast|outlook|target)", 1.5), (r"\bwarn", 1.2),
    (r"\bweak", 1.0), (r"\bloss(es)?\b", 1.0), (r"\blawsuit", 1.0), (r"\bprobe\b", 1.0),
    (r"\binvestigat", 1.0), (r"\blayoff", 1.2), (r"\brecall", 1.0), (r"\bbankrupt", 2.0),
    (r"\bbearish", 1.2), (r"\bsell-?off", 1.5), (r"\bcrash", 2.0), (r"\bfears?\b", 1.0),
    (r"\bconcern", 0.8), (r"\bdeclin", 1.0), (r"\bplummet", 2.0), (r"\bdisappoint", 1.2),
    (r"\bslash", 1.2), (r"\bworst\b", 1.5), (r"\bbrutal", 1.5), (r"\bfails? to meet|\bfall short", 1.5),
    (r"\bunder pressure", 1.0),
    (r"\b(one|two|three|six|\d+)-(week|month|year) low|\blowest\b", 1.0),
    (r"\b(shares|stocks?) (lower|down)\b|\bdown \d|\bdown by\b|\bmoved down", 1.0),
    (r"\blos(e|es|ing)\b|\blost\b", 1.0), (r"\bdans le rouge", 0.8),
]
NEGATION = re.compile(r"\b(pas|ne|n'|not|no|sans|never|without)\b")
EVENT_TAGS = [
    ("Résultats", r"\bresultats|\bearnings|\bchiffre d'affaires|\brevenue|\btrimestr|\bquarter"),
    ("Dividende", r"\bdividend"),
    ("Analyste", r"\bobjectif de cours|\bprice target|\bupgrad|\bdowngrad|\banalyst|\brecommandation"),
    ("Rachat / fusion", r"\bacqui|\brachat|\bfusion|\bmerger|\btakeover|\bopa\b"),
    ("Justice", r"\bproces|\bplainte|\blawsuit|\benquete|\bprobe|\bjustice"),
]
# En anglais, un nom européen peut désigner autre chose (Solvay, NY…) : on exige un mot boursier
FINANCE_CONTEXT = re.compile(
    r"\b(stock|shares?|target|guidance|earnings|results|revenue|profit|sales|investors?|dividend|ceo|"
    r"analysts?|market|acquisition|deal|outlook|forecast|eur|percent|%|quarter|buyback|rating)\b|%"
)
NOISE = re.compile(
    r"\bcours action\b|\bcotation bourse\b|^actualites\b|transactions sur actions propres|"
    r"droits de vote|nombre total d'actions|\bstock price\b.*\bquote\b"
)


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("`", "'")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def score_title(title: str) -> dict:
    """Sentiment d'un titre ∈ [−1 ; 1] + mots déclencheurs."""
    t = normalize(title)
    total, hits = 0.0, []
    for patterns, sign in ((POSITIVE, 1), (NEGATIVE, -1)):
        for pattern, weight in patterns:
            for m in re.finditer(pattern, t):
                before = t[max(0, m.start() - 25):m.start()]
                negated = bool(NEGATION.search(before)) and not re.search(r"\bpas repondu|\bne parvient", m.group())
                value = sign * weight * (-0.7 if negated else 1)
                total += value
                hits.append({"word": m.group().strip(), "value": round(value, 2)})
    score = math.tanh(total / 2)
    label = "positif" if score > 0.15 else "negatif" if score < -0.15 else "neutre"
    return {"score": round(score, 3), "label": label, "hits": hits}


def tags_for(title: str) -> list[str]:
    t = normalize(title)
    return [name for name, pattern in EVENT_TAGS if re.search(pattern, t)]


# ---------------------------------------------------------------- nom recherché
LEGAL = re.compile(
    r"[\s,]+(inc|corp|corporation|sa|s\.a|nv|n\.v|plc|ag|se|ltd|limited|group|groupe|holdings?|co|company|"
    r"societe europeenne|soci[eé]t[eé] europ[eé]enne|ord|class [a-c])\.?$", re.I
)


def clean_name(name: str) -> str:
    n = name.split(" - ")[0].split(",")[0].strip()
    previous = None
    while previous != n:
        previous, n = n, LEGAL.sub("", n).strip()
    first = n.split()[0] if n else n
    words = n.split()
    if len(first) >= 3 and first.isupper() and first.isalpha() and len(words) > 1 and words[1].isalpha():
        return first  # « LVMH Moët Hennessy » → « LVMH »
    return n


def search_term(product: dict, derivative: dict | None = None, extra: dict | None = None) -> str | None:
    kind = product.get("type")
    if kind in ("TURBO", "WARRANT"):
        return clean_name((derivative or {}).get("underlying") or "") or None
    if kind == "CRYPTO":
        return re.sub(r"\s+(EUR|USD|GBP|CHF)$", "", product.get("name") or "").strip() or None
    if kind == "ETF" and extra and extra.get("index"):
        return extra["index"]
    return clean_name(product.get("name") or "") or None


# ---------------------------------------------------------------- événements
def upcoming_events(symbol: str | None, days: int = 30) -> list[dict]:
    if not symbol:
        return []
    cal = yahoo.calendar(symbol) or {}
    today = date.today()
    out = []
    for key, label in (("Earnings Date", "Résultats trimestriels"), ("Ex-Dividend Date", "Détachement du dividende"),
                       ("Dividend Date", "Versement du dividende")):
        value = cal.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date) and 0 <= (value - today).days <= days:
            out.append({"type": key, "label": label, "date": value.isoformat(), "days": (value - today).days})
    return sorted(out, key=lambda e: e["days"])


# ---------------------------------------------------------------- point d'entrée
def analyze(product: dict, derivative: dict | None = None, extra: dict | None = None,
            events_symbol: str | None = None) -> dict:
    """Pour un turbo/warrant PUT, le score est inversé : de mauvaises nouvelles sur le
    sous-jacent sont favorables au put."""
    key = f"senti:{product['id']}"
    cached = cache.get(key, CACHE_TTL)
    if cached:
        return cached
    term = search_term(product, derivative, extra)
    if not term:
        return {"applicable": False, "score": None, "items": [], "events": [], "sources": [],
                "notes": ["Impossible de déterminer le nom à rechercher dans l'actualité."]}

    sources, raw = [], []
    for lang in ("fr", "en"):
        items = news.google_news(term, lang)
        sources.append({"name": f"{news.GOOGLE} ({lang.upper()})", "ok": items is not None})
        raw += items or []
        api_items = news.newsapi(term, lang)
        if api_items is not None:
            sources.append({"name": f"{news.NEWSAPI} ({lang.upper()})", "ok": True})
            raw += api_items

    needle = normalize(term)
    us_or_crypto = product.get("currency") == "USD" or product.get("type") == "CRYPTO"
    now = datetime.now(timezone.utc)
    seen, selected = set(), []
    for it in sorted(raw, key=lambda x: x["published"] or now - timedelta(days=99), reverse=True):
        title_n = normalize(it["title"])
        if not it["title"] or not re.search(rf"\b{re.escape(needle)}\b", title_n) or NOISE.search(title_n):
            continue
        if it["lang"] == "en" and not us_or_crypto and not FINANCE_CONTEXT.search(title_n):
            continue
        if it["published"] and now - it["published"] > timedelta(hours=WINDOW_HOURS):
            continue
        dedup = re.sub(r"[^a-z0-9 ]", "", title_n)[:60]
        if dedup in seen:
            continue
        seen.add(dedup)
        s = score_title(it["title"])
        age_h = (now - it["published"]).total_seconds() / 3600 if it["published"] else None
        selected.append({
            "title": it["title"], "url": it["url"], "source": it["source"], "lang": it["lang"],
            "published": it["published"].isoformat() if it["published"] else None,
            "age_hours": round(age_h, 1) if age_h is not None else None,
            "sentiment": s["label"], "sentiment_score": s["score"],
            "keywords": [h["word"] for h in s["hits"]][:4], "tags": tags_for(it["title"]),
        })
        if len(selected) >= MAX_ITEMS:
            break

    # Score : moyenne pondérée par la fraîcheur, ramenée vers 5 si peu d'articles
    notes = []
    if selected:
        weights = [1.0 if (i["age_hours"] or 0) < 24 else 0.7 if (i["age_hours"] or 0) < 48 else 0.5 for i in selected]
        avg = sum(w * i["sentiment_score"] for w, i in zip(weights, selected)) / sum(weights)
        confidence = min(1.0, len(selected) / 5)
        score = max(0.0, min(10.0, 5 + 5 * avg * confidence))
        if len(selected) < 5:
            notes.append(f"Seulement {len(selected)} article(s) en 72 h : score ramené vers la neutralité.")
    else:
        score = 5.0
        notes.append("Aucune actualité récente trouvée : sentiment neutre par défaut.")

    events = upcoming_events(events_symbol)
    for e in events:
        if e["type"] == "Earnings Date" and e["days"] <= 2:
            when = "aujourd'hui" if e["days"] == 0 else f"dans {e['days']} jour(s)"
            notes.append(f"💰 Résultats trimestriels {when} : forte volatilité attendue.")

    inverse = (derivative or {}).get("direction") == "PUT"
    underlying_score = None
    if inverse:
        underlying_score = round(score, 1)
        score = 10 - score
        notes.append(f"Turbo PUT : de mauvaises nouvelles sur {term} lui sont favorables (score inversé).")

    counts = {k: sum(1 for i in selected if i["sentiment"] == k) for k in ("positif", "neutre", "negatif")}
    result = {
        "applicable": True,
        "term": term,
        "score": round(score, 1),
        "inverse": inverse,
        "underlying_score": underlying_score,
        "verdict": "Positif" if score >= 6 else "Négatif" if score <= 4 else "Neutre",
        "counts": counts,
        "items": selected,
        "events": events,
        "sources": sources,
        "notes": notes,
        "window_hours": WINDOW_HOURS,
    }
    cache.put(key, result, source="sentiment")
    return result
