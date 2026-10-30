import pytest
from fastapi import Header, HTTPException


def _user_from_test_header(x_user_email: str | None = Header(default=None)) -> dict:
    """Tests métier : l'utilisateur est désigné par l'en-tête X-User-Email (créé au besoin).

    L'authentification réelle (mot de passe + cookie) est testée à part avec `auth_client`.
    """
    from app.database import get_conn

    if not x_user_email:
        raise HTTPException(status_code=401, detail="Session expirée : reconnecte-toi.")
    email = x_user_email.strip().lower()
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
        row = conn.execute(
            "SELECT id, email, created_at, last_login_at FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row)


def _make_client(tmp_path, monkeypatch, override: bool):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
    from fastapi.testclient import TestClient

    from app.deps import current_user
    from app.main import app
    from app.services import auth

    auth.throttle.reset()
    if override:
        app.dependency_overrides[current_user] = _user_from_test_header
    return TestClient(app), app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Client de test : base SQLite temporaire, sans planificateur, utilisateur via X-User-Email."""
    c, app = _make_client(tmp_path, monkeypatch, override=True)
    with c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    """Client de test avec la vraie authentification (mot de passe + cookie de session)."""
    c, app = _make_client(tmp_path, monkeypatch, override=False)
    app.dependency_overrides.clear()
    with c:
        yield c
