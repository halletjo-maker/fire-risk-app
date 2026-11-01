"""Site public : portefeuille témoin et demandes d'accès."""
from email import policy
from email.parser import BytesParser

from fastapi.testclient import TestClient

PW = "correct-horse-42"


def _admin(c):
    assert c.post("/users/register", json={"email": "jean@exemple.be", "password": PW}).status_code == 200
    return c


def _visitor():
    from app.main import app
    return TestClient(app)


def _portfolio(conn, user_id, name="Fictif · Monde"):
    wl = conn.execute("INSERT INTO watchlists (user_id, name) VALUES (?, ?)", (user_id, 'Monde 500' if name.startswith('Fictif') else name)).lastrowid
    pid = conn.execute("INSERT INTO portfolios (user_id, watchlist_id, name, initial_cash, cash) VALUES (?, ?, ?, 5000, 2000)",
                       (user_id, wl, name)).lastrowid
    conn.execute("INSERT INTO portfolio_positions (portfolio_id, symbol, name, qty, entry_price, last_price) "
                 "VALUES (?, 'ASML.AS', 'ASML', 5, 600, 660)", (pid,))
    conn.execute("INSERT INTO portfolio_values (portfolio_id, day, value_eur) VALUES (?, '2026-10-01', 5000)", (pid,))
    return pid


def test_showcase_portfolio(auth_client):
    from app.database import get_conn

    c = _admin(auth_client)
    v = _visitor()
    assert v.get("/public/portfolio").status_code == 404
    with get_conn() as conn:
        uid = conn.execute("SELECT id FROM users").fetchone()["id"]
        p1, p2 = _portfolio(conn, uid), _portfolio(conn, uid, "Mon perso")
    assert c.get(f"/portfolios/{p1}").json()["portfolio"]["can_publish"] is True
    assert c.post(f"/portfolios/{p1}/public", json={"public": True}).json() == {"is_public": True}
    assert c.post(f"/portfolios/{p2}/public", json={"public": True}).status_code == 200   # un seul à la fois
    assert c.get(f"/portfolios/{p1}").json()["portfolio"]["is_public"] is False

    r = v.get("/public/portfolio").json()
    assert r["list"] == "Mon perso" and r["value"] == 5300 and r["pnl_pct"] == 6.0  # nom de la liste suivie
    assert r["positions"][0]["name"] == "ASML" and r["positions"][0]["weight_pct"] == 62.3
    assert "jean@exemple.be" not in str(r) and "id" not in r

    c.post(f"/portfolios/{p2}/public", json={"public": False})
    assert v.get("/public/portfolio").status_code == 404


def test_only_admin_publishes(auth_client):
    from app.database import get_conn

    c = _admin(auth_client)
    tok = c.post("/users/invitations", json={"email": "ami@exemple.be"}).json()["link"].split("invitation=")[1]
    f = _visitor()
    f.post("/users/register", json={"email": "ami@exemple.be", "password": PW, "invitation": tok})
    with get_conn() as conn:
        uid = conn.execute("SELECT id FROM users WHERE email = 'ami@exemple.be'").fetchone()["id"]
        pid = _portfolio(conn, uid)
    assert f.get(f"/portfolios/{pid}").json()["portfolio"]["can_publish"] is False
    assert f.post(f"/portfolios/{pid}/public", json={"public": True}).status_code == 403


def test_access_request_flow(auth_client, tmp_path):
    c = _admin(auth_client)
    v = _visitor()
    r = v.post("/public/access-request", json={"email": "Curieux@Exemple.be", "message": "Vu sur WhatsApp"})
    assert r.status_code == 202 and r.json()["ok"] is True
    assert v.post("/public/access-request", json={"email": "curieux@exemple.be"}).json()["ok"] is True  # doublon : même réponse
    assert v.post("/public/access-request", json={"email": "robot@exemple.be", "website": "spam"}).json()["ok"] is True
    assert v.post("/public/access-request", json={"email": "jean@exemple.be"}).json()["ok"] is True  # déjà membre
    reqs = c.get("/users/access-requests").json()["requests"]
    assert [(x["email"], x["message"]) for x in reqs] == [("curieux@exemple.be", "Vu sur WhatsApp")]
    assert v.get("/users/access-requests").status_code == 401

    outbox = tmp_path / "outbox"
    notif = [BytesParser(policy=policy.default).parse(p.open("rb")) for p in outbox.glob("*.eml")]
    assert any(m["To"] == "jean@exemple.be" and "curieux@exemple.be" in m["Subject"] for m in notif)

    acc = c.post(f"/users/access-requests/{reqs[0]['id']}/accept", json={"app_url": "https://mm100.be"}).json()
    assert acc["link"].startswith("https://mm100.be/?invitation=")
    mails = [BytesParser(policy=policy.default).parse(p.open("rb")) for p in outbox.glob("*.eml")]
    inv = next(m for m in mails if m["To"] == "curieux@exemple.be")
    assert "jean@exemple.be" not in inv.get_content() and inv["Subject"] == "Ton accès à MM100"
    tok = acc["link"].split("invitation=")[1]
    assert v.get(f"/users/invitation/{tok}").json()["invited_by"] is None   # l'administrateur reste anonyme
    assert c.get("/users/access-requests").json()["requests"] == []


def test_access_request_decline_and_throttle(auth_client):
    c = _admin(auth_client)
    v = _visitor()
    v.post("/public/access-request", json={"email": "a@exemple.be"})
    rid = c.get("/users/access-requests").json()["requests"][0]["id"]
    assert c.delete(f"/users/access-requests/{rid}").json() == {"ok": True}
    codes = [v.post("/public/access-request", json={"email": f"x{i}@exemple.be"}).status_code for i in range(6)]
    assert codes[:4] == [202] * 4 and codes[-1] == 429
