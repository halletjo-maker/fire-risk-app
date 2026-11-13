"""Notifications sur le téléphone (Web Push), même application fermée.

Fonctionne avec Chrome/Brave/Firefox sur Android et ordinateur, et sur iPhone (iOS 16.4+)
quand MM100 est installé sur l'écran d'accueil. Les clés VAPID sont créées au premier besoin.
Trois sortes, réglables par chacun : alerts (mes alertes), trades (portefeuilles fictifs),
access (demandes d'accès, administrateur).
"""
from __future__ import annotations

import base64
import json
import logging
import threading

from ..config import get_settings
from ..database import get_conn

logger = logging.getLogger(__name__)

KINDS = {"alerts": "push_alerts", "trades": "push_trades", "access": "push_access"}
_key_lock = threading.Lock()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _setting(conn, key):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def keys() -> tuple[str, str]:
    """(clé privée PEM, clé publique pour le navigateur) ; créées une fois puis gardées."""
    with _key_lock, get_conn() as conn:
        private, public = _setting(conn, "vapid_private"), _setting(conn, "vapid_public")
        if private and public:
            return private, public
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
        public = _b64(key.public_key().public_bytes(serialization.Encoding.X962,
                                                    serialization.PublicFormat.UncompressedPoint))
        for k, v in (("vapid_private", private), ("vapid_public", public)):
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        return private, public


def subscribe(user_id: int, endpoint: str, p256dh: str, auth: str, agent: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh, "
            "auth = excluded.auth, user_agent = excluded.user_agent",
            (user_id, endpoint, p256dh, auth, (agent or "")[:200]))


def unsubscribe(user_id: int, endpoint: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?", (user_id, endpoint))


def _deliver(sub: dict, payload: str, private_pem: str) -> bool | None:
    """True envoyé ; False abonnement mort (à effacer) ; None erreur passagère."""
    from pywebpush import WebPushException, webpush

    try:
        webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                payload, vapid_private_key=_vapid(private_pem),
                vapid_claims={"sub": _contact()}, ttl=12 * 3600, timeout=15)
        return True
    except WebPushException as exc:
        code = getattr(exc.response, "status_code", None)
        if code in (404, 410):
            return False
        logger.warning("Notification non envoyée (%s)", code or exc)
        return None
    except Exception as exc:  # réseau, clé…
        logger.warning("Notification non envoyée (%s)", exc.__class__.__name__)
        return None


def _vapid(private_pem: str):
    from py_vapid import Vapid02

    return Vapid02.from_pem(private_pem.encode())


def _contact() -> str:
    from .mail import sender
    sender_addr = sender.smtp_config().get("from")
    if sender_addr:
        return f"mailto:{sender_addr}"
    url = get_settings().app_public_url.rstrip("/")
    return url if url.startswith("https://") else "mailto:admin@example.com"  # exigé : mailto: ou https:


def notify(user_id: int, kind: str | None, title: str, body: str, url: str = "/") -> int:
    """Envoie à tous les appareils de l'utilisateur (si cette sorte est activée). Renvoie le nombre reçu."""
    with get_conn() as conn:
        if kind:
            col = KINDS[kind]
            row = conn.execute(f"SELECT {col} AS on_ FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row or not row["on_"]:
                return 0
        subs = [dict(r) for r in conn.execute(
            "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?", (user_id,))]
    if not subs:
        return 0
    private, _ = keys()
    payload = json.dumps({"title": title, "body": body[:240], "url": url, "tag": kind or "test"})
    ok = 0
    for sub in subs:
        r = _deliver(sub, payload, private)
        if r:
            ok += 1
        elif r is False:
            with get_conn() as conn:
                conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (sub["id"],))
    return ok


def notify_later(user_id: int, kind: str, title: str, body: str, url: str = "/") -> None:
    """Sans bloquer l'appelant (planificateur, requête)."""
    def go():
        try:
            notify(user_id, kind, title, body, url)
        except Exception:
            logger.exception("Notification impossible")
    threading.Thread(target=go, daemon=True).start()


def notify_admins(kind: str, title: str, body: str, url: str = "/") -> None:
    with get_conn() as conn:
        admins = [r["id"] for r in conn.execute("SELECT id FROM users WHERE is_admin = 1")]
    for uid in admins:
        notify_later(uid, kind, title, body, url)


def status(user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT push_alerts, push_trades, push_access FROM users WHERE id = ?", (user_id,)).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM push_subscriptions WHERE user_id = ?", (user_id,)).fetchone()[0]
    return {"devices": count, "public_key": keys()[1],
            "kinds": {k: bool(row[c]) if row else True for k, c in KINDS.items()}}
