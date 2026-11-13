"""Inviter un ami : lien à usage unique, droits administrateur, gestion des membres."""
from fastapi.testclient import TestClient

PW = "correct-horse-42"


def admin(c):
    r = c.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    assert r.status_code == 200 and r.json()["user"]["is_admin"] is True
    return c


def invite(c, email="ami@exemple.be"):
    return c.post("/users/invitations", json={"email": email, "app_url": "https://1.2.3.4.sslip.io"})


def token_of(r):
    return r.json()["link"].split("invitation=")[1]


def friend_client():
    from app.main import app
    return TestClient(app)


def test_invitation_flow(auth_client, tmp_path):
    c = admin(auth_client)
    r = invite(c)
    assert r.status_code == 201
    body = r.json()
    assert body["link"].startswith("https://1.2.3.4.sslip.io/?invitation=")
    assert body["mail"]["sent"] is False and "outbox" in body["mail"]["status"]  # SMTP absent : lien à partager
    eml = list((tmp_path / "outbox").glob("*.eml"))
    from email import policy
    from email.parser import BytesParser
    msg = BytesParser(policy=policy.default).parse(eml[0].open("rb"))
    assert len(eml) == 1 and body["link"] in msg.get_content() and msg["To"] == "ami@exemple.be"
    tok = token_of(r)

    f = friend_client()
    info = f.get(f"/users/invitation/{tok}").json()
    assert info["email"] == "ami@exemple.be" and info["invited_by"] == "jean@exemple.be"
    # L'inscription reste fermée sans invitation, et l'invitation est liée à son adresse
    assert f.post("/users/register", json={"email": "ami@exemple.be", "password": PW}).status_code == 403
    assert f.post("/users/register", json={"email": "autre@exemple.be", "password": PW, "invitation": tok}).status_code == 403
    assert f.post("/users/register", json={"email": "ami@exemple.be", "password": "court", "invitation": tok}).status_code == 422
    r = f.post("/users/register", json={"email": "Ami@Exemple.be", "password": PW, "invitation": tok})
    assert r.status_code == 200 and r.json()["user"]["is_admin"] is False
    assert f.get("/watchlists").status_code == 200

    # Usage unique
    g = friend_client()
    assert g.get(f"/users/invitation/{tok}").status_code == 404
    assert g.post("/users/register", json={"email": "ami@exemple.be", "password": PW, "invitation": tok}).status_code == 403

    # Un membre invité ne peut pas inviter à son tour
    assert f.post("/users/invitations", json={"email": "x@exemple.be"}).status_code == 403
    assert f.get("/users/members").status_code == 403

    m = c.get("/users/members").json()
    assert [(u["email"], u["is_admin"], u["is_me"]) for u in m["members"]] == [
        ("jean@exemple.be", True, True), ("ami@exemple.be", False, False)]
    assert m["invitations"] == []
    assert invite(c).status_code == 409  # a déjà un compte


def test_expired_and_cancelled_invitations(auth_client):
    from app.database import get_conn

    c = admin(auth_client)
    tok = token_of(invite(c))
    with get_conn() as conn:
        conn.execute("UPDATE invitations SET expires_at = datetime('now', '-1 minute')")
    assert c.get(f"/users/invitation/{tok}").status_code == 404

    r = invite(c, "marie@exemple.be")
    inv_id = r.json()["invitation"]["id"]
    # Réinviter remplace l'ancien lien
    tok2 = token_of(invite(c, "marie@exemple.be"))
    assert c.get(f"/users/invitation/{token_of(r)}").status_code == 404
    assert [i["email"] for i in c.get("/users/members").json()["invitations"]] == ["marie@exemple.be"]
    new_id = c.get("/users/members").json()["invitations"][0]["id"]
    assert new_id != inv_id
    assert c.delete(f"/users/invitations/{new_id}").status_code == 200
    assert c.get(f"/users/invitation/{tok2}").status_code == 404


def test_remove_member_deletes_access_and_data(auth_client):
    c = admin(auth_client)
    tok = token_of(invite(c))
    f = friend_client()
    f.post("/users/register", json={"email": "ami@exemple.be", "password": PW, "invitation": tok})
    f.post("/watchlists", json={"name": "Perso"})
    friend_id = [u["id"] for u in c.get("/users/members").json()["members"] if not u["is_me"]][0]
    me_id = [u["id"] for u in c.get("/users/members").json()["members"] if u["is_me"]][0]

    assert c.delete(f"/users/members/{me_id}").status_code == 400
    assert c.delete(f"/users/members/{friend_id}").status_code == 200
    assert f.get("/watchlists").status_code == 401
    from app.database import get_conn
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM watchlists WHERE user_id = ?", (friend_id,)).fetchone()[0] == 0


def test_first_password_account_becomes_admin_on_upgrade(auth_client):
    """Base existante (avant les invitations) : le premier compte avec mot de passe devient admin."""
    from app.database import get_conn, init_db
    from app.services import auth

    with get_conn() as conn:
        conn.execute("INSERT INTO users (email, password_hash) VALUES ('jean@exemple.be', ?)", (auth.hash_password(PW),))
        conn.execute("INSERT INTO users (email, password_hash) VALUES ('marie@exemple.be', ?)", (auth.hash_password(PW),))
        conn.execute("UPDATE users SET is_admin = 0")
    init_db()
    with get_conn() as conn:
        assert conn.execute("SELECT email FROM users WHERE is_admin = 1").fetchall()[0][0] == "jean@exemple.be"
        assert conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0] == 1
    r = auth_client.post("/users/login", json={"email": "jean@exemple.be", "password": PW})
    assert r.json()["user"]["is_admin"] is True
    assert auth_client.get("/users/current").json()["user"]["is_admin"] is True
