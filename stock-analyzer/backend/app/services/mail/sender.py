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


# Fournisseurs proposés dans l'application (Profil → Réglages mail)
PROVIDERS = {
    "gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True, "label": "Gmail"},
    # Adresse sur ton nom de domaine hébergée chez OVHcloud (Zimbra Starter / MX Plan)
    "ovh": {"host": "ssl0.ovh.net", "port": 465, "tls": False, "label": "OVHcloud"},
}
GMAIL = PROVIDERS["gmail"]
DB_KEYS = ("smtp_user", "smtp_password", "smtp_from", "smtp_provider")


def provider_for(email: str) -> str:
    """Gmail pour une adresse gmail.com, sinon une adresse de ton domaine chez OVHcloud."""
    domain = email.rsplit("@", 1)[-1].lower()
    return "gmail" if domain in ("gmail.com", "googlemail.com") else "ovh"


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
        prov = PROVIDERS.get(db.get("smtp_provider") or "gmail", GMAIL)
        cfg.update(host=prov["host"], port=prov["port"], tls=prov["tls"], user=db["smtp_user"],
                   password=db["smtp_password"], source="app", provider=db.get("smtp_provider") or "gmail",
                   **{"from": db.get("smtp_from") or db["smtp_user"]})
    cfg["configured"] = bool(cfg["host"] and cfg["user"] and cfg["password"])
    return cfg


def smtp_configured() -> bool:
    return smtp_config()["configured"]


def _open(host: str, port: int, tls: bool) -> smtplib.SMTP:
    if tls and port != 465:
        smtp = smtplib.SMTP(host, port, timeout=20)
        smtp.starttls(context=ssl.create_default_context())
        return smtp
    return smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())


def check_login(user: str, password: str, provider: str = "gmail") -> str | None:
    """Essaie de se connecter au serveur d'envoi. Renvoie un message d'erreur, ou None si c'est bon."""
    prov = PROVIDERS[provider]
    try:
        with _open(prov["host"], prov["port"], prov["tls"]) as smtp:
            smtp.login(user, password)
        return None
    except smtplib.SMTPAuthenticationError:
        if provider == "gmail":
            return ("Gmail refuse ces identifiants. Utilise un mot de passe d'application (16 lettres), "
                    "pas ton mot de passe Gmail habituel.")
        return "OVHcloud refuse ces identifiants : vérifie l'adresse complète et le mot de passe de cette boîte mail."
    except (smtplib.SMTPException, OSError) as exc:
        return f"Connexion à {prov['label']} impossible ({exc.__class__.__name__}). Réessaie plus tard."


def outbox_dir() -> Path:
    """Dossier outbox/ à côté de la base SQLite."""
    return get_settings().database_path.parent / "outbox"


def build_message(to: str, subject: str, text: str, html: str | None = None,
                  attachments: list[tuple[str, bytes]] | None = None) -> EmailMessage:
    c = smtp_config()
    msg = EmailMessage()
    sender = c["from"] or c["user"] or "alertes@analyse-boursiere.local"
    msg["From"] = formataddr(("Analyse Boursière", sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] if "@" in sender else "analyse-boursiere.local")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    for name, data in attachments or ():
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return msg


def send(to: str, subject: str, text: str, html: str | None = None,
         attachments: list[tuple[str, bytes]] | None = None) -> dict:
    """Renvoie {"delivered": bool, "status": "...", "file": chemin .eml éventuel}."""
    s = smtp_config()
    msg = build_message(to, subject, text, html, attachments)
    if not s["configured"]:
        path = save_to_outbox(msg)
        return {"delivered": False, "status": "SMTP non configuré : mail enregistré dans outbox", "file": str(path)}
    try:
        with _open(s["host"], s["port"], s["tls"]) as smtp:
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
