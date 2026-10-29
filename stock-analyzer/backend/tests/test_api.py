def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    for table in ("users", "watchlists", "watchlist_items", "alerts", "analysis_history"):
        assert table in body["database"]["tables"]


def test_analyze_placeholder(client):
    r = client.get("/analyze", params={"q": "NOW"})
    assert r.status_code == 200
    assert r.json()["status"] == "not_implemented"


def test_login_remember_logout(client):
    assert client.get("/users/current").json()["user"] is None

    r = client.post("/users/login", json={"email": "Jean@Exemple.be"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "jean@exemple.be"

    # Reconnu au lancement suivant
    assert client.get("/users/current").json()["user"]["email"] == "jean@exemple.be"

    client.post("/users/logout")
    assert client.get("/users/current").json()["user"] is None


def test_login_rejects_invalid_email(client):
    assert client.post("/users/login", json={"email": "pas-un-mail"}).status_code == 422


def test_watchlists_scoped_to_user(client):
    client.post("/users/login", json={"email": "a@exemple.be"})
    client.post("/users/login", json={"email": "b@exemple.be"})
    a = {"X-User-Email": "a@exemple.be"}
    b = {"X-User-Email": "b@exemple.be"}

    assert client.get("/watchlists").status_code == 401

    r = client.post("/watchlists", json={"name": "Tech US", "color": "#3B82F6"}, headers=a)
    assert r.status_code == 201
    assert r.json()["watchlist"]["item_count"] == 0

    dup = client.post("/watchlists", json={"name": "Tech US"}, headers=a)
    assert dup.status_code == 409
    bad = client.post("/watchlists", json={"name": "X", "color": "#123456"}, headers=a)
    assert bad.status_code == 422

    assert [w["name"] for w in client.get("/watchlists", headers=a).json()["watchlists"]] == ["Tech US"]
    assert client.get("/watchlists", headers=b).json()["watchlists"] == []


def test_alerts_deleted_with_item(client):
    """Les alertes d'un produit disparaissent quand on retire le produit."""
    from app.database import get_conn

    client.post("/users/login", json={"email": "a@exemple.be"})
    wl = client.post("/watchlists", json={"name": "Test"}, headers={"X-User-Email": "a@exemple.be"})
    wl_id = wl.json()["watchlist"]["id"]
    with get_conn() as conn:
        item = conn.execute(
            "INSERT INTO watchlist_items (watchlist_id, symbol) VALUES (?, 'NOW')", (wl_id,)
        ).lastrowid
        conn.execute(
            "INSERT INTO alerts (item_id, alert_type, unsubscribe_token) VALUES (?, 'SIGNAL_FORT', 't1')",
            (item,),
        )
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlists WHERE id = ?", (wl_id,))
        assert conn.execute("SELECT COUNT(*) FROM watchlist_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
