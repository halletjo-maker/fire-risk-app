"""Connexion SQLite et schéma complet de l'application."""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import config
from .config import ALERT_FREQUENCIES, ALERT_TYPES, PRODUCT_TYPES, get_settings

logger = logging.getLogger(__name__)


def _in(values: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


SCHEMA = f"""
-- Utilisateurs identifiés par leur adresse mail (sans mot de passe)
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT,       -- scrypt ; NULL = mot de passe pas encore créé
    is_admin        INTEGER NOT NULL DEFAULT 0,   -- peut inviter des amis et gérer les membres
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Sessions de connexion (seule l'empreinte SHA-256 du jeton est stockée)
CREATE TABLE IF NOT EXISTS sessions (
    token_hash      TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_seen_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT    NOT NULL
);

-- Invitations à créer un compte (lien à usage unique, valable 7 jours)
CREATE TABLE IF NOT EXISTS invitations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash      TEXT    NOT NULL UNIQUE,
    email           TEXT    NOT NULL COLLATE NOCASE,
    invited_by      INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT    NOT NULL,
    used_at         TEXT
);

-- Réglages globaux de l'application (ex. utilisateur actif)
CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- Watchlists nommées et colorées
CREATE TABLE IF NOT EXISTS watchlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    color       TEXT    NOT NULL DEFAULT '#00FF88',
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, name)
);

-- Produits d'une watchlist + dernier état connu (rafraîchi toutes les 15 min)
CREATE TABLE IF NOT EXISTS watchlist_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id      INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol            TEXT    NOT NULL,
    product_id        TEXT,       -- identifiant de la source (ex. yf:NOW, bo:/bourse/...)
    name              TEXT,
    isin              TEXT,
    exchange          TEXT,
    product_type      TEXT    NOT NULL DEFAULT 'ACTION'
                      CHECK (product_type IN ({_in(PRODUCT_TYPES)})),
    position          INTEGER NOT NULL DEFAULT 0,
    last_price        REAL,
    last_change_pct   REAL,
    last_score        REAL,
    last_signal       TEXT CHECK (last_signal IN ('ACHAT', 'VENTE', 'NEUTRE')),
    last_refresh_at   TEXT,
    buy_price         REAL,       -- cours d'achat potentiel
    buy_kind          TEXT,       -- '≤' repli, '≥' confirmation, '≈' au cours actuel
    buy_note          TEXT,
    sell_price        REAL,       -- cours de vente potentiel (objectif)
    sell_note         TEXT,
    added_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (watchlist_id, symbol)
);

-- Alertes mail configurées par produit (supprimées avec le produit)
CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id             INTEGER NOT NULL REFERENCES watchlist_items(id) ON DELETE CASCADE,
    alert_type          TEXT    NOT NULL CHECK (alert_type IN ({_in(ALERT_TYPES)})),
    enabled             INTEGER NOT NULL DEFAULT 1,
    frequency           TEXT    NOT NULL DEFAULT 'immediate'
                        CHECK (frequency IN ({_in(ALERT_FREQUENCIES)})),
    last_state          TEXT,       -- ex. 'ABOVE'/'BELOW' pour détecter un croisement MM100
    last_triggered_at   TEXT,
    unsubscribe_token   TEXT    NOT NULL UNIQUE,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (item_id, alert_type)
);

-- Mails d'alerte envoyés (ou enregistrés dans outbox si SMTP absent)
CREATE TABLE IF NOT EXISTS alert_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    alert_id    INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
    alert_type  TEXT,
    product_id  TEXT,
    product     TEXT,
    subject     TEXT,
    delivered   INTEGER NOT NULL DEFAULT 0,
    status      TEXT,
    sent_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Historique des analyses réalisées
CREATE TABLE IF NOT EXISTS analysis_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query               TEXT    NOT NULL,
    symbol              TEXT,
    name                TEXT,
    product_type        TEXT,
    price               REAL,
    score_fundamental   REAL,
    score_technical     REAL,
    score_sentiment     REAL,
    score_global        REAL,
    verdict             TEXT,       -- FAVORABLE | PRUDENCE | DEFAVORABLE
    sources             TEXT,       -- JSON : sources utilisées
    report              TEXT,       -- JSON : rapport complet
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Cache des réponses des sources (limite les requêtes / le scraping)
CREATE TABLE IF NOT EXISTS data_cache (
    cache_key   TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    source      TEXT,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_user         ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_user       ON watchlists(user_id, position);
CREATE INDEX IF NOT EXISTS idx_items_watchlist       ON watchlist_items(watchlist_id, position);
CREATE INDEX IF NOT EXISTS idx_items_product         ON watchlist_items(product_id);
CREATE INDEX IF NOT EXISTS idx_alerts_item           ON alerts(item_id);
CREATE INDEX IF NOT EXISTS idx_history_user_date     ON analysis_history(user_id, created_at);
"""

TABLES = [
    "users",
    "sessions",
    "invitations",
    "alert_events",
    "app_settings",
    "watchlists",
    "watchlist_items",
    "alerts",
    "analysis_history",
    "data_cache",
]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Colonnes ajoutées après la première version (bases déjà créées)
MIGRATIONS = [
    ("watchlist_items", "product_id", "TEXT"),
    ("users", "password_hash", "TEXT"),
    ("users", "is_admin", "INTEGER NOT NULL DEFAULT 0"),
    ("watchlist_items", "buy_price", "REAL"),
    ("watchlist_items", "buy_kind", "TEXT"),
    ("watchlist_items", "buy_note", "TEXT"),
    ("watchlist_items", "sell_price", "REAL"),
    ("watchlist_items", "sell_note", "TEXT"),
]


def _import_legacy(path: Path) -> None:
    """Première utilisation du nouvel emplacement : reprend la base de l'ancien dossier data/."""
    legacy = config.LEGACY_DB_PATH
    if path.exists() or path.resolve() == legacy.resolve() or not legacy.is_file():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(legacy.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        dst = sqlite3.connect(path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        logger.info("Données reprises de %s vers %s", legacy, path)
    except sqlite3.Error as exc:
        path.unlink(missing_ok=True)
        logger.warning("Ancienne base illisible (%s) : démarrage avec une base neuve. Détail : %s", legacy, exc)


def init_db() -> None:
    path = get_settings().database_path
    _import_legacy(path)
    logger.info("Base de données : %s", path)
    with _connect(path) as conn:
        for table, column, kind in MIGRATIONS:
            exists = conn.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
            if exists:
                cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        conn.executescript(SCHEMA)
        # Bases créées avant les invitations : le premier compte avec mot de passe devient administrateur
        conn.execute(
            "UPDATE users SET is_admin = 1 WHERE id = (SELECT id FROM users WHERE password_hash IS NOT NULL "
            "ORDER BY id LIMIT 1) AND NOT EXISTS (SELECT 1 FROM users WHERE is_admin = 1)"
        )


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Connexion courte : commit si tout va bien, rollback sinon."""
    conn = _connect(get_settings().database_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_status() -> dict:
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        present = {r["name"] for r in rows}
        return {"ok": all(t in present for t in TABLES), "tables": sorted(present)}
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
