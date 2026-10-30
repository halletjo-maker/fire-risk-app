"""Administration du serveur : version installée et mise à jour à la demande."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..config import PROJECT_DIR, get_settings
from ..deps import admin_user

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
