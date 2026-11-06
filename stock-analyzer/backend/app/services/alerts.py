"""Module 9 — Alertes mail sur les produits des watchlists.

Types (configurables par produit) :
    SIGNAL_FORT            score global passe ≥ 7,5
    ALERTE_BAISSE          score global passe < 5
    MM100_CROISEMENT       le prix croise la MM100 (hausse ou baisse)
    ACTUALITE_IMPORTANTE   sentiment très négatif (score < 3)
    RESULTATS_A_VENIR      résultats trimestriels dans moins de 48 h

Un mail part quand la condition DEVIENT vraie (et non à chaque vérification tant qu'elle
le reste). La fréquence fixe un maximum : immédiate | 1×/jour | 1×/semaine. Une alerte
déclenchée trop tôt reste en attente et part à la fin du délai si la condition tient.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from ..config import get_settings
from ..database import get_conn
from . import analysis
from .fundamentals import num, pct
from .mail import sender

logger = logging.getLogger(__name__)

TYPES = {
    "SIGNAL_FORT": {"icon": "🚨", "label": "Signal fort", "help": "Le score global passe à 7,5/10 ou plus (conditions favorables)."},
    "ALERTE_BAISSE": {"icon": "📉", "label": "Alerte baisse", "help": "Le score global passe sous 5/10 (conditions défavorables)."},
    "MM100_CROISEMENT": {"icon": "📊", "label": "Croisement MM100", "help": "Le prix croise sa moyenne mobile 100 jours, à la hausse ou à la baisse."},
    "ACTUALITE_IMPORTANTE": {"icon": "📰", "label": "Actualité importante", "help": "Sentiment très négatif détecté dans l'actualité (score < 3/10)."},
    "RESULTATS_A_VENIR": {"icon": "💰", "label": "Résultats à venir", "help": "Résultats trimestriels dans moins de 48 heures."},
}
FREQUENCIES = {"immediate": timedelta(0), "daily": timedelta(days=1), "weekly": timedelta(days=7)}
FREQUENCY_LABELS = {"immediate": "Immédiate", "daily": "1 × par jour", "weekly": "1 × par semaine"}


def new_token() -> str:
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------- conditions
def evaluate(alert_type: str, last_state: str | None, full: dict) -> tuple[bool, str | None, dict]:
    """Renvoie (déclencher ?, nouvel état, contexte pour le mail)."""
    d, t, s = full["decision"], full["technical"], full["sentiment"]
    score = d.get("score") if d.get("available") else None

    if alert_type in ("SIGNAL_FORT", "ALERTE_BAISSE"):
        if score is None:
            return False, last_state, {}
        on = score >= 7.5 if alert_type == "SIGNAL_FORT" else score < 5
        state = "ON" if on else "OFF"
        return on and last_state != "ON", state, {"score": score}

    if alert_type == "MM100_CROISEMENT":
        mm = t.get("mm100") if t.get("applicable") else None
        if not mm:
            return False, last_state, {}
        state = "ABOVE" if mm["above"] else "BELOW"
        if last_state is None:  # première vérification : on ne prévient que d'un croisement récent
            crossed = bool(mm.get("cross"))
        else:
            crossed = state != last_state
        direction = "HAUSSIER" if mm["above"] else "BAISSIER"
        return crossed, state, {"direction": direction, "mm": mm}

    if alert_type == "ACTUALITE_IMPORTANTE":
        if not s.get("applicable"):
            return False, last_state, {}
        raw = s.get("underlying_score") if s.get("inverse") else s.get("score")  # sentiment brut des titres
        on = raw is not None and raw < 3 and bool(s.get("items"))
        worst = min(s.get("items") or [{}], key=lambda i: i.get("sentiment_score", 0))
        return on and last_state != "ON", "ON" if on else "OFF", {"sentiment": raw, "title": worst.get("title")}

    if alert_type == "RESULTATS_A_VENIR":
        e = next((e for e in s.get("events", []) if e["type"] == "Earnings Date" and 0 <= e["days"] <= 2), None)
        if not e:
            return False, last_state, {}
        return last_state != e["date"], e["date"], {"date": e["date"], "days": e["days"]}

    return False, last_state, {}


def frequency_allows(frequency: str, last_triggered_at: str | None, now: datetime) -> bool:
    if not last_triggered_at:
        return True
    last = datetime.strptime(last_triggered_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return now - last >= FREQUENCIES.get(frequency, timedelta(0))


# ---------------------------------------------------------------- mail
def compose(alert_type: str, ctx: dict, full: dict, token: str, watchlist: str) -> tuple[str, str, str]:
    p, q, d, t = full["product"], full["quote"], full["decision"], full["technical"]
    name = f"{p['name']} ({p.get('symbol') or p.get('isin') or ''})".replace(" ()", "")
    score = d.get("score")
    sc = num(score, 1) if score is not None else "–"
    if alert_type == "SIGNAL_FORT":
        tag, headline = "SIGNAL ACHAT ✅", f"Le score global passe à {sc}/10 : conditions favorables à l'achat."
        subject = f"[{tag}] {name} — Score {sc}/10"
    elif alert_type == "ALERTE_BAISSE":
        tag, headline = "ALERTE BAISSE 📉", f"Le score global passe à {sc}/10 : conditions défavorables."
        subject = f"[{tag}] {name} — Score {sc}/10"
    elif alert_type == "MM100_CROISEMENT":
        up = ctx["direction"] == "HAUSSIER"
        tag = f"MM100 ⚡ CROISEMENT {'HAUSSIER' if up else 'BAISSIER'}"
        headline = (f"Le prix vient de passer {'au-dessus' if up else 'sous'} sa moyenne mobile 100 jours "
                    f"({num(ctx['mm']['value'], 2)}).")
        subject = f"[{tag}] {name} — Score {sc}/10"
    elif alert_type == "ACTUALITE_IMPORTANTE":
        tag = "ACTUALITÉ 📰 NÉGATIVE"
        headline = f"Sentiment très négatif dans l'actualité ({num(ctx['sentiment'], 1)}/10)."
        subject = f"[{tag}] {name} — Sentiment {num(ctx['sentiment'], 1)}/10"
    else:
        tag = "RÉSULTATS 💰 DANS 48 H"
        date_fr = datetime.fromisoformat(ctx["date"]).strftime("%d/%m/%Y")
        headline = f"Résultats trimestriels attendus le {date_fr} : forte volatilité possible."
        subject = f"[{tag}] {name} — {date_fr}"

    mm = t.get("mm100") if t.get("applicable") else None
    lines = [
        headline,
        f"Score global : {sc}/10 — {d['buy']['icon']} {d['buy']['label']}" if d.get("available") else "Score global indisponible.",
        (f"Position vs MM100 : {'au-dessus' if mm['above'] else 'en dessous'} ({pct(mm['distance_pct'], 1, sign=True)})"
         if mm else "Position vs MM100 : non disponible."),
        f"Cours : {num(q.get('price'), 2)} {p.get('currency') or ''} ({pct(q.get('change_pct'), 2, sign=True)} aujourd'hui)".replace("  ", " "),
        (f"Titre marquant : « {ctx['title']} »" if ctx.get("title") else f"Watchlist : {watchlist}"),
    ][:5]
    base = get_settings().app_public_url.rstrip("/")
    link = f"{base}/?analyse={p['id']}"
    unsub = f"{base}/api/alerts/unsubscribe/{token}"
    text = "\n".join(lines) + f"\n\nVoir l'analyse complète : {link}\n\n—\nSe désinscrire de cette alerte : {unsub}\n" \
        "Aide à la décision automatisée, pas un conseil en investissement (MiFID II)."
    rows = "".join(f'<p style="margin:0 0 8px;color:#E6EDF3;font-size:15px;line-height:1.4">{escape(line)}</p>' for line in lines)
    html = f"""<!doctype html><html lang="fr"><body style="margin:0;background:#0D1117;font-family:Inter,Roboto,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0D1117;padding:16px 0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#161B22;border:1px solid #30363D;border-radius:12px">
<tr><td style="padding:20px 20px 8px">
<p style="margin:0 0 4px;color:#8B949E;font-size:12px;letter-spacing:.08em;text-transform:uppercase">{escape(TYPES[alert_type]['icon'])} {escape(TYPES[alert_type]['label'])}</p>
<h1 style="margin:0 0 14px;color:#FFFFFF;font-size:19px;line-height:1.3">{escape(name)}</h1>
{rows}
</td></tr>
<tr><td style="padding:8px 20px 20px">
<a href="{escape(link)}" style="display:inline-block;background:#00FF88;color:#0D1117;font-weight:700;text-decoration:none;padding:11px 18px;border-radius:8px">Voir l'analyse complète</a>
</td></tr>
<tr><td style="padding:14px 20px;border-top:1px solid #30363D;color:#8B949E;font-size:12px;line-height:1.5">
Aide à la décision automatisée — ne constitue pas un conseil en investissement (MiFID II).<br>
<a href="{escape(unsub)}" style="color:#8B949E">Se désinscrire de cette alerte</a>
</td></tr></table></td></tr></table></body></html>"""
    return subject, text, html


# ---------------------------------------------------------------- vérification
def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_all(now: datetime | None = None) -> int:
    """Vérifie toutes les alertes actives ; renvoie le nombre de mails envoyés/enregistrés."""
    now = now or _now()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.alert_type, a.frequency, a.last_state, a.last_triggered_at, a.unsubscribe_token,
                   i.product_id, i.name AS item_name, w.name AS watchlist, u.id AS user_id, u.email
            FROM alerts a
            JOIN watchlist_items i ON i.id = a.item_id
            JOIN watchlists w ON w.id = i.watchlist_id
            JOIN users u ON u.id = w.user_id
            WHERE a.enabled = 1 AND i.product_id IS NOT NULL
            ORDER BY i.product_id
            """
        ).fetchall()
    analyses: dict[str, dict | None] = {}
    sent = 0
    for r in rows:
        pid = r["product_id"]
        if pid not in analyses:
            try:
                analyses[pid] = analysis.run(pid)
            except Exception:
                logger.exception("Analyse impossible pour l'alerte %s", r["id"])
                analyses[pid] = None
        full = analyses[pid]
        if full is None:
            continue
        trigger, state, ctx = evaluate(r["alert_type"], r["last_state"], full)
        if trigger and not frequency_allows(r["frequency"], r["last_triggered_at"], now):
            continue  # en attente : l'état n'est pas mis à jour, l'alerte repartira après le délai
        if trigger:
            subject, text, html = compose(r["alert_type"], ctx, full, r["unsubscribe_token"], r["watchlist"])
            result = sender.send(r["email"], subject, text, html)
            sent += 1
            from . import push
            push.notify_later(r["user_id"], "alerts", subject, f"{r['item_name']} · watchlist « {r['watchlist']} »", "/")
            with get_conn() as conn:
                conn.execute(
                    "UPDATE alerts SET last_state = ?, last_triggered_at = ? WHERE id = ?",
                    (state, now.strftime("%Y-%m-%d %H:%M:%S"), r["id"]),
                )
                conn.execute(
                    "INSERT INTO alert_events (user_id, alert_id, alert_type, product_id, product, subject, delivered, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["user_id"], r["id"], r["alert_type"], pid, r["item_name"], subject,
                     1 if result["delivered"] else 0, result["status"]),
                )
            logger.info("Alerte %s (%s) : %s", r["alert_type"], r["item_name"], result["status"])
        elif state != r["last_state"]:
            with get_conn() as conn:
                conn.execute("UPDATE alerts SET last_state = ? WHERE id = ?", (state, r["id"]))
    return sent
