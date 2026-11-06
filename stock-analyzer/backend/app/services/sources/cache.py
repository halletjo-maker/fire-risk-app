"""Petit cache SQLite (table data_cache) pour limiter les appels aux sources."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from ...database import get_conn

logger = logging.getLogger(__name__)
_FMT = "%Y-%m-%d %H:%M:%S"


def get(key: str, max_age_seconds: int):
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT payload, fetched_at FROM data_cache WHERE cache_key = ?", (key,)
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    fetched = datetime.strptime(row["fetched_at"], _FMT).replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - fetched > timedelta(seconds=max_age_seconds):
        return None
    return json.loads(row["payload"])


def put(key: str, payload, source: str | None = None) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO data_cache (cache_key, payload, source, fetched_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(cache_key) DO UPDATE SET payload = excluded.payload, "
                "source = excluded.source, fetched_at = excluded.fetched_at",
                (key, json.dumps(payload, default=str), source),
            )
    except Exception:
        logger.exception("Écriture du cache impossible (%s)", key)
