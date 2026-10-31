"""Mot de passe oublié : lien par mail, usage unique, 1 heure, sans révéler si le compte existe."""
from app.database import get_conn
from app.services.mail import sender

PW = "correct-horse-42"


def setup(auth_client, monkeypatch):
    mails = []
    monkeypatch.setattr(sender, "send", lambda to, subj, text, html=None: mails.append((to, subj, text)) or
                        {"delivered": True, "status": "Envoyé", "file": None})
    auth_client.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    auth_client.cookies.clear()
    return mails


def token_from(mails):
    return mails[-1][2].split("reinitialiser=")[1].split()[0]


def test_reset_flow(auth_client, monkeypatch):
    c = auth_client
    mails = setup(c, monkeypatch)
    r1 = c.post("/users/password/forgot", json={"email": "Jean@Exemple.be", "app_url": "https://1.2.3.4.sslip.io"}).json()
    r2 = c.post("/users/password/forgot", json={"email": "inconnu@exemple.be"}).json()
    assert r1 == r2 and "Si un compte existe" in r1["message"]  # rien n'est révélé
    assert len(mails) == 1 and mails[0][0] == "jean@exemple.be" and "https://1.2.3.4.sslip.io/?reinitialiser=" in mails[0][2]
    tok = token_from(mails)
    assert c.get(f"/users/password/reset/{tok}").json() == {"email": "jean@exemple.be"}

    other = c.__class__(c.app)
    other.post("/users/login", json={"email": "jean@exemple.be", "password": PW})  # autre appareil connecté
    assert c.post("/users/password/reset", json={"token": tok, "password": "court"}).status_code == 422
    r = c.post("/users/password/reset", json={"token": tok, "password": "nouveau-mdp-2026"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "jean@exemple.be"
    assert c.get("/watchlists").status_code == 200          # connecté directement
    assert other.get("/watchlists").status_code == 401      # autres appareils déconnectés
    assert c.post("/users/password/reset", json={"token": tok, "password": "encore-un-autre-1"}).status_code == 400  # usage unique
    c.cookies.clear()
    assert c.post("/users/login", json={"email": "jean@exemple.be", "password": PW}).status_code == 401
    assert c.post("/users/login", json={"email": "jean@exemple.be", "password": "nouveau-mdp-2026"}).status_code == 200


def test_reset_link_expires_and_new_request_cancels_old(auth_client, monkeypatch):
    c = auth_client
    mails = setup(c, monkeypatch)
    c.post("/users/password/forgot", json={"email": "jean@exemple.be"})
    old = token_from(mails)
    c.post("/users/password/forgot", json={"email": "jean@exemple.be"})
    new = token_from(mails)
    assert c.get(f"/users/password/reset/{old}").status_code == 404
    with get_conn() as conn:
        conn.execute("UPDATE password_resets SET expires_at = datetime('now', '-1 minute')")
    assert c.get(f"/users/password/reset/{new}").status_code == 404
    assert c.post("/users/password/reset", json={"token": new, "password": "nouveau-mdp-2026"}).status_code == 400


def test_forgot_is_rate_limited(auth_client, monkeypatch):
    c = auth_client
    setup(c, monkeypatch)
    for _ in range(5):
        assert c.post("/users/password/forgot", json={"email": "jean@exemple.be"}).status_code == 200
    assert c.post("/users/password/forgot", json={"email": "jean@exemple.be"}).status_code == 429
