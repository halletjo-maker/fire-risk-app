"""Point d'entrée FastAPI — Analyse Boursière."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_NAME, APP_VERSION, get_settings
from .database import init_db
from .routers import analyze, health, users, watchlists
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

for router in (health.router, users.router, watchlists.router, analyze.router):
    app.include_router(router)
