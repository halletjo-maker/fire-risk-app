"""Test de la méthode sur le passé : simulation sur des cours fabriqués (sans réseau)."""
import numpy as np
import pandas as pd

from app.services import backtest


def _df(prices, start="2016-01-04"):
    idx = pd.bdate_range(start=start, periods=len(prices))
    p = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame({"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": 1e6})


def test_simulation_buys_in_uptrend_and_respects_stops(monkeypatch):
    rng = np.random.default_rng(1)
    up = 100 * np.cumprod(1 + 0.0015 + rng.normal(0, 0.01, 900))
    crash = up[-1] * np.cumprod(1 - 0.004 + rng.normal(0, 0.01, 300))
    hist = {"UP": _df(np.concatenate([up, crash]))}
    bench = _df(np.linspace(100, 200, 1200))
    monkeypatch.setattr(backtest.yahoo, "history_many", lambda syms, period="1y": {s: hist[s] for s in syms if s in hist})
    monkeypatch.setattr(backtest.yahoo, "history", lambda sym, period="2y": bench)
    r = backtest.run(["UP"], 3)
    rules = r["variants"]["rules"]["stats"]
    assert r["tested"] == 1 and rules["trades"] >= 1 and 0 < rules["exposure_pct"] <= 100
    assert r["variants"]["old"]["stats"]["trades"] >= 1
    assert rules["max_drawdown_pct"] > -40          # les stop-loss limitent la chute du krach
    assert r["benchmark"]["stats"]["total_pct"] > 0 and set(r["variants"]) == {"rules", "old", "no_market", "tight_stop"}
    assert r["equal_weight"]["stats"]["total_pct"] is not None


def test_entry_rule_matches_paper_portfolios():
    base = {"price": 100, "buy_price": 99, "stop_price": 92}
    assert backtest.entry_ok({**base, "buy_kind": "≈"})
    assert not backtest.entry_ok({**base, "buy_kind": "≤"}) and backtest.entry_ok({**base, "buy_kind": "≤", "buy_price": 99.6})
    assert backtest.entry_ok({**base, "buy_kind": "≥"}) and not backtest.entry_ok({**base, "buy_kind": "≥", "stop_price": 101})


def test_api_launch_and_latest(client, monkeypatch):
    from app.database import get_conn
    import threading

    H = {"X-User-Email": "a@exemple.be"}
    wl = client.post("/watchlists", json={"name": "Test"}, headers=H).json()
    wid = (wl.get("watchlist") or wl)["id"]
    assert client.post("/backtest", json={"watchlist_id": wid, "years": 5}, headers=H).status_code == 400  # liste vide
    with get_conn() as conn:
        conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, name, product_id) VALUES (?, 'UP', 'Up', 'yf:UP')", (wid,))
    monkeypatch.setattr(backtest, "run", lambda syms, years, progress=None: {"variants": {}, "tested": len(syms)})
    monkeypatch.setattr(threading.Thread, "start", lambda self: self.run())   # exécution immédiate
    r = client.post("/backtest", json={"watchlist_id": wid, "years": 5}, headers=H)
    assert r.status_code == 202
    b = client.get("/backtest", headers=H).json()["backtest"]
    assert b["status"] == "done" and b["result"]["tested"] == 1 and b["result"]["params"]["list"] == "Test"
