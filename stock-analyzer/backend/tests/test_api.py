def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    for table in ("users", "watchlists", "watchlist_items", "alerts", "analysis_history"):
        assert table in body["database"]["tables"]


def test_analyze_requires_query(client):
    assert client.get("/analyze").status_code == 422


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


def test_profile_and_known_users(client):
    client.post("/users/login", json={"email": "a@exemple.be"})
    client.post("/users/login", json={"email": "b@exemple.be"})
    h = {"X-User-Email": "A@Exemple.be"}  # casse indifférente
    client.post("/watchlists", json={"name": "Tech US"}, headers=h)

    r = client.get("/users/me", headers=h)
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@exemple.be"
    assert r.json()["stats"] == {"watchlists": 1, "products": 0, "active_alerts": 0, "analyses": 0}
    assert client.get("/users/me").status_code == 401

    known = [u["email"] for u in client.get("/users/known").json()["users"]]
    assert set(known) == {"a@exemple.be", "b@exemple.be"}


def test_data_kept_after_switching_user(client):
    """Changer d'utilisateur ne supprime rien : on retrouve ses watchlists en revenant."""
    client.post("/users/login", json={"email": "a@exemple.be"})
    client.post("/watchlists", json={"name": "Long terme"}, headers={"X-User-Email": "a@exemple.be"})
    client.post("/users/logout")
    client.post("/users/login", json={"email": "b@exemple.be"})
    client.post("/users/logout")
    client.post("/users/login", json={"email": "a@exemple.be"})
    names = [w["name"] for w in client.get("/watchlists", headers={"X-User-Email": "a@exemple.be"}).json()["watchlists"]]
    assert names == ["Long terme"]


def test_analyze_saves_history(client, monkeypatch):
    from app.services import market

    fake = {
        "query": "NOW", "query_kind": "ticker", "status": "ok", "message": "",
        "product": {"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "type": "ACTION"},
        "quote": {"price": 100.0}, "sources": [{"name": "Yahoo Finance", "ok": True}],
    }
    monkeypatch.setattr(market, "analyze", lambda *a, **k: fake)
    client.post("/users/login", json={"email": "a@exemple.be"})
    h = {"X-User-Email": "a@exemple.be"}
    assert client.get("/analyze", params={"q": "NOW"}, headers=h).json()["status"] == "ok"
    assert client.get("/users/me", headers=h).json()["stats"]["analyses"] == 1


def test_quote_unavailable(client, monkeypatch):
    from app.services import market

    monkeypatch.setattr(market, "get_quote", lambda *a, **k: None)
    assert client.get("/quote", params={"id": "yf:XYZ"}).status_code == 503


def test_decision_saves_scores(client, monkeypatch):
    from app.services import analysis

    full = {
        "product": {"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "type": "ACTION"},
        "quote": {"price": 100.0},
        "decision": {"available": True, "score": 5.5, "buy": {"level": "PRUDENCE"},
                     "components": [{"key": "fundamental", "score": 8.0}, {"key": "technical", "score": 4.3},
                                    {"key": "sentiment", "score": 3.6}]},
    }
    monkeypatch.setattr(analysis, "run", lambda *a, **k: full)
    client.post("/users/login", json={"email": "a@exemple.be"})
    h = {"X-User-Email": "a@exemple.be"}
    assert client.get("/decision", params={"id": "yf:NOW"}, headers=h).json()["decision"]["score"] == 5.5
    from app.database import get_conn

    with get_conn() as conn:
        row = conn.execute("SELECT score_global, score_technical, verdict FROM analysis_history").fetchone()
    assert (row["score_global"], row["score_technical"], row["verdict"]) == (5.5, 4.3, "PRUDENCE")
