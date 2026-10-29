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


def outbox_dir() -> Path:
    """Dossier outbox/ à côté de la base SQLite."""
    return get_settings().database_path.parent / "outbox"


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    s = get_settings()
    msg = EmailMessage()
    sender = s.smtp_from or s.smtp_user or "alertes@analyse-boursiere.local"
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
    s = get_settings()
    msg = build_message(to, subject, text, html)
    if not s.smtp_configured:
        path = save_to_outbox(msg)
        return {"delivered": False, "status": "SMTP non configuré : mail enregistré dans outbox", "file": str(path)}
    try:
        if s.smtp_use_tls and s.smtp_port != 465:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.login(s.smtp_user, s.smtp_password)
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
