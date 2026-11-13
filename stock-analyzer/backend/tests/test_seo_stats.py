"""Référencement (titres par page, sitemap, robots) et compteur de visites sans cookie."""
import pytest
from fastapi.testclient import TestClient

from app.main import WEB_DIR

built = pytest.mark.skipif(not (WEB_DIR / "seo.json").exists(), reason="interface non construite")
UA = "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/156.0 Mobile Safari/537.36"


@built
def test_meta_per_page_and_sitemap(auth_client, monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://mm100.be")
    c = auth_client
    h = c.get("/apprendre/taxe-plus-values").text
    assert "<title>La taxe sur les plus-values (depuis 2026) · MM100</title>" in h
    assert '<link rel="canonical" href="https://mm100.be/apprendre/taxe-plus-values" />' in h
    assert 'property="og:url" content="https://mm100.be/apprendre/taxe-plus-values"' in h and "noindex" not in h
    assert "10 000 € par personne" in h.split('name="description" content="')[1].split('"')[0]
    assert 'content="noindex"' in c.get("/apprendre/inexistante").text
    sm = c.get("/sitemap.xml")
    assert sm.headers["content-type"].startswith("application/xml")
    assert "<loc>https://mm100.be/apprendre/tob-taxe-de-bourse</loc>" in sm.text and "<loc>https://mm100.be/</loc>" in sm.text
    assert "Sitemap: https://mm100.be/sitemap.xml" in c.get("/robots.txt").text


@built
def test_visit_counter(auth_client):
    from app.main import app

    admin = auth_client
    admin.post("/users/register", json={"email": "jean@exemple.be", "password": "correct-horse-42"})
    v1, v2 = TestClient(app), TestClient(app)
    h1 = {"user-agent": UA}
    v1.post("/public/hit", json={"path": "/", "referrer": "https://www.reddit.com/r/BEFire/"}, headers=h1)
    v1.post("/public/hit", json={"path": "/apprendre/taxe-plus-values", "referrer": "http://testserver/"}, headers=h1)
    v2.post("/public/hit", json={"path": "/apprendre/taxe-plus-values", "ref": "whatsapp"},
            headers={"user-agent": UA + " autre"})
    v2.post("/public/hit", json={"path": "/apprendre/taxe-plus-values"}, headers={"user-agent": "Googlebot/2.1"})  # robot
    v2.post("/public/hit", json={"path": "/watchlists"}, headers={"user-agent": UA})                               # pas public
    admin.post("/public/hit", json={"path": "/"}, headers=h1)                                                      # membre connecté
    s = admin.get("/admin/stats?days=7").json()
    assert (s["visitors"], s["views"]) == (2, 3) and s["today"] == {"visitors": 2, "views": 3}
    assert s["pages"][0] == {"path": "/apprendre/taxe-plus-values", "title": "La taxe sur les plus-values (depuis 2026)", "views": 2}
    assert {x["source"]: x["visitors"] for x in s["sources"]} == {"Reddit": 1, "WhatsApp": 1}
    assert len(s["series"]) == 7
    assert v1.get("/admin/stats").status_code == 401
