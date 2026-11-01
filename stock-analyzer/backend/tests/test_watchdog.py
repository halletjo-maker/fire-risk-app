"""Alerte de la surveillance du serveur : fonctionne sans le code de l'application."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "watchdog_alert.py"


def load():
    spec = importlib.util.spec_from_file_location("watchdog_alert", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_alert_uses_app_mail_settings(auth_client, tmp_path, monkeypatch):
    from app.database import get_conn

    auth_client.post("/users/register", json={"email": "jean@exemple.be", "password": "correct-horse-42"})
    with get_conn() as conn:
        for k, v in {"smtp_user": "contact@mm100.be", "smtp_password": "secret", "smtp_provider": "ovh",
                     "smtp_from": "contact@mm100.be"}.items():
            conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)", (k, v))
    env = tmp_path / ".env"
    from app.config import get_settings
    env.write_text(f"APP_PUBLIC_URL=https://mm100.be\nDATABASE_PATH={get_settings().database_path}\n")
    wd = load()
    monkeypatch.setattr(wd, "ENV_FILE", env)
    sent = []
    monkeypatch.setattr(wd, "send_mail", lambda cfg, to, subject, text: sent.append((cfg, to, subject, text)))
    assert wd.main(["x", "down", "l'application ne répond plus"]) == 0
    cfg, to, subject, text = sent[0]
    assert (cfg["host"], cfg["port"], cfg["tls"]) == ("ssl0.ovh.net", 465, False)
    assert to == ["jean@exemple.be"] and subject == "⚠️ MM100 ne répond plus"
    assert "https://mm100.be" in text and "l'application ne répond plus" in text
    wd.main(["x", "up", "Rétabli"])
    assert sent[1][2] == "✅ MM100 fonctionne à nouveau"


def test_env_fallback():
    wd = load()
    cfg = wd.smtp_config({"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_USER": "a@gmail.com",
                          "SMTP_PASSWORD": "x"}, {})
    assert cfg["tls"] is True and cfg["from"] == "a@gmail.com"
    assert wd.smtp_config({}, {}) is None
