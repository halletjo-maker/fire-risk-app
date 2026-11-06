"""Sauvegardes de la base.

- Chaque nuit : une copie compressée dans le dossier backups/ à côté de la base (14 gardées).
- Chaque dimanche : la même copie, chiffrée avec le mot de passe de sauvegarde, envoyée par mail
  aux administrateurs. Si le serveur disparaît, ce fichier suffit pour tout retrouver
  (python -m app.restore_backup fichier.mm100).

Ce qui n'est pas sauvegardé : le cache des cours (il se recharge) et les sessions (on se reconnecte).
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import logging
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from ..database import get_conn

logger = logging.getLogger(__name__)

KEEP = 14
MAGIC = b"MM100BK1"
MAX_MAIL_BYTES = 20 * 1024 * 1024  # Gmail refuse au-delà de 25 Mo
SKIP_TABLES = ("data_cache", "sessions", "password_resets")
PASSPHRASE_MIN = 12
EXTENSION = ".mm100"


def backup_dir() -> Path:
    return get_settings().database_path.parent / "backups"


def _setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _save(conn, **values) -> None:
    for key, value in values.items():
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ── Copie de la base ─────────────────────────────────────────────────────────
def snapshot() -> bytes:
    """Copie cohérente de la base (même pendant qu'elle travaille), allégée et compressée."""
    src = get_settings().database_path
    with tempfile.TemporaryDirectory() as tmp:
        dest_path = Path(tmp) / "copie.db"
        source = sqlite3.connect(src)
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
            existing = {r[0] for r in dest.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in SKIP_TABLES:
                if table in existing:
                    dest.execute(f"DELETE FROM {table}")
            dest.commit()
            dest.execute("VACUUM")
        finally:
            dest.close()
            source.close()
        return gzip.compress(dest_path.read_bytes(), compresslevel=9)


def local_backup(now: datetime | None = None) -> Path:
    """Copie du jour dans backups/ ; on garde les 14 plus récentes."""
    now = now or datetime.now()
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"mm100-{now:%Y-%m-%d}.db.gz"
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(snapshot())
    os.replace(tmp, path)
    for old in sorted(folder.glob("mm100-*.db.gz"))[:-KEEP]:
        old.unlink(missing_ok=True)
    return path


def local_list() -> list[dict]:
    folder = backup_dir()
    if not folder.exists():
        return []
    return [{"name": p.name, "size": p.stat().st_size} for p in sorted(folder.glob("mm100-*.db.gz"), reverse=True)]


# ── Chiffrement ──────────────────────────────────────────────────────────────
def _derive(passphrase: str, salt: bytes) -> bytes:
    raw = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return base64.urlsafe_b64encode(raw)


def encrypt(data: bytes, key: bytes, salt: bytes) -> bytes:
    from cryptography.fernet import Fernet
    return MAGIC + salt + Fernet(key).encrypt(data)


def decrypt(blob: bytes, passphrase: str) -> bytes:
    """Renvoie la base compressée ; ValueError si le fichier ou le mot de passe ne va pas."""
    from cryptography.fernet import Fernet, InvalidToken
    if not blob.startswith(MAGIC):
        raise ValueError("Ce fichier n'est pas une sauvegarde MM100.")
    salt, token = blob[len(MAGIC):len(MAGIC) + 16], blob[len(MAGIC) + 16:]
    try:
        return Fernet(_derive(passphrase, salt)).decrypt(token)
    except InvalidToken:
        raise ValueError("Mot de passe de sauvegarde incorrect.") from None


def set_passphrase(passphrase: str) -> None:
    """On garde la clé dérivée (pas le mot de passe) : il faut le mot de passe pour ouvrir un fichier."""
    salt = os.urandom(16)
    with get_conn() as conn:
        _save(conn, backup_salt=salt.hex(), backup_key=_derive(passphrase, salt).decode(),
              backup_passphrase_set_at=datetime.now().isoformat(timespec="seconds"))


def check_passphrase(passphrase: str) -> bool | None:
    """Le mot de passe noté est-il celui des copies envoyées ? None si aucun n'a été choisi."""
    with get_conn() as conn:
        key, salt = _setting(conn, "backup_key"), _setting(conn, "backup_salt")
    if not key or not salt:
        return None
    return hmac.compare_digest(_derive(passphrase, bytes.fromhex(salt)), key.encode())


# ── Envoi hebdomadaire ───────────────────────────────────────────────────────
def status() -> dict:
    from .mail import sender
    with get_conn() as conn:
        return {
            "passphrase_set": bool(_setting(conn, "backup_key")),
            "passphrase_set_at": _setting(conn, "backup_passphrase_set_at"),
            "last_sent": _setting(conn, "backup_last_sent"),
            "last_status": _setting(conn, "backup_last_status"),
            "mail_configured": sender.smtp_configured(),
            "local": local_list(),
        }


def send_by_mail(now: datetime | None = None) -> dict:
    """Chiffre la copie du jour et l'envoie aux administrateurs. Renvoie {"sent", "status"}."""
    from .mail import sender
    now = now or datetime.now()
    with get_conn() as conn:
        key, salt = _setting(conn, "backup_key"), _setting(conn, "backup_salt")
        admins = [r["email"] for r in conn.execute("SELECT email FROM users WHERE is_admin = 1 ORDER BY id")]
    if not key or not salt:
        result = {"sent": False, "status": "Aucun mot de passe de sauvegarde choisi"}
    elif not admins:
        result = {"sent": False, "status": "Aucun administrateur"}
    else:
        blob = encrypt(snapshot(), key.encode(), bytes.fromhex(salt))
        if len(blob) > MAX_MAIL_BYTES:
            result = {"sent": False, "status": f"Sauvegarde trop lourde pour un mail ({len(blob) // 1_000_000} Mo)"}
        else:
            name = f"mm100-sauvegarde-{now:%Y-%m-%d}{EXTENSION}"
            text = (
                f"Bonjour,\n\nVoici la sauvegarde hebdomadaire de MM100 du {now:%d/%m/%Y} "
                f"({max(1, len(blob) // 1000)} ko).\n\n"
                "Garde ce mail : si le serveur tombe en panne, ce fichier permet de tout retrouver "
                "(comptes, watchlists, portefeuilles fictifs, historique).\n"
                "Il est chiffré : il ne s'ouvre qu'avec ton mot de passe de sauvegarde. "
                "Sans ce mot de passe, personne ne peut le lire, même pas toi.\n\n"
                "Les anciennes sauvegardes peuvent être supprimées : la plus récente suffit.\n\n— MM100\n"
            )
            failures = [r["status"] for r in (sender.send(to, f"Sauvegarde MM100 du {now:%d/%m/%Y}", text,
                                                         attachments=[(name, blob)]) for to in admins)
                        if not r["delivered"]]
            result = {"sent": not failures, "status": failures[0] if failures else "Envoyée"}
    with get_conn() as conn:
        values = {"backup_last_status": result["status"]}
        if result["sent"]:
            values["backup_last_sent"] = now.isoformat(timespec="seconds")
        _save(conn, **values)
    return result


def nightly() -> None:
    try:
        local_backup()
    except Exception:
        logger.exception("Sauvegarde locale impossible")


def weekly() -> None:
    try:
        r = send_by_mail()
        logger.info("Sauvegarde par mail : %s", r["status"])
    except Exception:
        logger.exception("Sauvegarde par mail impossible")
