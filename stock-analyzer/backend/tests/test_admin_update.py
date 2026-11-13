"""Bouton « Mettre à jour maintenant » : version installée et demande déposée pour le service système."""
from fastapi.testclient import TestClient

PW = "correct-horse-42"


def test_version_and_update_request(auth_client, tmp_path, monkeypatch):
    from app.routers import admin

    c = auth_client
    c.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    monkeypatch.setattr(admin, "VERSION_FILE", tmp_path / "VERSION")
    monkeypatch.setattr(admin, "UPDATE_UNIT", tmp_path / "absent.path")

    r = c.get("/admin/version").json()
    assert r == {"version": None, "auto_update": False, "update_pending": False}
    assert c.post("/admin/update").status_code == 409  # PC : pas de service de mise à jour

    (tmp_path / "VERSION").write_text("b7cca1e|2026-10-30T15:00:00+01:00|Watchlists : cours | cibles\n")
    unit = tmp_path / "analyse-boursiere-update.path"
    unit.write_text("[Path]")
    monkeypatch.setattr(admin, "UPDATE_UNIT", unit)
    r = c.get("/admin/version").json()
    assert r["version"] == {"commit": "b7cca1e", "date": "2026-10-30T15:00:00+01:00", "subject": "Watchlists : cours | cibles"}
    assert r["auto_update"] is True
    assert c.post("/admin/update").status_code == 202
    assert (tmp_path / "update.request").exists()  # à côté de la base, dossier accessible en écriture
    assert c.get("/admin/version").json()["update_pending"] is True


def test_update_reserved_to_admin(auth_client):
    from app.main import app

    c = auth_client
    c.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    link = c.post("/users/invitations", json={"email": "ami@exemple.be"}).json()["link"]
    f = TestClient(app)
    f.post("/users/register", json={"email": "ami@exemple.be", "password": PW, "invitation": link.split("=")[1]})
    assert f.get("/admin/version").status_code == 403
    assert f.post("/admin/update").status_code == 403
    assert TestClient(app).post("/admin/update").status_code == 401
