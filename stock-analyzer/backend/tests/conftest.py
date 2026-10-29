import os

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Client de test avec une base SQLite temporaire et sans planificateur."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
