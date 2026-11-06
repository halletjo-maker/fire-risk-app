"""Module 1 — mot de passe, sessions par cookie, inscription fermée, limitation des essais."""
from app.services import auth

PW = "correct-horse-42"


def register(c, email="jean@exemple.be", pw=PW):
    return c.post("/users/register", json={"email": email, "password": pw})


def test_hash_roundtrip_and_salt():
    h1, h2 = auth.hash_password(PW), auth.hash_password(PW)
    assert h1 != h2 and h1.startswith("scrypt$") and PW not in h1
    assert auth.verify_password(PW, h1) and not auth.verify_password("autre-mot-de-passe", h1)
    assert not auth.verify_password(PW, None) and not auth.verify_password(PW, "corrompu")


def test_first_account_setup_then_registration_closed(auth_client):
    c = auth_client
    st = c.get("/users/current").json()
    assert st == {"user": None, "setup_required": True, "registration_open": True}

    assert register(c, pw="court").status_code == 422
    r = register(c, email="Jean@Exemple.be")
    assert r.status_code == 200 and r.json()["user"]["email"] == "jean@exemple.be"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie

    st = c.get("/users/current").json()
    assert st["user"]["email"] == "jean@exemple.be" and not st["setup_required"] and not st["registration_open"]
    # Un inconnu ne peut plus créer de compte, ni réécrire le mot de passe existant
    c.cookies.clear()
    assert register(c, email="pirate@exemple.be").status_code == 403
    assert register(c, email="jean@exemple.be", pw="nouveau-mdp-123").status_code == 403


def test_api_requires_session(auth_client):
    c = auth_client
    for path in ("/watchlists", "/users/me", "/search?q=apple", "/analyze?q=apple", "/report?id=yf:NOW",
                 "/alerts/history"):
        assert c.get(path).status_code == 401, path
    assert c.get("/health").status_code == 200
    assert c.get("/alerts/unsubscribe/inconnu").status_code == 404  # lien des mails : public (page « lien invalide »)

    register(c)
    assert c.get("/watchlists").status_code == 200
    # Un faux cookie ne donne rien
    c.cookies.set(auth.COOKIE_NAME, "faux-jeton")
    assert c.get("/watchlists").status_code == 401


def test_login_logout_and_bearer(auth_client):
    c = auth_client
    register(c)
    c.post("/users/logout")
    assert c.get("/users/current").json()["user"] is None
    assert c.get("/watchlists").status_code == 401

    bad = c.post("/users/login", json={"email": "jean@exemple.be", "password": "mauvais-mdp"})
    unknown = c.post("/users/login", json={"email": "personne@exemple.be", "password": "mauvais-mdp"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["detail"] == unknown.json()["detail"]  # ne révèle pas si le compte existe

    r = c.post("/users/login", json={"email": "JEAN@exemple.be", "password": PW})
    assert r.status_code == 200
    token = r.cookies[auth.COOKIE_NAME]
    c.cookies.clear()
    assert c.get("/watchlists", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_existing_passwordless_account_keeps_its_data(auth_client):
    """Ancienne installation (connexion par mail seul) : le mot de passe est ajouté au compte existant."""
    from app.database import get_conn

    with get_conn() as conn:
        uid = conn.execute("INSERT INTO users (email) VALUES ('jean@exemple.be')").lastrowid
        conn.execute("INSERT INTO watchlists (user_id, name) VALUES (?, 'Long terme')", (uid,))
    c = auth_client
    assert c.get("/users/current").json()["setup_required"] is True
    # Pas de connexion possible sans mot de passe défini
    assert c.post("/users/login", json={"email": "jean@exemple.be", "password": PW}).status_code == 401
    assert register(c).status_code == 200
    assert [w["name"] for w in c.get("/watchlists").json()["watchlists"]] == ["Long terme"]


def test_allowed_emails(auth_client, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "Jean@Exemple.be, marie@exemple.be")
    c = auth_client
    assert register(c, email="pirate@exemple.be").status_code == 403
    assert register(c).status_code == 200
    c.cookies.clear()
    assert c.get("/users/current").json()["registration_open"] is True
    assert register(c, email="marie@exemple.be").status_code == 200
    assert register(c, email="marie@exemple.be").status_code == 409


def test_throttle_blocks_after_repeated_failures(auth_client):
    c = auth_client
    register(c)
    c.cookies.clear()
    for _ in range(5):
        assert c.post("/users/login", json={"email": "jean@exemple.be", "password": "mauvais-mdp"}).status_code == 401
    r = c.post("/users/login", json={"email": "jean@exemple.be", "password": PW})
    assert r.status_code == 429 and "Réessaie" in r.json()["detail"]


def test_change_password_logs_out_other_devices(auth_client):
    from fastapi.testclient import TestClient

    from app.main import app

    c = auth_client
    register(c)
    other = TestClient(app)
    other.post("/users/login", json={"email": "jean@exemple.be", "password": PW})
    assert other.get("/watchlists").status_code == 200

    assert c.post("/users/password", json={"current_password": "faux", "new_password": "nouveau-mdp-123"}).status_code == 400
    assert c.post("/users/password", json={"current_password": PW, "new_password": "court"}).status_code == 422
    assert c.post("/users/password", json={"current_password": PW, "new_password": "nouveau-mdp-123"}).status_code == 200

    assert c.get("/watchlists").status_code == 200        # cet appareil reste connecté
    assert other.get("/watchlists").status_code == 401    # l'autre est déconnecté
    assert other.post("/users/login", json={"email": "jean@exemple.be", "password": "nouveau-mdp-123"}).status_code == 200


def test_reset_password_cli(auth_client, monkeypatch, capsys):
    from app import reset_password

    register(auth_client)
    answers = iter(["nouveau-mdp-123", "nouveau-mdp-123"])
    monkeypatch.setattr(reset_password, "getpass", lambda prompt="": next(answers))
    monkeypatch.setattr("sys.argv", ["x", "jean@exemple.be"])
    assert reset_password.main() == 0
    assert auth_client.get("/watchlists").status_code == 401  # sessions fermées
    assert auth_client.post("/users/login", json={"email": "jean@exemple.be", "password": "nouveau-mdp-123"}).status_code == 200
