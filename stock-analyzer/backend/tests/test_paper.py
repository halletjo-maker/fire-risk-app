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

    def item(sym, price, signal="ACHAT", score=8.0, kind="≈", buy=None, sell=None, stop=None, ccy="USD",
             above_m200=1, guard=0):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, last_score, "
                "last_signal, buy_price, buy_kind, sell_price, stop_price, currency, above_m200, guard) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (wl, sym, f"yf:{sym}", sym, price, score, signal, buy or price, kind, sell or price * 1.2,
                 stop or price * 0.9, ccy, above_m200, guard))

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
    item("EEE", 110, above_m200=0)              # sous la MM200 : pas d'achat
    item("FFF", 95, above_m200=None)            # MM200 inconnue (historique court) : pas d'achat
    r = client.post("/portfolios", json={"watchlist_id": wl}, headers=H)
    assert r.status_code == 201
    pid = r.json()["portfolio"]["id"]
    pos = positions(pid)
    assert set(pos) == {"AAA", "BBB"}
    assert pos["AAA"]["qty"] == 6 and pos["AAA"]["entry_fx"] == 1.25 and pos["BBB"]["qty"] == 9
    assert pos["AAA"]["stop"] == pytest.approx(85) and pos["AAA"]["target"] is None   # stop suiveur 15 %, pas d'objectif
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    spent = sum(p["qty"] * p["entry_price"] / p["entry_fx"] + p["entry_fee"] for p in pos.values())
    fees = sum(p["entry_fee"] for p in pos.values())
    assert d["cash"] == pytest.approx(5000 - spent, abs=0.01)
    # Frais Saxo Bronze + TOB : AAA (USD) 480 € → courtage 0,9 € min + change 0,25 % + TOB 0,35 %
    assert pos["AAA"]["entry_fee"] == pytest.approx(0.9 + 480 * (0.0025 + 0.0035), abs=0.02)
    assert pos["BBB"]["entry_fee"] == pytest.approx(2 + 450 * 0.0035, abs=0.02)   # EUR : min. 2 € + TOB
    assert d["fees_paid"] == pytest.approx(fees, abs=0.01) and d["open_count"] == 2
    assert d["value"] == pytest.approx(5000 - fees, abs=0.01)  # seuls les frais sont perdus au départ
    assert d["history"][0]["value_eur"] == pytest.approx(5000 - fees, abs=0.01)
    assert client.get(f"/portfolios/{pid}", headers={"X-User-Email": "b@exemple.be"}).status_code == 404


def test_sell_rules_and_cooldown(setup):
    client, wl, item, set_item = setup
    item("WIN", 100)
    item("TRL", 100)
    item("GRD", 100)
    pid = client.post("/portfolios", json={"watchlist_id": wl}, headers=H).json()["portfolio"]["id"]
    assert len(positions(pid)) == 3

    set_item("WIN", last_price=150, sell_price=120)   # bien au-delà de l'ancien objectif : on garde
    set_item("TRL", last_price=125)                   # monte : le stop suit (125 × 0,85 = 106,25)
    set_item("GRD", guard=1, last_price=101)          # tendance de fond baissière : vente
    paper.run(pid)
    closed = positions(pid, "CLOSED")
    assert "WIN" not in closed and positions(pid)["WIN"]["stop"] == pytest.approx(127.5)
    assert closed["GRD"]["exit_reason"].startswith("Tendance de fond baissière")
    assert positions(pid)["TRL"]["stop"] == pytest.approx(106.25)

    set_item("TRL", last_price=106)
    paper.run(pid)
    trl = positions(pid, "CLOSED")["TRL"]
    assert trl["exit_reason"] == "Stop suiveur touché (gains protégés)" and trl["pnl_eur"] > 0

    # Toujours ACHAT, mais vendu il y a moins de 5 jours : pas de rachat
    set_item("GRD", last_price=100, guard=0)
    paper.run(pid)
    assert "GRD" not in positions(pid)
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["stats"]["closed"] == 2 and d["trades"][0]["exit_reason"]
    assert d["open_count"] == 1


def test_stop_loss_and_max_positions(setup):
    client, wl, item, set_item = setup
    for i in range(4):
        item(f"S{i}", 100, score=8 + i / 10)
    r = client.post("/portfolios", json={"watchlist_id": wl, "max_positions": 2}, headers=H).json()["portfolio"]
    pos = positions(r["id"])
    assert set(pos) == {"S3", "S2"}  # meilleurs scores, 2 lignes maximum
    set_item("S3", last_price=84)    # sous le stop (85)
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


def test_opportunities_portfolio_uses_all_wide_lists(setup, monkeypatch):
    from app.services import screens

    client, wl, item, set_item = setup
    created = []
    monkeypatch.setattr(screens, "create_preset_watchlist", lambda uid, key: created.append(key) or 0)
    monkeypatch.setattr(screens, "refresh_in_background", lambda wid: None)
    with get_conn() as conn:
        uid = conn.execute("SELECT id FROM users WHERE email = 'a@exemple.be'").fetchone()["id"]
        for kind, sym, score, ts in (("screen:world", "MSFT", 8.0, "2026-11-06 10:00:00"),
                                     ("screen:opportunites", "NVDA", 9.0, "2026-11-06 11:00:00"),
                                     ("screen:ipo10", "MSFT", 4.0, "2026-11-05 10:00:00")):   # doublon plus ancien
            wid = conn.execute("INSERT INTO watchlists (user_id, name, kind) VALUES (?, ?, ?)", (uid, kind, kind)).lastrowid
            conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, last_score, "
                         "last_signal, currency, above_m200, last_refresh_at) VALUES (?, ?, ?, ?, 100, ?, ?, 'USD', 1, ?)",
                         (wid, sym, f"yf:{sym}", sym, score, "ACHAT" if score >= 7.5 else "NEUTRE", ts))
    item("TECH", 100)   # watchlist manuelle : hors univers « toutes les listes larges »
    r = client.post("/portfolios", json={"universe": "all"}, headers=H).json()["portfolio"]
    assert r["name"] == "Opportunités" and r["watchlist"]["kind"] == "universe:all"
    assert set(created) == {"ipo5"}                     # seule la liste manquante est créée
    assert set(positions(r["id"])) == {"MSFT", "NVDA"}  # MSFT : la donnée la plus récente (ACHAT) l'emporte


def test_opportunities_filter(monkeypatch):
    from app.services import screens

    fake = {"most_actives": [{"symbol": "BIG", "quoteType": "EQUITY", "marketCap": 5e10, "regularMarketPrice": 50,
                              "longName": "Big Corp Common Stock", "currency": "USD", "region": "US"},
                             {"symbol": "PENNY", "quoteType": "EQUITY", "marketCap": 2e8, "regularMarketPrice": 0.5}],
            "day_gainers": [{"symbol": "BIG", "quoteType": "EQUITY", "marketCap": 5e10, "regularMarketPrice": 50},
                            {"symbol": "ETF1", "quoteType": "ETF", "marketCap": 5e10, "regularMarketPrice": 50}]}
    monkeypatch.setattr(screens.yahoo.yf, "screen", lambda q, count=25: {"quotes": fake.get(q, [])})
    m = screens.opportunities()
    assert [x["symbol"] for x in m] == ["BIG"] and m[0]["name"] == "Big Corp" and m[0]["zone"] == "americas"


def test_turbo_call_portfolio(setup):
    """Turbos Call levier 2 sur la liste Monde 500 : barrière, stop suiveur sur le sous-jacent, frais."""
    from app.services import turbo

    client, wl, item, set_item = setup
    with get_conn() as conn:
        uid = conn.execute("SELECT id FROM users WHERE email = 'a@exemple.be'").fetchone()["id"]
        wid = conn.execute("INSERT INTO watchlists (user_id, name, kind) VALUES (?, 'Monde', 'screen:world')",
                           (uid,)).lastrowid
        for sym, ccy, score in (("AAPL", "USD", 9.0), ("ASML.AS", "EUR", 8.5), ("BTC-EUR", "EUR", 9.5)):
            conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, last_score, "
                         "last_signal, currency, above_m200, guard) VALUES (?, ?, ?, ?, 100, ?, 'ACHAT', ?, 1, 0)",
                         (wid, sym, f"yf:{sym}", sym, score, ccy))
    item("TECH", 100)   # liste manuelle : pas utilisée par les turbos
    r = client.post("/portfolios", json={"product": "turbo", "capital": 1000}, headers=H).json()["portfolio"]
    assert r["name"] == "Turbos Call" and r["product"] == "turbo" and r["max_positions"] == 5
    pos = positions(r["id"])
    assert set(pos) == {"AAPL", "ASML.AS"}   # pas de turbo sur les cryptos
    a = pos["ASML.AS"]
    # 200 € par ligne : 1 € + TOB 0,35 % + écart 0,25 % ; levier 2 → barrière à 50, turbo à 50 €
    assert a["financing"] == pytest.approx(50) and a["entry_price"] == pytest.approx(50)
    assert a["entry_fee"] == pytest.approx(1 + 200 * 0.0035 + (200 - 1.7) * 0.0025, abs=0.02)
    assert a["qty"] * 50 + a["entry_fee"] == pytest.approx(200, abs=0.05)
    assert a["stop"] == pytest.approx(85) and a["under_entry"] == 100

    set_item("ASML.AS", last_price=110)   # +10 % sur le sous-jacent ≈ +20 % sur le turbo
    set_item("AAPL", last_price=84)        # sous le stop de 15 % : vente
    paper.run(r["id"])
    d = client.get(f"/portfolios/{r['id']}", headers=H).json()["portfolio"]
    a = next(p for p in d["positions"] if p["symbol"] == "ASML.AS")
    assert a["last_price"] == pytest.approx(60, abs=0.01) and a["under_last"] == 110
    assert a["pnl_pct"] == pytest.approx(18.8, abs=0.5) and a["barrier"] == pytest.approx(50, abs=0.01)
    t = d["trades"][0]
    assert t["symbol"] == "AAPL" and t["exit_price"] == pytest.approx(34, abs=0.01)   # 84 − 50
    assert t["pnl_pct"] == pytest.approx(-33, abs=1.5)                                 # −16 % × levier 2 + frais

    set_item("ASML.AS", last_price=49)    # sous la barrière : turbo désactivé, perte totale
    paper.run(r["id"])
    closed = positions(r["id"], "CLOSED")["ASML.AS"]
    assert closed["exit_reason"].startswith("Barrière") and closed["exit_price"] == 0
    assert closed["pnl_eur"] == pytest.approx(-200, abs=0.05)


def test_turbo_financing_rises():
    from app.services import turbo

    pos = {"financing": 50.0, "entry_at": "2025-11-06 00:00:00"}
    assert turbo.financing_level(pos) > 51.4   # ≈ +3 % en un an
