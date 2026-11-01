"""Administration du serveur : version installée et mise à jour à la demande."""
from __future__ import annotations

import re
import socket
from typing import Literal
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..config import PROJECT_DIR, get_settings
from ..database import get_conn
from ..deps import admin_user
from ..services import backup
from ..services.mail import sender

router = APIRouter(prefix="/admin", tags=["administration"])

VERSION_FILE = PROJECT_DIR.parent / "VERSION"            # écrit par deploy/enable-autoupdate.sh
UPDATE_UNIT = Path("/etc/systemd/system/analyse-boursiere-update.path")


def _request_file() -> Path:
    return get_settings().database_path.parent / "update.request"


def _version() -> dict | None:
    try:
        commit, date, subject = VERSION_FILE.read_text(encoding="utf-8").strip().split("|", 2)
        return {"commit": commit, "date": date, "subject": subject}
    except (OSError, ValueError):
        return None


@router.get("/version")
def version(admin: dict = Depends(admin_user)) -> dict:
    return {
        "version": _version(),
        "auto_update": UPDATE_UNIT.exists(),
        "update_pending": _request_file().exists(),
    }


@router.post("/update", status_code=202)
def request_update(admin: dict = Depends(admin_user)) -> dict:
    """Dépose une demande : le service système (root) télécharge la dernière version et redémarre l'app."""
    if not UPDATE_UNIT.exists():
        raise HTTPException(status_code=409, detail="La mise à jour automatique n'est pas installée sur cette machine.")
    _request_file().write_text("demandée depuis l'application\n", encoding="utf-8")
    return {"update_pending": True}


class MailIn(BaseModel):
    user: EmailStr
    password: str = Field(min_length=8, max_length=128)
    provider: Literal["gmail", "ovh"] | None = None  # déduit de l'adresse si absent


@router.get("/mail")
def mail_settings(admin: dict = Depends(admin_user)) -> dict:
    """Compte d'envoi des mails (le mot de passe n'est jamais renvoyé)."""
    c = sender.smtp_config()
    return {"configured": c["configured"], "source": c["source"], "user": c["user"] if c["configured"] else None,
            "provider": c.get("provider") if c["configured"] else None}


@router.put("/mail")
def set_mail(payload: MailIn, admin: dict = Depends(admin_user)) -> dict:
    """Gmail (mot de passe d'application) ou adresse de ton domaine chez OVHcloud ; vérifié avant d'être enregistré."""
    provider = payload.provider or sender.provider_for(payload.user)
    password = payload.password.replace(" ", "") if provider == "gmail" else payload.password  # Google : 4 groupes de 4
    problem = sender.check_login(payload.user, password, provider)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    with get_conn() as conn:
        for key, value in (("smtp_user", payload.user), ("smtp_password", password), ("smtp_from", payload.user),
                           ("smtp_provider", provider)):
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    return mail_settings(admin)


@router.delete("/mail")
def clear_mail(admin: dict = Depends(admin_user)) -> dict:
    with get_conn() as conn:
        conn.execute(f"DELETE FROM app_settings WHERE key IN ({','.join('?' * len(sender.DB_KEYS))})", sender.DB_KEYS)
    return mail_settings(admin)


# ── Sauvegardes ─────────────────────────────────────────────────────────────
class BackupPassIn(BaseModel):
    passphrase: str = Field(min_length=backup.PASSPHRASE_MIN, max_length=200)


@router.get("/backup")
def backup_status(admin: dict = Depends(admin_user)) -> dict:
    return backup.status()


@router.put("/backup")
def set_backup_passphrase(payload: BackupPassIn, admin: dict = Depends(admin_user)) -> dict:
    backup.set_passphrase(payload.passphrase)
    return backup.status()


@router.post("/backup/send")
def send_backup_now(admin: dict = Depends(admin_user)) -> dict:
    result = backup.send_by_mail()
    return {**result, **backup.status()}


# ── Nom de domaine ───────────────────────────────────────────────────────────
DOMAIN_UNIT = Path("/etc/systemd/system/analyse-boursiere-domain.path")
DOMAIN_RE = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


class DomainIn(BaseModel):
    domain: str = Field(min_length=3, max_length=200)


def _resolve(name: str | None) -> set[str]:
    """Adresses IPv4 annoncées par le DNS pour ce nom (vide si inconnu)."""
    if not name:
        return set()
    try:
        return {a[4][0] for a in socket.getaddrinfo(name, None, socket.AF_INET)}
    except (socket.gaierror, UnicodeError, OSError):
        return set()


def _domain_files() -> tuple[Path, Path]:
    d = get_settings().database_path.parent
    return d / "domain.request", d / "domain.status"


def _server_ips(request: Request) -> set[str]:
    return _resolve(urlparse(get_settings().app_public_url).hostname) | _resolve(request.url.hostname)


@router.get("/domain")
def domain_status(request: Request, admin: dict = Depends(admin_user)) -> dict:
    req, status = _domain_files()
    last = None
    try:
        state, names, when = status.read_text(encoding="utf-8").strip().split("|", 2)
        last = {"ok": state == "ok", "detail": names, "at": when}
    except (OSError, ValueError):
        pass
    return {
        "current": urlparse(get_settings().app_public_url).hostname,
        "available": DOMAIN_UNIT.exists(),
        "pending": req.exists(),
        "last": last,
        "server_ip": sorted(_server_ips(request))[0] if _server_ips(request) else None,
    }


@router.post("/domain", status_code=202)
def set_domain(payload: DomainIn, request: Request, admin: dict = Depends(admin_user)) -> dict:
    """Vérifie que le domaine pointe vers ce serveur puis demande la configuration (Caddy, https, liens)."""
    if not DOMAIN_UNIT.exists():
        raise HTTPException(status_code=409, detail="Réglage indisponible sur cette installation (serveur pas encore à jour).")
    name = payload.domain.strip().lower()
    name = re.sub(r"^https?://", "", name).split("/")[0].removeprefix("www.")
    if not DOMAIN_RE.match(name):
        raise HTTPException(status_code=422, detail="Nom de domaine invalide (exemple : mm100.be).")
    server = _server_ips(request)
    found = _resolve(name)
    if not found:
        raise HTTPException(status_code=400, detail=f"{name} n'est pas encore visible sur Internet. Vérifie que le domaine "
                            "est actif et que la zone DNS contient une entrée A vers l'adresse du serveur, puis réessaie "
                            "dans 15 minutes (la propagation peut prendre jusqu'à quelques heures).")
    if server and not (found & server):
        raise HTTPException(status_code=400, detail=f"{name} pointe vers {', '.join(sorted(found))} au lieu de "
                            f"{', '.join(sorted(server))}. Corrige l'entrée A dans la zone DNS (et supprime l'entrée par défaut).")
    names = [name] + ([f"www.{name}"] if _resolve(f"www.{name}") & (server or found) else [])
    req, _ = _domain_files()
    req.write_text(" ".join(names) + "\n", encoding="utf-8")
    return {"pending": True, "names": names}
