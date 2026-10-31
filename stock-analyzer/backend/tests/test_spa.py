"""Fiches publiques : /apprendre/... renvoie la page unique de l'interface, sans connexion."""
import pytest

from app.main import WEB_DIR


@pytest.mark.skipif(not (WEB_DIR / "index.html").exists(), reason="interface non construite")
def test_spa_fallback(auth_client):
    c = auth_client
    for path in ("/", "/apprendre", "/apprendre/rsi", "/apprendre/inconnue"):
        r = c.get(path)
        assert r.status_code == 200 and '<div id="root">' in r.text, path
    assert c.get("/assets/absent.js").status_code == 404
    assert c.get("/favicon.svg").headers["content-type"].startswith("image/svg")
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/api/watchlists").status_code == 401  # l'outil reste protégé
