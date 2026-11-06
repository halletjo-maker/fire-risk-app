"""Rapport mensuel des portefeuilles fictifs, envoyé par mail le 1er du mois (mois précédent).

Pour chaque portefeuille : valeur en début et fin de mois, performance du mois et depuis le
départ, achats et ventes du mois (meilleure / pire vente, taux de réussite, frais), lignes
ouvertes, comparaison avec un ETF MSCI World. Un envoi réussi est mémorisé : pas de doublon.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..database import get_conn
from . import paper
from .mail import sender
from .sources import yahoo

logger = logging.getLogger(__name__)

BENCHMARK = ("IWDA.AS", "ETF MSCI World")
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
TZ = ZoneInfo("Europe/Brussels")


def previous_month(today: date | None = None) -> tuple[int, int]:
    today = today or datetime.now(TZ).date()
    return (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)


def _bounds(year: int, month: int) -> tuple[str, str]:
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


_bench_cache: dict = {}


def benchmark(year: int, month: int, since: str | None = None) -> float | None:
    """Performance de l'ETF MSCI World sur le mois (ou depuis `since`, ex. date de création)."""
    first, last = _bounds(year, month)
    first = max(first, since or first)
    key = (BENCHMARK[0], year, month)
    if key not in _bench_cache:
        _bench_cache[key] = yahoo.history(BENCHMARK[0], period="6mo")
    df = _bench_cache[key]
    if df is None or df.empty:
        return None
    closes = df["close"].dropna()
    before = closes[closes.index < first]
    inside = closes[(closes.index >= first) & (closes.index <= f"{last} 23:59")]
    if before.empty or inside.empty:
        return None
    return round((float(inside.iloc[-1]) / float(before.iloc[-1]) - 1) * 100, 2)


def portfolio_month(conn, pf, year: int, month: int) -> dict | None:
    """Chiffres du mois pour un portefeuille, ou None s'il n'existait pas encore."""
    first, last = _bounds(year, month)
    if pf["created_at"][:10] > last:
        return None
    start_row = conn.execute("SELECT value_eur FROM portfolio_values WHERE portfolio_id = ? AND day < ? "
                             "ORDER BY day DESC LIMIT 1", (pf["id"], first)).fetchone()
    end_row = conn.execute("SELECT value_eur, day FROM portfolio_values WHERE portfolio_id = ? AND day <= ? "
                           "ORDER BY day DESC LIMIT 1", (pf["id"], last)).fetchone()
    start = start_row["value_eur"] if start_row else pf["initial_cash"]
    end = end_row["value_eur"] if end_row else start
    month_start = f"{first} 00:00:00"
    month_end = f"{last} 23:59:59"
    buys = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(entry_fee), 0) AS fees FROM portfolio_positions "
                        "WHERE portfolio_id = ? AND entry_at BETWEEN ? AND ?", (pf["id"], month_start, month_end)).fetchone()
    sells = [dict(r) for r in conn.execute(
        "SELECT name, symbol, pnl_eur, exit_reason, exit_fee, "
        "ROUND((exit_price * qty / exit_fx - exit_fee) / (entry_price * qty / entry_fx + entry_fee) * 100 - 100, 2) AS pnl_pct "
        "FROM portfolio_positions WHERE portfolio_id = ? AND status = 'CLOSED' AND exit_at BETWEEN ? AND ? "
        "ORDER BY pnl_eur DESC", (pf["id"], month_start, month_end))]
    summary = paper.summary(conn, pf)
    return {
        "name": pf["name"], "created_in_month": pf["created_at"][:10] >= first,
        "created_at": pf["created_at"][:10], "initial": pf["initial_cash"],
        "start": round(start, 2), "end": round(end, 2),
        "month_pct": round((end / start - 1) * 100, 2) if start else None,
        "total_pct": round((end / pf["initial_cash"] - 1) * 100, 2),
        "buys": buys["n"], "sells": len(sells), "wins": sum(1 for s in sells if (s["pnl_eur"] or 0) > 0),
        "realized": round(sum(s["pnl_eur"] or 0 for s in sells), 2),
        "fees": round(buys["fees"] + sum(s["exit_fee"] or 0 for s in sells), 2),
        "best": sells[0] if sells else None, "worst": sells[-1] if len(sells) > 1 else None,
        "benchmark": benchmark(year, month, pf["created_at"][:10]) if pf["created_at"][:10] >= first else None,
        "open": sorted(summary["positions"], key=lambda p: p["pnl_pct"] or 0, reverse=True),
    }


def build(user_id: int, year: int, month: int, until_day: int | None = None) -> dict | None:
    """Rapport d'un mois complet, ou du 1er au `until_day` inclus (mois en cours, envoi à la demande)."""
    with get_conn() as conn:
        user = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        pfs = conn.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
        items = [x for x in (portfolio_month(conn, pf, year, month) for pf in pfs) if x]
    if user is None or not items:
        return None
    label = f"{MONTHS[month - 1]} {year}"
    span = "sur le mois"
    if until_day:
        label += " (le 1er)" if until_day == 1 else f" (du 1er au {until_day})"
        span = "depuis le 1er du mois"
    return {"email": user["email"], "year": year, "month": month, "label": label, "span": span, "partial": bool(until_day),
            "portfolios": items, "benchmark": benchmark(year, month)}


# ── Mise en forme ───────────────────────────────────────────────────────────

def _eur(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if v < 0 else ''}{s} €"


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.2f} %".replace(".", ",")


def _color(v: float | None) -> str:
    return "#00FF88" if (v or 0) > 0 else "#FF4444" if (v or 0) < 0 else "#8B949E"


def render(report: dict) -> tuple[str, str, str]:
    """(objet, texte, html)."""
    label, bench = report["label"], report["benchmark"]
    subject = f"📊 Rapport {label} — portefeuilles fictifs"
    lines = [f"Rapport mensuel — {label}", ""]
    cards = []
    for p in report["portfolios"]:
        since = (f"depuis sa création le {p['created_at'][8:10]}/{p['created_at'][5:7]}" if p["created_in_month"]
                 else report.get("span", "sur le mois"))
        lines += [
            f"■ {p['name']}",
            f"  Valeur : {_eur(p['start'])} → {_eur(p['end'])} ({_pct(p['month_pct'])} {since})",
            f"  Depuis le départ ({_eur(p['initial'])}) : {_pct(p['total_pct'])}",
            *([f"  Repère {BENCHMARK[1]} sur la même période : {_pct(p['benchmark'])}"] if p.get("benchmark") is not None else []),
            f"  Achats : {p['buys']} · ventes : {p['sells']} ({p['wins']} gagnante(s)) · "
            f"gains réalisés : {_eur(p['realized'])} · frais : {_eur(p['fees'])}",
        ]
        if p["best"]:
            lines.append(f"  Meilleure vente : {p['best']['name']} {_pct(p['best']['pnl_pct'])} ({p['best']['exit_reason']})")
        if p["worst"]:
            lines.append(f"  Pire vente : {p['worst']['name']} {_pct(p['worst']['pnl_pct'])} ({p['worst']['exit_reason']})")
        lines.append(f"  Lignes ouvertes : {len(p['open'])}")
        for o in p["open"][:10]:
            lines.append(f"    · {o['name']} ({o['symbol']}) {_pct(o['pnl_pct'])}")
        lines.append("")

        rows = "".join(
            f'<tr><td style="padding:4px 0;color:#E6EDF3;font-size:13px">{escape(o["name"])} '
            f'<span style="color:#8B949E">{escape(o["symbol"])}</span></td>'
            f'<td align="right" style="padding:4px 0;font-size:13px;color:{_color(o["pnl_pct"])}">{_pct(o["pnl_pct"])}</td></tr>'
            for o in p["open"][:10])
        extra = ""
        if p["best"]:
            extra += (f'<p style="margin:6px 0 0;color:#8B949E;font-size:13px">Meilleure vente : '
                      f'<b style="color:#E6EDF3">{escape(p["best"]["name"])}</b> '
                      f'<span style="color:{_color(p["best"]["pnl_pct"])}">{_pct(p["best"]["pnl_pct"])}</span></p>')
        if p["worst"]:
            extra += (f'<p style="margin:2px 0 0;color:#8B949E;font-size:13px">Pire vente : '
                      f'<b style="color:#E6EDF3">{escape(p["worst"]["name"])}</b> '
                      f'<span style="color:{_color(p["worst"]["pnl_pct"])}">{_pct(p["worst"]["pnl_pct"])}</span></p>')
        cards.append(f"""
<tr><td style="padding:16px 20px;border-top:1px solid #30363D">
<p style="margin:0 0 4px;color:#E6EDF3;font-size:16px;font-weight:700">{escape(p['name'])}</p>
<p style="margin:0;color:#E6EDF3;font-size:24px;font-weight:700">{_eur(p['end'])}
 <span style="font-size:15px;color:{_color(p['month_pct'])}">{_pct(p['month_pct'])}</span></p>
<p style="margin:2px 0 8px;color:#8B949E;font-size:13px">{_eur(p['start'])} → {_eur(p['end'])} {since} ·
 depuis le départ {_pct(p['total_pct'])}</p>
{f'<p style="margin:0 0 4px;color:#8B949E;font-size:13px">Repère {BENCHMARK[1]} sur la même période : <span style="color:{_color(p["benchmark"])}">{_pct(p["benchmark"])}</span></p>' if p.get("benchmark") is not None else ''}
<p style="margin:0;color:#8B949E;font-size:13px">{p['buys']} achat(s) · {p['sells']} vente(s), {p['wins']} gagnante(s) ·
 gains réalisés <span style="color:{_color(p['realized'])}">{_eur(p['realized'])}</span> · frais {_eur(p['fees'])}</p>
{extra}
<p style="margin:12px 0 4px;color:#8B949E;font-size:12px;letter-spacing:.06em;text-transform:uppercase">
Lignes ouvertes ({len(p['open'])})</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows or '<tr><td style="color:#8B949E;font-size:13px">Aucune</td></tr>'}</table>
</td></tr>""")

    bench_txt = (f"Repère : {BENCHMARK[1]} {_pct(bench)} {'depuis le 1er du mois' if report.get('partial') else 'sur le mois complet'}."
                 if bench is not None
                 else "Repère MSCI World indisponible ce mois-ci.")
    url = get_settings().app_public_url.rstrip("/")
    lines += [bench_txt, "", f"Ouvrir l'application : {url}", "",
              "Simulation avec de l'argent virtuel. Pas un conseil en investissement (MiFID II)."]
    html = f"""<!doctype html><html lang="fr"><body style="margin:0;background:#0D1117;font-family:Inter,Roboto,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0D1117;padding:16px 0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#161B22;border:1px solid #30363D;border-radius:12px">
<tr><td style="padding:20px 20px 12px">
<p style="margin:0 0 4px;color:#8B949E;font-size:12px;letter-spacing:.08em;text-transform:uppercase">📊 Rapport mensuel</p>
<p style="margin:0;color:#E6EDF3;font-size:20px;font-weight:700">Portefeuilles fictifs — {escape(label)}</p>
<p style="margin:6px 0 0;color:#8B949E;font-size:13px">{escape(bench_txt)}</p>
</td></tr>
{''.join(cards)}
<tr><td style="padding:16px 20px;border-top:1px solid #30363D">
<a href="{escape(url)}" style="display:inline-block;background:#00FF88;color:#0D1117;font-weight:700;text-decoration:none;padding:10px 16px;border-radius:8px">Ouvrir l'application</a>
<p style="margin:12px 0 0;color:#8B949E;font-size:11px;line-height:1.5">Simulation avec de l'argent virtuel, sur les derniers
cours connus. Les performances passées ne préjugent pas des performances futures. Pas un conseil en investissement (MiFID II).
Pour ne plus recevoir ce rapport : Profil → Rapport mensuel.</p>
</td></tr></table></td></tr></table></body></html>"""
    return subject, "\n".join(lines), html


# ── Envoi ───────────────────────────────────────────────────────────────────

def _sent_key(user_id: int, year: int, month: int) -> str:
    return f"monthly_report:{user_id}:{year:04d}-{month:02d}"


def send_for_user(user_id: int, year: int, month: int, force: bool = False, until_day: int | None = None) -> dict:
    with get_conn() as conn:
        if not force and conn.execute("SELECT 1 FROM app_settings WHERE key = ?",
                                      (_sent_key(user_id, year, month),)).fetchone():
            return {"sent": False, "status": "Déjà envoyé"}
    report = build(user_id, year, month, until_day)
    if report is None:
        return {"sent": False, "status": "Aucun portefeuille fictif sur cette période"}
    subject, text, html = render(report)
    result = sender.send(report["email"], subject, text, html)
    if result["delivered"] and not until_day:  # un rapport partiel ne remplace pas celui du 1er
        with get_conn() as conn:
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, datetime('now')) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (_sent_key(user_id, year, month),))
    return {"sent": result["delivered"], "status": result["status"], "label": report["label"], "email": report["email"]}


def send_all(today: date | None = None) -> int:
    """Le 1er (et les 2 jours suivants en cas d'échec) : rapport du mois précédent à chaque abonné."""
    year, month = previous_month(today)
    with get_conn() as conn:
        users = [r["id"] for r in conn.execute(
            "SELECT DISTINCT u.id FROM users u JOIN portfolios p ON p.user_id = u.id WHERE u.monthly_report = 1")]
    sent = 0
    for uid in users:
        try:
            sent += send_for_user(uid, year, month)["sent"]
        except Exception:
            logger.exception("Rapport mensuel impossible pour l'utilisateur %s", uid)
    logger.info("Rapports mensuels %02d/%d : %s envoyé(s)", month, year, sent)
    return sent
