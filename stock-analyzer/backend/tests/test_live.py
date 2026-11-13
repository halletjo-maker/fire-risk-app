"""Cours rapides (5 min) et alerte « forte variation du jour »."""
from app.database import get_conn
from app.services import live, market, push, world

H = {"X-User-Email": "a@exemple.be"}


def test_fast_prices_and_big_move_alert(client, monkeypatch):
    wl = client.post("/watchlists", json={"name": "Tech"}, headers=H).json()["watchlist"]["id"]
    with get_conn() as conn:
        for sym in ("NOVA", "CALM"):
            conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, "
                         "last_change_pct, currency) VALUES (?, ?, ?, ?, 10, 0, 'USD')", (wl, sym, f"yf:{sym}", sym))
    quotes = {"yf:NOVA": {"price": 11.0, "change_pct": 7.2}, "yf:CALM": {"price": 10.1, "change_pct": 1.0}}
    traded = {"yf:NOVA", "yf:CALM"}
    monkeypatch.setattr(market, "get_quote", lambda pid, isin=None: {"quote": quotes[pid]})
    monkeypatch.setattr(world, "open_zones", lambda now=None: {"crypto", "americas"})   # Bourse US ouverte
    sent = []
    monkeypatch.setattr(push, "notify_later", lambda uid, kind, title, body, url="/": sent.append((kind, title, body)))

    assert live.fast_prices() == 2
    with get_conn() as conn:
        assert conn.execute("SELECT last_price, last_change_pct FROM watchlist_items WHERE symbol = 'NOVA'").fetchone()[:] == (11.0, 7.2)

    assert live.check_moves("2026-11-13", traded) == 1
    assert sent[0][0] == "alerts" and "NOVA" in sent[0][1] and "+7,2 %" in sent[0][2]
    assert live.check_moves("2026-11-13", traded) == 0   # une fois par jour
    quotes["yf:NOVA"] = {"price": 10.5, "change_pct": 5.1}  # a encore bougé après l'alerte, puis clôture
    live.fast_prices()
    assert live.check_moves("2026-11-14", set()) == 0    # samedi : pas de séance, pas d'alerte
    quotes["yf:NOVA"] = {"price": 9.7, "change_pct": -7.3}
    live.fast_prices()
    assert live.check_moves("2026-11-16", traded) == 1 and sent[-1][1].startswith("📉")


def test_traded_on():
    assert live.traded_on({"time": "2026-11-13T15:30:00-05:00"}, "2026-11-13")
    assert not live.traded_on({"time": "2026-11-13T22:00:00+01:00"}, "2026-11-14")
    assert not live.traded_on({}, "2026-11-14") and live.traded_on({}, "2026-11-13")   # samedi / vendredi


def test_holdings_refresh_button(client, monkeypatch):
    from app.services import holdings

    asked = []
    monkeypatch.setattr(live, "fast_prices", lambda ids=None: asked.append(ids) or 0)
    monkeypatch.setattr(holdings, "refresh_quotes", lambda only=None: 0)
    from app.routers import holdings as router
    router._last_refresh.clear()
    r = client.post("/holdings/refresh", headers=H)
    assert r.status_code == 200 and "positions" in r.json() and asked == [[]]
    client.post("/holdings/refresh", headers=H)
    assert asked == [[]]                     # 2e appui dans les 30 s : pas de nouvelle mise à jour


def test_closed_markets_only_crypto(client, monkeypatch):
    wl = client.post("/watchlists", json={"name": "Mix"}, headers=H).json()["watchlist"]["id"]
    with get_conn() as conn:
        for sym in ("AAPL", "BTC-EUR"):
            conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name) VALUES (?, ?, ?, ?)",
                         (wl, sym, f"yf:{sym}", sym))
    asked = []
    monkeypatch.setattr(market, "get_quote", lambda pid, isin=None: asked.append(pid) or {"quote": {"price": 1}})
    monkeypatch.setattr(world, "open_zones", lambda now=None: {"crypto"})   # nuit / week-end
    live.fast_prices()
    assert asked == ["yf:BTC-EUR"]
