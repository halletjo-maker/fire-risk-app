from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..services.mail import sender
from ..config import APP_NAME, APP_VERSION, get_settings
from ..database import db_status
from ..scheduler import scheduler_status

router = APIRouter(tags=["santé"])


@router.get("/health")
def health() -> dict:
    """État du backend : base de données, planificateur, configuration."""
    settings = get_settings()
    db = db_status()
    return {
        "status": "ok" if db["ok"] else "degraded",
        "app": APP_NAME,
        "version": APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": db,
        "scheduler": scheduler_status(),
        "config": {
            "smtp_configured": sender.smtp_configured(),
            "newsapi_configured": bool(settings.newsapi_key),
            "alpha_vantage_configured": bool(settings.alpha_vantage_key),
            "refresh_interval_minutes": settings.refresh_interval_minutes,
        },
    }
