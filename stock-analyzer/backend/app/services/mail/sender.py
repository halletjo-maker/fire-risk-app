"""Envoi des mails via smtplib (configuration SMTP dans .env).

Sans SMTP configuré, le mail est enregistré dans data/outbox/ (fichier .eml lisible)
pour pouvoir vérifier les alertes avant de saisir un mot de passe.
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from ...config import get_settings

logger = logging.getLogger(__name__)


GMAIL = {"host": "smtp.gmail.com", "port": 587, "tls": True}
DB_KEYS = ("smtp_user", "smtp_password", "smtp_from")


def smtp_config() -> dict:
    """Compte d'envoi : réglages saisis dans l'application (Profil → Réglages mail), sinon le .env."""
    s = get_settings()
    cfg = {"host": s.smtp_host, "port": s.smtp_port, "user": s.smtp_user, "password": s.smtp_password,
           "from": s.smtp_from, "tls": s.smtp_use_tls, "source": "env" if s.smtp_configured else None}
    try:
        from ...database import get_conn
        with get_conn() as conn:
            db = {r["key"]: r["value"] for r in conn.execute(
                f"SELECT key, value FROM app_settings WHERE key IN ({','.join('?' * len(DB_KEYS))})", DB_KEYS)}
    except Exception:
        db = {}
    if db.get("smtp_user") and db.get("smtp_password"):
        cfg.update(GMAIL, user=db["smtp_user"], password=db["smtp_password"], source="app",
                   **{"from": db.get("smtp_from") or db["smtp_user"]})
    cfg["configured"] = bool(cfg["host"] and cfg["user"] and cfg["password"])
    return cfg


def smtp_configured() -> bool:
    return smtp_config()["configured"]


def check_login(user: str, password: str) -> str | None:
    """Essaie de se connecter à Gmail. Renvoie un message d'erreur, ou None si c'est bon."""
    try:
        with smtplib.SMTP(GMAIL["host"], GMAIL["port"], timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(user, password)
        return None
    except smtplib.SMTPAuthenticationError:
        return ("Gmail refuse ces identifiants. Utilise un mot de passe d'application (16 lettres), "
                "pas ton mot de passe Gmail habituel.")
    except (smtplib.SMTPException, OSError) as exc:
        return f"Connexion à Gmail impossible ({exc.__class__.__name__}). Réessaie plus tard."


def outbox_dir() -> Path:
    """Dossier outbox/ à côté de la base SQLite."""
    return get_settings().database_path.parent / "outbox"


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    c = smtp_config()
    msg = EmailMessage()
    sender = c["from"] or c["user"] or "alertes@analyse-boursiere.local"
    msg["From"] = formataddr(("Analyse Boursière", sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="analyse-boursiere.local")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send(to: str, subject: str, text: str, html: str | None = None) -> dict:
    """Renvoie {"delivered": bool, "status": "...", "file": chemin .eml éventuel}."""
    s = smtp_config()
    msg = build_message(to, subject, text, html)
    if not s["configured"]:
        path = save_to_outbox(msg)
        return {"delivered": False, "status": "SMTP non configuré : mail enregistré dans outbox", "file": str(path)}
    try:
        if s["tls"] and s["port"] != 465:
            with smtplib.SMTP(s["host"], s["port"], timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(s["user"], s["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(s["host"], s["port"], timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.login(s["user"], s["password"])
                smtp.send_message(msg)
        return {"delivered": True, "status": "Envoyé", "file": None}
    except smtplib.SMTPAuthenticationError:
        logger.warning("SMTP : identifiants refusés")
        return {"delivered": False, "status": "Identifiants SMTP refusés (mot de passe d'application ?)", "file": None}
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("SMTP : envoi impossible (%s)", exc)
        return {"delivered": False, "status": f"Envoi impossible : {exc.__class__.__name__}", "file": None}


def save_to_outbox(msg: EmailMessage) -> Path:
    folder = outbox_dir()
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", msg["Subject"].lower())[:50].strip("-")
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{slug}.eml"
    path.write_bytes(bytes(msg))
    return path
