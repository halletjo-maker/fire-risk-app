"""Requêtes HTTP « polies » : délai minimum par site, timeout court, aucune exception."""
from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

import requests

from ...config import get_settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

_session = requests.Session()
_session.headers.update(
    {"User-Agent": USER_AGENT, "Accept-Language": "fr-BE,fr;q=0.9,en;q=0.8"}
)
_last_call: dict[str, float] = {}
_lock = threading.Lock()


def _wait_turn(host: str) -> None:
    """Respecte SCRAPING_DELAY_SECONDS entre deux requêtes vers le même site."""
    delay = get_settings().scraping_delay_seconds
    with _lock:
        now = time.monotonic()
        wait = _last_call.get(host, 0) + delay - now
        _last_call[host] = now + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def fetch_text(
    url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float = 10
) -> str | None:
    """Renvoie le contenu de la page, ou None en cas d'échec (jamais d'exception)."""
    _wait_turn(urlparse(url).netloc)
    try:
        r = _session.get(url, params=params, headers=headers, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            logger.info("HTTP %s pour %s", r.status_code, url)
            return None
        return r.text
    except requests.RequestException as exc:
        logger.info("Échec réseau pour %s : %s", url, exc)
        return None
