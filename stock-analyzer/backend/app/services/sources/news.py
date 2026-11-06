"""Priorité 5 — Actualités : Google News RSS (gratuit) + NewsAPI (si clé dans .env)."""
from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime, timedelta, timezone

import feedparser

from ...config import get_settings
from .http import fetch_text

logger = logging.getLogger(__name__)

GOOGLE = "Google News"
NEWSAPI = "NewsAPI"

EDITIONS = {
    "fr": {"hl": "fr", "gl": "BE", "ceid": "BE:fr"},
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
}


def google_news(query: str, lang: str = "fr", days: int = 3) -> list[dict] | None:
    """Articles des `days` derniers jours. None si la source ne répond pas."""
    text = fetch_text("https://news.google.com/rss/search", params={"q": f"{query} when:{days}d", **EDITIONS[lang]})
    if text is None:
        return None
    feed = feedparser.parse(text)
    items = []
    for e in feed.entries:
        published = None
        if e.get("published_parsed"):
            published = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
        source = (e.get("source") or {}).get("title")
        title = e.get("title", "")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        items.append({"title": title.strip(), "url": e.get("link"), "source": source,
                      "published": published, "lang": lang, "via": GOOGLE})
    return items


def newsapi(query: str, lang: str = "fr", days: int = 3) -> list[dict] | None:
    key = get_settings().newsapi_key
    if not key:
        return None
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    text = fetch_text("https://newsapi.org/v2/everything", params={
        "q": f'"{query}"', "from": since, "language": lang, "sortBy": "publishedAt",
        "pageSize": 30, "apiKey": key,
    })
    if text is None:
        return None
    try:
        articles = json.loads(text).get("articles", [])
    except ValueError:
        return None
    items = []
    for a in articles:
        try:
            published = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            published = None
        items.append({"title": (a.get("title") or "").strip(), "url": a.get("url"),
                      "source": (a.get("source") or {}).get("name"), "published": published,
                      "lang": lang, "via": NEWSAPI})
    return items
