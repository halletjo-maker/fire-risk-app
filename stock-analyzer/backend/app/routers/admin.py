"""Administration du serveur : version installée et mise à jour à la demande."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..config import PROJECT_DIR, get_settings
from ..database import get_conn
from ..deps import admin_user
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
    password: str = Field(min_length=8, max_length=64)


@router.get("/mail")
def mail_settings(admin: dict = Depends(admin_user)) -> dict:
    """Compte d'envoi des mails (le mot de passe n'est jamais renvoyé)."""
    c = sender.smtp_config()
    return {"configured": c["configured"], "source": c["source"], "user": c["user"] if c["configured"] else None}


@router.put("/mail")
def set_mail(payload: MailIn, admin: dict = Depends(admin_user)) -> dict:
    """Compte Gmail + mot de passe d'application ; vérifié auprès de Gmail avant d'être enregistré."""
    password = payload.password.replace(" ", "")  # Google l'affiche en 4 groupes de 4 lettres
    problem = sender.check_login(payload.user, password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    with get_conn() as conn:
        for key, value in (("smtp_user", payload.user), ("smtp_password", password), ("smtp_from", payload.user)):
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    return mail_settings(admin)


@router.delete("/mail")
def clear_mail(admin: dict = Depends(admin_user)) -> dict:
    with get_conn() as conn:
        conn.execute(f"DELETE FROM app_settings WHERE key IN ({','.join('?' * len(sender.DB_KEYS))})", sender.DB_KEYS)
    return mail_settings(admin)
