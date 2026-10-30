"""Tâches de fond planifiées avec APScheduler.

- refresh_watchlists : met à jour prix / score / signal des produits suivis (Module 8)
- check_alerts       : évalue les alertes et envoie les mails (Module 9)
Les deux tâches tournent toutes les REFRESH_INTERVAL_MINUTES (15 par défaut).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings

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
    run_portfolios()


def run_portfolios() -> None:
    """Portefeuilles fictifs : achats / ventes sur les cours tout juste mis à jour."""
    from .services import paper

    try:
        paper.run_all()
    except Exception:
        logger.exception("Échec de la simulation des portefeuilles fictifs")


def check_alerts() -> None:
    """Évalue les alertes actives et envoie les mails (Module 9)."""
    from .services import alerts

    try:
        sent = alerts.check_all()
        logger.info("Vérification des alertes : %s mail(s) envoyé(s)", sent)
    except Exception:
        logger.exception("Échec de la vérification des alertes")


def refresh_screens() -> None:
    """Listes larges (IPO 10 ans…) : une fois par jour après la clôture américaine."""
    from .services import screens

    try:
        screens.refresh(resync=True)
    except Exception:
        logger.exception("Échec de la mise à jour des listes larges")
    run_portfolios()


def refresh_world_zones() -> None:
    """Liste mondiale : toutes les 30 min, les titres dont la Bourse est ouverte (+ cryptos 7 j/7)."""
    from .services import screens, world

    try:
        if screens._screen_ids(None, kind=screens.WORLD_KIND):
            screens.refresh(zones=world.open_zones())
            run_portfolios()
    except Exception:
        logger.exception("Échec de la mise à jour de la liste mondiale")


def start_scheduler() -> None:
    settings = get_settings()
    if not settings.scheduler_enabled or scheduler.running:
        return
    minutes = settings.refresh_interval_minutes
    scheduler.add_job(
        refresh_watchlists, "interval", minutes=minutes, id="refresh_watchlists",
        name="Rafraîchissement des watchlists", replace_existing=True,
    )
    # Les alertes passent 3 minutes après le rafraîchissement : les analyses sont alors en cache
    scheduler.add_job(
        check_alerts, "interval", minutes=minutes, id="check_alerts",
        name="Vérification des alertes mail", replace_existing=True,
        next_run_time=datetime.now().astimezone() + timedelta(minutes=minutes + 3),
    )
    # Clôture US 22 h (Bruxelles) : calcul à 22 h 45 du lundi au vendredi
    scheduler.add_job(
        refresh_screens, "cron", day_of_week="mon-fri", hour=22, minute=45, id="refresh_screens",
        name="Listes larges (1×/jour)", replace_existing=True,
    )
    scheduler.add_job(
        refresh_world_zones, "cron", minute="5,35", id="refresh_world_zones",
        name="Liste mondiale (Bourses ouvertes, toutes les 30 min)", replace_existing=True,
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
