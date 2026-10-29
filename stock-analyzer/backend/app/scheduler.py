"""Tâches de fond planifiées avec APScheduler.

- refresh_watchlists : met à jour prix / score / signal des produits suivis (Module 8)
- check_alerts       : évalue les alertes et envoie les mails (Module 9)
Les deux tâches tournent toutes les REFRESH_INTERVAL_MINUTES (15 par défaut).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .database import get_conn

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    timezone="Europe/Brussels",
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
)


def refresh_watchlists() -> None:
    """Met à jour prix, variation, score et signal de tous les produits suivis."""
    from .services import watchlist  # import local : évite de charger les sources au démarrage

    try:
        done = watchlist.refresh_all()
        logger.info("Rafraîchissement watchlists : %s produit(s) mis à jour", done)
    except Exception:  # une tâche de fond ne doit jamais faire tomber l'app
        logger.exception("Échec du rafraîchissement des watchlists")


def check_alerts() -> None:
    """Placeholder — l'évaluation et l'envoi des mails arrivent au Module 9."""
    try:
        with get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM alerts WHERE enabled = 1").fetchone()[0]
        logger.info("Vérification des alertes : %s alerte(s) active(s)", count)
    except Exception:
        logger.exception("Échec de la vérification des alertes")


def start_scheduler() -> None:
    settings = get_settings()
    if not settings.scheduler_enabled or scheduler.running:
        return
    minutes = settings.refresh_interval_minutes
    scheduler.add_job(
        refresh_watchlists, "interval", minutes=minutes, id="refresh_watchlists",
        name="Rafraîchissement des watchlists", replace_existing=True,
    )
    scheduler.add_job(
        check_alerts, "interval", minutes=minutes, id="check_alerts",
        name="Vérification des alertes mail", replace_existing=True,
    )
    scheduler.start()
    logger.info("Planificateur démarré (toutes les %s min)", minutes)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def scheduler_status() -> dict:
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }
