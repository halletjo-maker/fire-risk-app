"""Configuration chargée depuis le fichier .env (jamais de secret dans le code)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Le .env est cherché à la racine du projet, puis dans backend/ (le premier trouvé gagne).
for candidate in (PROJECT_DIR / ".env", BACKEND_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)
        break


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _placeholder(value: str | None) -> str | None:
    """Ignore les valeurs d'exemple laissées telles quelles dans le .env."""
    if not value or value.startswith(("ta_cle", "ton_mot", "ton_mail")):
        return None
    return value


@dataclass(frozen=True)
class Settings:
    newsapi_key: str | None = field(default_factory=lambda: _placeholder(os.getenv("NEWSAPI_KEY")))
    alpha_vantage_key: str | None = field(
        default_factory=lambda: _placeholder(os.getenv("ALPHA_VANTAGE_KEY"))
    )

    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: _int("SMTP_PORT", 587))
    smtp_user: str | None = field(default_factory=lambda: _placeholder(os.getenv("SMTP_USER")))
    smtp_password: str | None = field(
        default_factory=lambda: _placeholder(os.getenv("SMTP_PASSWORD"))
    )
    smtp_from: str | None = field(default_factory=lambda: _placeholder(os.getenv("SMTP_FROM")))
    smtp_use_tls: bool = field(default_factory=lambda: _bool("SMTP_USE_TLS", True))

    app_public_url: str = field(
        default_factory=lambda: os.getenv("APP_PUBLIC_URL", "http://localhost:8000")
    )
    database_path: Path = field(
        default_factory=lambda: _resolve(os.getenv("DATABASE_PATH", "data/stock_analyzer.db"))
    )
    scheduler_enabled: bool = field(default_factory=lambda: _bool("SCHEDULER_ENABLED", True))
    refresh_interval_minutes: int = field(
        default_factory=lambda: max(1, _int("REFRESH_INTERVAL_MINUTES", 15))
    )
    scraping_delay_seconds: int = field(default_factory=lambda: _int("SCRAPING_DELAY_SECONDS", 2))
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
        ]
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else BACKEND_DIR / p


def get_settings() -> Settings:
    """Relit l'environnement à chaque appel (pratique pour les tests)."""
    return Settings()


APP_NAME = "Analyse Boursière"
APP_VERSION = "0.1.0"

# 8 couleurs proposées pour les watchlists (identiques côté frontend).
WATCHLIST_COLORS = [
    "#00FF88",  # vert
    "#3B82F6",  # bleu
    "#A855F7",  # violet
    "#F59E0B",  # ambre
    "#EF4444",  # rouge
    "#06B6D4",  # cyan
    "#EC4899",  # rose
    "#94A3B8",  # gris
]

PRODUCT_TYPES = ["ACTION", "ETF", "TURBO", "WARRANT", "CRYPTO", "INDICE", "AUTRE"]
ALERT_TYPES = [
    "SIGNAL_FORT",  # score global >= 7.5
    "ALERTE_BAISSE",  # score global < 5
    "MM100_CROISEMENT",  # le prix croise la MM100
    "ACTUALITE_IMPORTANTE",  # sentiment < 3
    "RESULTATS_A_VENIR",  # résultats trimestriels < 48 h
]
ALERT_FREQUENCIES = ["immediate", "daily", "weekly"]
