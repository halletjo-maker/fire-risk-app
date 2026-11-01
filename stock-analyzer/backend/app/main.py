"""Point d'entrée FastAPI — Analyse Boursière."""
from __future__ import annotations

import html
import json
import logging
import mimetypes
import re
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import APP_NAME, APP_VERSION, get_settings
from .database import init_db
from .routers import admin, alerts, analyze, health, portfolios, public, push, users, watchlists
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
               portfolios.router, public.router, push.router):
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
        """Page unique, avec l'adresse publique et le titre/description propres à la page demandée
        (Google et aperçus de liens partagés)."""
        base = public_base(scope)
        page = index.read_text(encoding="utf-8").replace("__PUBLIC_URL__", base)
        path = (scope.get("path") or "/").rstrip("/") or "/"
        return HTMLResponse(with_meta(page, path, base), headers={"Cache-Control": "no-cache"})

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


def public_base(scope) -> str:
    base = get_settings().app_public_url.rstrip("/")
    if not base:
        host = dict(scope.get("headers") or []).get(b"host", b"localhost").decode("latin-1")
        base = f"{scope.get('scheme', 'http')}://{host}"
    return base


_seo_cache: dict = {"mtime": None, "pages": {}}


def seo_pages() -> dict:
    """Titres et descriptions des pages publiques (seo.json, produit à la construction de l'interface)."""
    f = WEB_DIR / "seo.json"
    try:
        mtime = f.stat().st_mtime
    except OSError:
        return {}
    if _seo_cache["mtime"] != mtime:
        _seo_cache.update(mtime=mtime, pages=json.loads(f.read_text(encoding="utf-8")))
    return _seo_cache["pages"]


def with_meta(page: str, path: str, base: str) -> str:
    meta = seo_pages().get(path)
    if not meta:  # écrans de l'outil (connexion, invitation…) : pas dans Google
        return page.replace("</head>", '    <meta name="robots" content="noindex" />\n  </head>', 1)
    title, desc, url = (html.escape(meta["title"]), html.escape(meta["description"]), html.escape(base + (path if path != "/" else "/")))
    page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page, count=1, flags=re.S)
    page = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, page, count=1)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + desc, page, count=1)
    page = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + url, page, count=1)
    return page.replace("</head>", f'    <link rel="canonical" href="{url}" />\n  </head>', 1)


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> PlainTextResponse:
    base = public_base(request.scope)
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {base}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    base = public_base(request.scope)
    try:
        day = datetime.fromtimestamp((WEB_DIR / "seo.json").stat().st_mtime, timezone.utc).date().isoformat()
    except OSError:
        day = datetime.now(timezone.utc).date().isoformat()
    urls = "".join(
        f"<url><loc>{html.escape(base + path)}</loc><lastmod>{day}</lastmod>"
        f"<priority>{meta.get('priority', 0.5):.1f}</priority></url>"
        for path, meta in seo_pages().items())
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, media_type="application/xml")


if (WEB_DIR / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=WEB_DIR, html=True), name="web")
