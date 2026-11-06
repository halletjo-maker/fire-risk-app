"""Alerte « MM100 en panne / rétabli » envoyée par la surveillance du serveur (watchdog.sh).

Volontairement indépendant du code de l'application : il doit marcher même quand
l'application ne démarre plus (mise à jour ratée). Lit la base et le .env directement.
Usage (en tant qu'utilisateur analyse) : python watchdog_alert.py down|up "détail"
"""
from __future__ import annotations

import json
import smtplib
import sqlite3
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
PROVIDERS = {"gmail": ("smtp.gmail.com", 587, True), "ovh": ("ssl0.ovh.net", 465, False)}


def read_env(path: Path | None = None) -> dict:
    path = path or ENV_FILE
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def connect(env: dict) -> sqlite3.Connection:
    conn = sqlite3.connect(env.get("DATABASE_PATH") or "", timeout=10)  # lancé en tant qu'analyse (propriétaire)
    conn.row_factory = sqlite3.Row
    return conn


def settings(conn) -> dict:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM app_settings")}


def smtp_config(env: dict, s: dict) -> dict | None:
    if s.get("smtp_user") and s.get("smtp_password"):
        host, port, tls = PROVIDERS.get(s.get("smtp_provider") or "gmail", PROVIDERS["gmail"])
        return {"host": host, "port": port, "tls": tls, "user": s["smtp_user"], "password": s["smtp_password"],
                "from": s.get("smtp_from") or s["smtp_user"]}
    if env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASSWORD"):
        port = int(env.get("SMTP_PORT") or 587)
        return {"host": env["SMTP_HOST"], "port": port, "tls": port != 465, "user": env["SMTP_USER"],
                "password": env["SMTP_PASSWORD"], "from": env.get("SMTP_FROM") or env["SMTP_USER"]}
    return None


def message(kind: str, detail: str, url: str) -> tuple[str, str]:
    if kind == "up":
        return "✅ MM100 fonctionne à nouveau", f"Le site {url} répond de nouveau normalement.\n\n{detail}\n\n— Surveillance du serveur"
    return ("⚠️ MM100 ne répond plus",
            f"Le site {url} ne répond plus et le redémarrage automatique n'a pas suffi.\n\n"
            f"Détail : {detail}\n\n"
            "Que faire : rien d'urgent si tu n'en as pas besoin tout de suite. Sinon, ouvre une session "
            "Claude Code et colle ce message : on regardera ensemble le journal du serveur.\n"
            "Tu recevras un mail dès que le site sera rétabli.\n\n— Surveillance du serveur")


def send_mail(cfg: dict, to: list[str], subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"] = formataddr(("MM100 surveillance", cfg["from"]))
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(text)
    ctx = ssl.create_default_context()
    if cfg["tls"]:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30, context=ctx) as smtp:
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)


def send_push(conn, s: dict, subject: str, body: str, contact: str) -> int:
    """Notifications téléphone des administrateurs (si pywebpush est disponible)."""
    try:
        from py_vapid import Vapid02
        from pywebpush import webpush
    except ImportError:
        return 0
    if not s.get("vapid_private"):
        return 0
    key = Vapid02.from_pem(s["vapid_private"].encode())
    subs = conn.execute("SELECT p.endpoint, p.p256dh, p.auth FROM push_subscriptions p "
                        "JOIN users u ON u.id = p.user_id WHERE u.is_admin = 1").fetchall()
    sent = 0
    for sub in subs:
        try:
            webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                    json.dumps({"title": subject, "body": body[:200], "url": "/", "tag": "watchdog"}),
                    vapid_private_key=key, vapid_claims={"sub": contact}, ttl=6 * 3600, timeout=15)
            sent += 1
        except Exception as exc:  # appareil hors ligne, etc.
            print(f"notification non envoyée : {exc.__class__.__name__}")
    return sent


def main(argv: list[str]) -> int:
    kind = argv[1] if len(argv) > 1 else "down"
    detail = argv[2] if len(argv) > 2 else ""
    env = read_env()
    url = env.get("APP_PUBLIC_URL", "le site")
    subject, text = message(kind, detail, url)
    try:
        conn = connect(env)
        s = settings(conn)
        admins = [r["email"] for r in conn.execute("SELECT email FROM users WHERE is_admin = 1")]
    except sqlite3.Error as exc:
        print(f"base illisible : {exc}")
        return 1
    cfg = smtp_config(env, s)
    if cfg and admins:
        try:
            send_mail(cfg, admins, subject, text)
            print("mail envoyé")
        except Exception as exc:
            print(f"mail non envoyé : {exc.__class__.__name__}")
    contact = f"mailto:{cfg['from']}" if cfg else "mailto:admin@example.com"
    try:
        print(f"notifications : {send_push(conn, s, subject, detail or text.splitlines()[0], contact)}")
    except sqlite3.Error:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
