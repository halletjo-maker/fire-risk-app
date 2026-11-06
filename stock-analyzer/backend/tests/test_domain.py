"""Nom de domaine : vérification DNS avant de demander la configuration du serveur."""
PW = "correct-horse-42"


def setup(auth_client, tmp_path, monkeypatch, dns):
    from app.routers import admin

    unit = tmp_path / "domain.path"
    unit.write_text("[Path]")
    monkeypatch.setattr(admin, "DOMAIN_UNIT", unit)
    monkeypatch.setenv("APP_PUBLIC_URL", "https://2.31.12.35.sslip.io")
    monkeypatch.setattr(admin, "_resolve", lambda name: set(dns.get(name, [])))
    auth_client.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    return tmp_path / "domain.request"


def test_domain_ok_with_www(auth_client, tmp_path, monkeypatch):
    dns = {"2.31.12.35.sslip.io": ["2.31.12.35"], "mm100.be": ["2.31.12.35"], "www.mm100.be": ["2.31.12.35"]}
    req = setup(auth_client, tmp_path, monkeypatch, dns)
    st = auth_client.get("/admin/domain").json()
    assert st["available"] and st["current"] == "2.31.12.35.sslip.io" and st["server_ip"] == "2.31.12.35"
    r = auth_client.post("/admin/domain", json={"domain": "https://www.MM100.be/"})
    assert r.status_code == 202 and r.json()["names"] == ["mm100.be", "www.mm100.be"]
    assert req.read_text() == "mm100.be www.mm100.be\n"
    assert auth_client.get("/admin/domain").json()["pending"] is True


def test_domain_checks(auth_client, tmp_path, monkeypatch):
    dns = {"2.31.12.35.sslip.io": ["2.31.12.35"], "parking.be": ["213.186.33.5"], "nowww.be": ["2.31.12.35"]}
    req = setup(auth_client, tmp_path, monkeypatch, dns)
    r = auth_client.post("/admin/domain", json={"domain": "mm100.be"})
    assert r.status_code == 400 and "pas encore visible" in r.json()["detail"]
    r = auth_client.post("/admin/domain", json={"domain": "parking.be"})
    assert r.status_code == 400 and "213.186.33.5 au lieu de 2.31.12.35" in r.json()["detail"]
    assert auth_client.post("/admin/domain", json={"domain": "pas un domaine"}).status_code == 422
    assert not req.exists()
    assert auth_client.post("/admin/domain", json={"domain": "nowww.be"}).json()["names"] == ["nowww.be"]


def test_domain_unavailable_or_not_admin(auth_client, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import admin

    setup(auth_client, tmp_path, monkeypatch, {})
    monkeypatch.setattr(admin, "DOMAIN_UNIT", tmp_path / "absent")
    assert auth_client.post("/admin/domain", json={"domain": "mm100.be"}).status_code == 409
    assert TestClient(app).get("/admin/domain").status_code == 401
