"""Module 8 — watchlists : CRUD, produits, ordre, cascades, rafraîchissement."""
import pytest

H = {"X-User-Email": "a@exemple.be"}
OTHER = {"X-User-Email": "b@exemple.be"}

QUOTES = {
    "yf:NOW": {"product": {"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "type": "ACTION", "isin": None,
                           "exchange": "NYSE", "currency": "USD"}, "quote": {"price": 109.0, "change_pct": -27.4}},
    "yf:SOLB.BR": {"product": {"id": "yf:SOLB.BR", "symbol": "SOLB.BR", "name": "Solvay", "type": "ACTION",
                               "isin": "BE0003470755", "exchange": "Brussels", "currency": "EUR"},
                   "quote": {"price": 23.8, "change_pct": 0.1}},
    "yf:IWDA.AS": {"product": {"id": "yf:IWDA.AS", "symbol": "IWDA.AS", "name": "iShares MSCI World", "type": "ETF",
                               "isin": None, "exchange": "Amsterdam", "currency": "EUR"},
                   "quote": {"price": 131.5, "change_pct": -0.2}},
}


@pytest.fixture()
def api(client, monkeypatch):
    from app.services import analysis, market

    monkeypatch.setattr(market, "get_quote", lambda pid, isin=None: QUOTES.get(pid))
    scores = {"yf:NOW": (5.5, "NEUTRE"), "yf:SOLB.BR": (4.6, "VENTE"), "yf:IWDA.AS": (7.8, "ACHAT")}

    def fake_run(pid, isin=None):
        s, sig = scores[pid]
        return {"product": QUOTES[pid]["product"], "quote": QUOTES[pid]["quote"],
                "decision": {"available": True, "score": s, "signal": sig}}

    monkeypatch.setattr(analysis, "run", fake_run)
    client.post("/users/login", json={"email": "a@exemple.be"})
    client.post("/users/login", json={"email": "b@exemple.be"})
    return client


def make(api, name="Tech US", color="#3B82F6"):
    return api.post("/watchlists", json={"name": name, "color": color}, headers=H).json()["watchlist"]


def add(api, wl, pid):
    return api.post(f"/watchlists/{wl}/items", json={"product_id": pid}, headers=H)


def test_add_items_scores_refreshed_in_background(api):
    wl = make(api)["id"]
    r = add(api, wl, "yf:NOW")
    assert r.status_code == 201
    item = r.json()["item"]
    assert item["name"] == "ServiceNow" and item["last_price"] == 109.0 and item["product_type"] == "ACTION"
    items = api.get(f"/watchlists/{wl}/items", headers=H).json()["items"]
    # la tâche d'arrière-plan a calculé score et signal
    assert items[0]["last_score"] == 5.5 and items[0]["last_signal"] == "NEUTRE" and items[0]["last_refresh_at"]
    assert add(api, wl, "yf:NOW").status_code == 409          # déjà présent
    assert add(api, wl, "yf:UNKNOWN").status_code == 503      # introuvable


def test_rename_color_and_conflicts(api):
    a, b = make(api, "A")["id"], make(api, "B")["id"]
    r = api.patch(f"/watchlists/{a}", json={"name": "Green Energy", "color": "#00FF88"}, headers=H)
    assert r.json()["watchlist"]["name"] == "Green Energy" and r.json()["watchlist"]["color"] == "#00FF88"
    assert api.patch(f"/watchlists/{b}", json={"name": "Green Energy"}, headers=H).status_code == 409
    assert api.patch(f"/watchlists/{b}", json={"color": "#123456"}, headers=H).status_code == 422
    assert api.patch(f"/watchlists/{a}", json={"name": "X"}, headers=OTHER).status_code == 404  # pas à lui


def test_reorder_items(api):
    wl = make(api)["id"]
    ids = [add(api, wl, p).json()["item"]["id"] for p in ("yf:NOW", "yf:SOLB.BR", "yf:IWDA.AS")]
    new = [ids[2], ids[0], ids[1]]
    assert api.put(f"/watchlists/{wl}/items/order", json={"ids": new}, headers=H).status_code == 200
    assert [i["id"] for i in api.get(f"/watchlists/{wl}/items", headers=H).json()["items"]] == new
    assert api.put(f"/watchlists/{wl}/items/order", json={"ids": new[:2]}, headers=H).status_code == 422


def test_remove_item_deletes_its_alerts(api):
    from app.database import get_conn

    wl = make(api)["id"]
    item = add(api, wl, "yf:NOW").json()["item"]["id"]
    with get_conn() as conn:
        conn.execute("INSERT INTO alerts (item_id, alert_type, unsubscribe_token) VALUES (?, 'SIGNAL_FORT', 'tok')", (item,))
    r = api.delete(f"/watchlists/{wl}/items/{item}", headers=H)
    assert r.json()["deleted"] == {"id": item, "name": "ServiceNow", "symbol": "NOW", "alerts": 1}
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0


def test_duplicate_and_delete_watchlist(api):
    wl = make(api, "Long terme")["id"]
    add(api, wl, "yf:NOW"); add(api, wl, "yf:IWDA.AS")
    dup = api.post(f"/watchlists/{wl}/duplicate", headers=H).json()["watchlist"]
    assert dup["name"] == "Long terme (copie)" and dup["item_count"] == 2
    dup2 = api.post(f"/watchlists/{wl}/duplicate", headers=H).json()["watchlist"]
    assert dup2["name"] == "Long terme (copie) (2)"
    r = api.delete(f"/watchlists/{wl}", headers=H).json()["deleted"]
    assert r["name"] == "Long terme" and r["items"] == 2
    names = [w["name"] for w in api.get("/watchlists", headers=H).json()["watchlists"]]
    assert names == ["Long terme (copie)", "Long terme (copie) (2)"]
    assert api.get(f"/watchlists/{wl}/items", headers=H).status_code == 404


def test_refresh_all_updates_each_product_once(api, monkeypatch):
    from app.services import analysis, watchlist

    a, b = make(api, "A")["id"], make(api, "B")["id"]
    add(api, a, "yf:NOW"); add(api, b, "yf:NOW"); add(api, b, "yf:SOLB.BR")
    calls = []
    real = analysis.run
    monkeypatch.setattr(analysis, "run", lambda pid, isin=None: calls.append(pid) or real(pid))
    assert watchlist.refresh_all() == 2
    assert sorted(calls) == ["yf:NOW", "yf:SOLB.BR"]  # NOW une seule fois malgré 2 watchlists


def test_migration_adds_product_id(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript("CREATE TABLE watchlist_items (id INTEGER PRIMARY KEY, watchlist_id INTEGER, symbol TEXT, position INTEGER);")
    conn.close()
    monkeypatch.setenv("DATABASE_PATH", str(db))
    from app.database import init_db

    init_db()
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(watchlist_items)")}
    assert "product_id" in cols
