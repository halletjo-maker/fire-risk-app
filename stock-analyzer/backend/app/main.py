"""Point d'entrée FastAPI — Analyse Boursière."""
from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import APP_NAME, APP_VERSION, get_settings
from .database import init_db
from .routers import admin, alerts, analyze, health, portfolios, public, users, watchlists
from .scheduler import start_scheduler, stop_scheduler

settings = get_settings()
mimetypes.add_type("application/manifest+json", ".webmanifest")  # installation sur téléphone
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

for router in (health.router, users.router, watchlists.router, analyze.router, alerts.router, admin.router,
               portfolios.router, public.router):
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
class SPAStaticFiles(StaticFiles):
    """Fichiers de l'interface ; toute autre adresse (ex. /apprendre/rsi) renvoie la page unique."""

    async def get_response(self, path, scope):
        response = await self._response(path, scope)
        if isinstance(response, FileResponse) and Path(response.path).name == "index.html":
            return self._page(Path(response.path), scope)
        return response

    @staticmethod
    def _page(index: Path, scope) -> HTMLResponse:
        """Page unique avec l'adresse publique (aperçu des liens partagés : image et adresse absolues)."""
        base = get_settings().app_public_url.rstrip("/")
        if not base:
            host = dict(scope.get("headers") or []).get(b"host", b"localhost").decode("latin-1")
            base = f"{scope.get('scheme', 'http')}://{host}"
        html = index.read_text(encoding="utf-8").replace("__PUBLIC_URL__", base)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    async def _response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = None
        if response is None or response.status_code == 404:
            if "." in path.rsplit("/", 1)[-1]:  # fichier manquant (ex. .js) : vrai 404
                return response if response is not None else await super().get_response("__absent__", scope)
            return await super().get_response("index.html", scope)
        return response


if (WEB_DIR / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=WEB_DIR, html=True), name="web")
