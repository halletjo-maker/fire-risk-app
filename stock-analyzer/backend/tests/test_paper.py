"""Portefeuille fictif : règles d'achat / de vente, frais, change, stop suiveur."""
import pytest

from app.database import get_conn
from app.services import paper

H = {"X-User-Email": "a@exemple.be"}


@pytest.fixture()
def setup(client, monkeypatch):
    monkeypatch.setattr(paper, "fx_rate", lambda ccy: {"USD": 1.25, "EUR": 1.0}.get(ccy or "EUR"))
    monkeypatch.setattr(paper, "_quote_price", lambda s: None)
    wl = client.post("/watchlists", json={"name": "Tech"}, headers=H).json()["watchlist"]["id"]

    def item(sym, price, signal="ACHAT", score=8.0, kind="≈", buy=None, sell=None, stop=None, ccy="USD"):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, last_score, "
                "last_signal, buy_price, buy_kind, sell_price, stop_price, currency) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (wl, sym, f"yf:{sym}", sym, price, score, signal, buy or price, kind, sell or price * 1.2,
                 stop or price * 0.9, ccy))

    def set_item(sym, **kw):
        with get_conn() as conn:
            for k, v in kw.items():
                conn.execute(f"UPDATE watchlist_items SET {k} = ? WHERE symbol = ?", (v, sym))

    return client, wl, item, set_item


def positions(pid, status="OPEN"):
    with get_conn() as conn:
        return {r["symbol"]: dict(r) for r in conn.execute(
            "SELECT * FROM portfolio_positions WHERE portfolio_id = ? AND status = ?", (pid, status))}


def test_buys_best_scores_within_slots(setup):
    client, wl, item, _ = setup
    item("AAA", 100, score=9.0)                 # 500 € → 625 $ → 6 actions
    item("BBB", 50, score=8.0, ccy="EUR")       # 500 € → 9 actions (frais déduits)
    item("CCC", 2000, score=8.5)                # 1 action coûte 1 600 € > 500 € : ignoré
    item("DDD", 100, signal="NEUTRE")           # pas de signal ACHAT
    item("EEE", 110, kind="≤", buy=100)         # attend un repli à 100
    item("FFF", 95, kind="≥", buy=100)          # attend un retour au-dessus de 100
    r = client.post("/portfolios", json={"watchlist_id": wl}, headers=H)
    assert r.status_code == 201
    pid = r.json()["portfolio"]["id"]
    pos = positions(pid)
    assert set(pos) == {"AAA", "BBB"}
    assert pos["AAA"]["qty"] == 6 and pos["AAA"]["entry_fx"] == 1.25 and pos["BBB"]["qty"] == 9
    assert pos["AAA"]["stop"] == pytest.approx(90) and pos["AAA"]["target"] == pytest.approx(120)
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    spent = 6 * 100 / 1.25 + 9 * 50 + 2 * paper.FEE_MIN
    assert d["cash"] == pytest.approx(5000 - spent, abs=0.01)
    assert d["fees_paid"] == 2.0 and d["open_count"] == 2
    assert d["value"] == pytest.approx(5000 - 2, abs=0.01)  # seuls les frais sont perdus au départ
    assert d["history"][0]["value_eur"] == pytest.approx(4998, abs=0.01)
    assert client.get(f"/portfolios/{pid}", headers={"X-User-Email": "b@exemple.be"}).status_code == 404


def test_sell_rules_and_cooldown(setup):
    client, wl, item, set_item = setup
    item("TGT", 100)
    item("TRL", 100)
    item("SIG", 100)
    pid = client.post("/portfolios", json={"watchlist_id": wl}, headers=H).json()["portfolio"]["id"]
    assert len(positions(pid)) == 3

    set_item("TGT", last_price=121)                   # objectif 120 atteint
    set_item("TRL", last_price=115)                   # monte : le stop suit (115 × 0,9 = 103,5)
    set_item("SIG", last_signal="VENTE", last_price=101)
    paper.run(pid)
    closed = positions(pid, "CLOSED")
    assert closed["TGT"]["exit_reason"] == "Objectif de vente atteint" and closed["TGT"]["pnl_eur"] > 0
    assert closed["SIG"]["exit_reason"] == "Signal passé à VENTE"
    assert positions(pid)["TRL"]["stop"] == pytest.approx(103.5)

    set_item("TRL", last_price=103)
    paper.run(pid)
    trl = positions(pid, "CLOSED")["TRL"]
    assert trl["exit_reason"] == "Stop suiveur touché (gains protégés)" and trl["pnl_eur"] > 0

    # Toujours ACHAT et dans la zone, mais vendu il y a moins de 5 jours : pas de rachat
    set_item("TGT", last_price=100, last_signal="ACHAT")
    paper.run(pid)
    assert "TGT" not in positions(pid)
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["stats"]["closed"] == 3 and d["stats"]["wins"] >= 2 and d["trades"][0]["exit_reason"]
    assert d["open_count"] == 0 and d["invested"] == 0


def test_stop_loss_and_max_positions(setup):
    client, wl, item, set_item = setup
    for i in range(4):
        item(f"S{i}", 100, score=8 + i / 10)
    r = client.post("/portfolios", json={"watchlist_id": wl, "max_positions": 2}, headers=H).json()["portfolio"]
    pos = positions(r["id"])
    assert set(pos) == {"S3", "S2"}  # meilleurs scores, 2 lignes maximum
    set_item("S3", last_price=89)    # sous le stop (90)
    paper.run(r["id"])
    c = positions(r["id"], "CLOSED")["S3"]
    assert c["exit_reason"] == "Stop-loss touché" and c["pnl_eur"] < 0
    assert set(positions(r["id"])) == {"S2", "S1"}  # la place libérée est reprise


def test_list_and_delete(setup):
    client, wl, item, _ = setup
    item("AAA", 100)
    pid = client.post("/portfolios", json={"watchlist_id": wl, "capital": 10000}, headers=H).json()["portfolio"]["id"]
    lst = client.get("/portfolios", headers=H).json()["portfolios"]
    assert lst[0]["initial_cash"] == 10000 and lst[0]["name"] == "Fictif · Tech" and "positions" not in lst[0]
    assert client.post("/portfolios", json={"watchlist_id": 9999}, headers=H).status_code == 404
    assert client.delete(f"/portfolios/{pid}", headers=H).status_code == 200
    assert client.get("/portfolios", headers=H).json()["portfolios"] == []


def test_fx_rate_pence(monkeypatch):
    from app.services.sources import yahoo
    monkeypatch.setattr(yahoo, "quote", lambda s: {"price": 0.85} if s == "EURGBP=X" else None)
    monkeypatch.setattr(paper.cache, "get", lambda k, t: None)
    monkeypatch.setattr(paper.cache, "put", lambda *a, **k: None)
    assert paper.fx_rate("EUR") == 1.0
    assert paper.fx_rate("GBp") == pytest.approx(85.0)
    assert paper.fx_rate("JPY") is None
