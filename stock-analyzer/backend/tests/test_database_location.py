"""Emplacement de la base : hors du dossier de l'application, reprise automatique de l'ancienne."""
import sqlite3

from app import config, database


def test_windows_default_location(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "IS_WINDOWS", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    for value in (None, "data/stock_analyzer.db", r"data\stock_analyzer.db", "./data/stock_analyzer.db"):
        if value is None:
            monkeypatch.delenv("DATABASE_PATH", raising=False)
        else:
            monkeypatch.setenv("DATABASE_PATH", value)
        assert config.get_settings().database_path == tmp_path / "AnalyseBoursiere" / "stock_analyzer.db"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ailleurs.db"))
    assert config.get_settings().database_path == tmp_path / "ailleurs.db"


def test_legacy_database_is_imported(monkeypatch, tmp_path):
    legacy = tmp_path / "old dir (5)" / "stock_analyzer.db"
    legacy.parent.mkdir()
    with sqlite3.connect(legacy) as c:
        c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, created_at TEXT, last_login_at TEXT)")
        c.execute("INSERT INTO users (email) VALUES ('jean@exemple.be')")
    new = tmp_path / "AppData" / "AnalyseBoursiere" / "stock_analyzer.db"
    monkeypatch.setattr(config, "LEGACY_DB_PATH", legacy)
    monkeypatch.setenv("DATABASE_PATH", str(new))
    database.init_db()
    with sqlite3.connect(new) as c:
        assert c.execute("SELECT email FROM users").fetchall() == [("jean@exemple.be",)]
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        assert "password_hash" in cols  # migration appliquée après la reprise
    # Deuxième démarrage : la nouvelle base n'est plus écrasée
    with sqlite3.connect(new) as c:
        c.execute("INSERT INTO users (email) VALUES ('marie@exemple.be')")
    database.init_db()
    with sqlite3.connect(new) as c:
        assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2


def test_unreadable_legacy_database_does_not_block_startup(monkeypatch, tmp_path):
    legacy = tmp_path / "stock_analyzer.db"
    legacy.write_bytes(b"pas une base sqlite" * 100)
    new = tmp_path / "neuf" / "stock_analyzer.db"
    monkeypatch.setattr(config, "LEGACY_DB_PATH", legacy)
    monkeypatch.setenv("DATABASE_PATH", str(new))
    database.init_db()
    assert database.db_status()["ok"]
