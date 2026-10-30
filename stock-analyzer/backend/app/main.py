"""Point d'entrée FastAPI — Analyse Boursière."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, get_settings
from .database import init_db
from .routers import admin, alerts, analyze, health, users, watchlists
from .scheduler import start_scheduler, stop_scheduler

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

origins = settings.cors_origins or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, users.router, watchlists.router, analyze.router, alerts.router, admin.router):
    app.include_router(router)


# Interface prête à l'emploi (npm run build → backend/web) : l'app entière tient sur le port 8000,
# sans Node.js. L'interface appelle "/api/..." : on retire ce préfixe avant le routage.
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class StripApiPrefix:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["path"] == "/api" or scope["path"].startswith("/api/")):
            scope = dict(scope, path=scope["path"][4:] or "/", raw_path=None)
        await self.app(scope, receive, send)


app.add_middleware(StripApiPrefix)
if (WEB_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
