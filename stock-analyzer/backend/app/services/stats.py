"""Compteur de visites du site public, sans cookie ni service extérieur.

Une visite = une page publique affichée par un navigateur (les robots et les membres connectés
ne comptent pas). Un « visiteur » est reconnu le temps d'une journée grâce à une empreinte
irréversible (sel aléatoire du jour + adresse IP + navigateur) ; elle est effacée après 2 jours.
Seuls des totaux par jour sont gardés : pages vues, visiteurs, provenance.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, timedelta
from urllib.parse import urlparse

from ..database import get_conn

BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|curl|wget|python|headless",
                  re.I)
SOURCE_RE = re.compile(r"[^a-z0-9.\-]")
KNOWN = {"google": "Google", "bing": "Bing", "duckduckgo": "DuckDuckGo", "reddit": "Reddit", "facebook": "Facebook",
         "instagram": "Instagram", "linkedin": "LinkedIn", "t.co": "X (Twitter)", "x.com": "X (Twitter)",
         "youtube": "YouTube", "tiktok": "TikTok", "whatsapp": "WhatsApp", "wa.me": "WhatsApp", "messenger": "Messenger"}


def _today() -> str:
    return date.today().isoformat()


def _salt(conn, day: str) -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'stats_salt'").fetchone()
    if row and row["value"].startswith(day + "|"):
        return row["value"].split("|", 1)[1]
    salt = secrets.token_hex(16)  # nouveau jour : nouveau sel, les anciennes empreintes deviennent inutilisables
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('stats_salt', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (f"{day}|{salt}",))
    conn.execute("DELETE FROM daily_visitors WHERE day < ?", ((date.fromisoformat(day) - timedelta(days=1)).isoformat(),))
    return salt


def source_of(ref_param: str | None, referrer: str | None, own_host: str | None) -> str | None:
    """« Reddit », « Google »… ; None pour une navigation interne au site ; « Direct » sans origine connue."""
    raw = (ref_param or "").strip().lower()
    if raw:
        raw = SOURCE_RE.sub("", raw)[:30]
        return next((v for k, v in KNOWN.items() if k in raw), raw or "Direct")
    host = (urlparse(referrer or "").hostname or "").lower().removeprefix("www.")
    if not host:
        return "Direct"
    if own_host and host == own_host.lower().removeprefix("www."):
        return None
    return next((v for k, v in KNOWN.items() if k in host), host[:40])


def record(path: str, ip: str, agent: str | None, referrer: str | None, ref_param: str | None,
           own_host: str | None) -> bool:
    if not agent or BOTS.search(agent):
        return False
    day = _today()
    with get_conn() as conn:
        digest = hashlib.sha256(f"{_salt(conn, day)}|{ip}|{agent}".encode()).hexdigest()[:20]
        new = conn.execute("INSERT OR IGNORE INTO daily_visitors (day, hash) VALUES (?, ?)", (day, digest)).rowcount
        conn.execute("INSERT INTO site_stats (day, visitors, views) VALUES (?, ?, 1) ON CONFLICT(day) DO UPDATE SET "
                     "visitors = visitors + excluded.visitors, views = views + 1", (day, new))
        conn.execute("INSERT INTO site_page_views (day, path, views) VALUES (?, ?, 1) "
                     "ON CONFLICT(day, path) DO UPDATE SET views = views + 1", (day, path))
        src = source_of(ref_param, referrer, own_host)
        if new and src:
            conn.execute("INSERT INTO site_sources (day, source, visitors) VALUES (?, ?, 1) "
                         "ON CONFLICT(day, source) DO UPDATE SET visitors = visitors + 1", (day, src))
    return True


def summary(days: int, titles: dict) -> dict:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_conn() as conn:
        daily = {r["day"]: dict(r) for r in conn.execute(
            "SELECT day, visitors, views FROM site_stats WHERE day >= ? ORDER BY day", (since,))}
        pages = conn.execute("SELECT path, SUM(views) AS views FROM site_page_views WHERE day >= ? "
                             "GROUP BY path ORDER BY views DESC LIMIT 10", (since,)).fetchall()
        sources = conn.execute("SELECT source, SUM(visitors) AS visitors FROM site_sources WHERE day >= ? "
                               "GROUP BY source ORDER BY visitors DESC LIMIT 8", (since,)).fetchall()
        requests = conn.execute("SELECT COUNT(*) FROM invite_requests").fetchone()[0]
    series = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        series.append(daily.get(d, {"day": d, "visitors": 0, "views": 0}))
    today = series[-1]
    return {
        "days": days,
        "visitors": sum(x["visitors"] for x in series), "views": sum(x["views"] for x in series),
        "today": {"visitors": today["visitors"], "views": today["views"]},
        "series": series,
        "pages": [{"path": r["path"], "title": (titles.get(r["path"]) or {}).get("title", r["path"]).replace(" · MM100", ""),
                   "views": r["views"]} for r in pages],
        "sources": [dict(r) for r in sources],
        "pending_requests": requests,
    }
