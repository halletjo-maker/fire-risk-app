import gzip
import sqlite3
from datetime import datetime
from email import message_from_bytes, policy

import pytest


def _admin(c):
    c.post("/users/register", json={"email": "jean@exemple.be", "password": "correct-horse-42"})


def test_local_backup_rotation_and_content(auth_client):
    from app.config import get_settings
    from app.database import get_conn
    from app.services import backup

    _admin(auth_client)
    with get_conn() as conn:
        conn.execute("INSERT INTO data_cache (cache_key, payload) VALUES ('x', 'gros cache')")
    for day in range(1, 18):
        path = backup.local_backup(datetime(2026, 10, day))
    files = backup.local_list()
    assert len(files) == backup.KEEP and files[0]["name"] == "mm100-2026-10-17.db.gz"
    copy = get_settings().database_path.parent / "copie.db"
    copy.write_bytes(gzip.decompress(path.read_bytes()))
    with sqlite3.connect(copy) as conn:
        assert conn.execute("SELECT email FROM users").fetchall() == [("jean@exemple.be",)]
        assert conn.execute("SELECT COUNT(*) FROM data_cache").fetchone()[0] == 0   # cache non sauvegardé
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0     # sessions non plus


def test_weekly_mail_encrypted_and_restorable(auth_client):
    from app.config import get_settings
    from app.restore_backup import restore
    from app.services import backup
    from app.services.mail import sender

    c = auth_client
    _admin(c)
    st = c.get("/admin/backup").json()
    assert st["passphrase_set"] is False
    assert c.post("/admin/backup/send").json()["sent"] is False               # pas de mot de passe choisi
    assert c.put("/admin/backup", json={"passphrase": "court"}).status_code == 422
    st = c.put("/admin/backup", json={"passphrase": "mon secret de secours"}).json()
    assert st["passphrase_set"] is True and "secret" not in str(st)

    r = c.post("/admin/backup/send").json()            # SMTP non configuré → le mail va dans outbox
    assert r["sent"] is False and "outbox" in r["status"]
    eml = sorted(sender.outbox_dir().glob("*.eml"))[-1]
    msg = message_from_bytes(eml.read_bytes(), policy=policy.default)
    assert msg["To"] == "jean@exemple.be" and msg["Subject"].startswith("Sauvegarde MM100")
    att = next(msg.iter_attachments())
    assert att.get_filename().endswith(".mm100")
    blob = att.get_content()
    assert blob.startswith(backup.MAGIC) and b"jean@exemple.be" not in blob   # chiffré

    with pytest.raises(ValueError, match="incorrect"):
        backup.decrypt(blob, "mauvais mot de passe")
    f = get_settings().database_path.parent / "recu.mm100"
    f.write_bytes(blob)
    target = get_settings().database_path.parent / "restauree.db"
    restore(f, "mon secret de secours", target)
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT email FROM users").fetchall() == [("jean@exemple.be",)]


def test_backup_admin_only(auth_client):
    c = auth_client
    _admin(c)
    c.post("/users/logout")
    assert c.get("/admin/backup").status_code == 401


def test_ovh_provider(auth_client, monkeypatch):
    from app.services.mail import sender

    c = auth_client
    _admin(c)
    seen = []
    monkeypatch.setattr(sender, "check_login", lambda u, p, prov="gmail": seen.append((u, p, prov)))
    ok = c.put("/admin/mail", json={"user": "contact@mm100.be", "password": "Mot de passe avec espaces"}).json()
    assert ok["provider"] == "ovh" and seen == [("contact@mm100.be", "Mot de passe avec espaces", "ovh")]
    cfg = sender.smtp_config()
    assert (cfg["host"], cfg["port"], cfg["tls"], cfg["from"]) == ("ssl0.ovh.net", 465, False, "contact@mm100.be")
    msg = sender.build_message("a@b.be", "Test", "texte")
    assert "contact@mm100.be" in msg["From"] and msg["Message-ID"].endswith("@mm100.be>")
