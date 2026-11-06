"""Cours d'achat / de vente potentiels et suggestions inspirées d'une watchlist."""
import time

import pytest

from app.services import targets


def full(price=100.0, support=None, resistance=None, m100=None, above=None, ptype="ACTION", chart=None):
    mm = {"value": m100, "above": above} if m100 else None
    return {"product": {"type": ptype}, "quote": {"price": price},
            "technical": {"applicable": True, "levels": {"support": support, "resistance": resistance},
                          "mm100": mm, "chart": chart or []}}


def test_uptrend_buy_on_pullback_to_closest_floor():
    r = targets.compute(full(price=100, support=92, resistance=115, m100=95, above=True))
    assert r["buy_price"] == 95 and r["buy_kind"] == "≤" and "MM100" in r["buy_note"]
    assert r["sell_price"] == 115 and "résistance" in r["sell_note"]


def test_uptrend_near_floor_means_buy_zone_reached():
    r = targets.compute(full(price=100, support=99.2, resistance=112, m100=90, above=True))
    assert r["buy_kind"] == "≈" and r["buy_price"] == 100 and "support" in r["buy_note"]


def test_downtrend_waits_for_return_above_mm100():
    r = targets.compute(full(price=90, support=85, resistance=120, m100=100, above=False))
    assert r["buy_kind"] == "≥" and r["buy_price"] == pytest.approx(101.0)
    assert r["sell_price"] == 120  # résistance au-dessus du seuil d'achat


def test_target_from_volatility_when_no_room_to_resistance():
    chart = [{"high": 102 + (i % 2), "low": 98 - (i % 2), "close": 100} for i in range(30)]  # ATR ≈ 4,5 %
    r = targets.compute(full(price=100, support=95, resistance=101, m100=96, above=True, chart=chart))
    assert r["sell_price"] == pytest.approx(100 * (1 + 0.135), rel=0.02) and "volatilité" in r["sell_note"]
    r = targets.compute(full(price=100, support=95, resistance=None, m100=96, above=True))
    assert r["sell_price"] == pytest.approx(108)  # sans historique : +8 %


def test_not_computed_for_derivatives_or_without_technical():
    assert targets.compute(full(ptype="TURBO", m100=90, above=True)) is None
    assert targets.compute({"product": {"type": "ACTION"}, "quote": {"price": 10},
                            "technical": {"applicable": False}}) is None


def test_refresh_stores_targets_and_api_returns_them(client, monkeypatch):
    from app.services import analysis

    data = full(price=100, support=92, resistance=115, m100=95, above=True)
    data.update(product={"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "type": "ACTION"},
                decision={"available": True, "score": 7.8, "signal": "ACHAT"})
    data["quote"]["change_pct"] = 1.2
    monkeypatch.setattr(analysis, "run", lambda pid, isin=None: data)
    H = {"X-User-Email": "a@exemple.be"}
    wl = client.post("/watchlists", json={"name": "Tech"}, headers=H).json()["watchlist"]["id"]
    from app.database import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name) VALUES (?, 'NOW', 'yf:NOW', 'ServiceNow')", (wl,))
    from app.services import watchlist
    watchlist.refresh_all()
    item = client.get(f"/watchlists/{wl}/items", headers=H).json()["items"][0]
    assert (item["buy_price"], item["buy_kind"], item["sell_price"]) == (95, "≤", 115)
    dup = client.post(f"/watchlists/{wl}/duplicate", headers=H).json()["watchlist"]["id"]
    assert client.get(f"/watchlists/{dup}/items", headers=H).json()["items"][0]["sell_price"] == 115


def snap(sym, score, status="AU-DESSUS"):
    return {"id": f"yf:{sym}", "symbol": sym, "name": sym, "type": "ACTION", "currency": "USD", "price": 10.0,
            "change_pct": 0.5, "technical_score": score, "mm100_status": status, "mm100_distance_pct": 4.0}


def test_build_suggestions(monkeypatch):
    from app.services import report, suggestions

    peers = {"NOW": ["CRM", "ADBE", "NOW2"], "MSFT": ["CRM", "GOOG", "NOW"], "ASML.AS": [], "ASML": ["AMAT"]}
    scores = {"CRM": 7.5, "ADBE": 4.0, "NOW2": 6.0, "GOOG": 8.1, "AMAT": 5.6, "IWDA.AS": 6.2}
    monkeypatch.setattr(report, "_peers", lambda s: peers.get(s, []))
    monkeypatch.setattr(report, "_snapshot", lambda s: snap(s, scores[s]) if s in scores else None)
    items = [
        {"symbol": "NOW", "product_id": "yf:NOW", "name": "ServiceNow", "product_type": "ACTION", "last_score": 6, "last_signal": "NEUTRE"},
        {"symbol": "MSFT", "product_id": "yf:MSFT", "name": "Microsoft", "product_type": "ACTION", "last_score": 8, "last_signal": "ACHAT"},
        {"symbol": "ASML.AS", "product_id": "yf:ASML.AS", "name": "ASML", "product_type": "ACTION", "last_score": 5, "last_signal": "NEUTRE"},
    ]
    r = suggestions.build(items)
    syms = [s["symbol"] for s in r["items"]]
    # NOW déjà suivi exclu, ADBE (4,0) écarté, tri par score technique, max 4 + ETF de diversification
    assert syms == ["GOOG", "CRM", "NOW2", "AMAT", "IWDA.AS"]
    crm = next(s for s in r["items"] if s["symbol"] == "CRM")
    assert "Microsoft" in crm["reason"] and "ServiceNow" in crm["reason"]
    assert r["items"][-1]["kind"] == "diversification"
    assert r["based_on"][0] == "Microsoft"  # signal ACHAT en premier


def test_suggestions_endpoint_runs_in_background(client, monkeypatch):
    from app.services import report

    monkeypatch.setattr(report, "_peers", lambda s: ["CRM"])
    monkeypatch.setattr(report, "_snapshot", lambda s: snap(s, 7.0))
    H = {"X-User-Email": "a@exemple.be"}
    wl = client.post("/watchlists", json={"name": "Tech"}, headers=H).json()["watchlist"]["id"]
    r = client.get(f"/watchlists/{wl}/suggestions", headers=H).json()
    assert r["status"] == "ready" and r["items"] == [] and "Ajoute" in r["message"]

    from app.database import get_conn
    with get_conn() as conn:
        conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, product_type) "
                     "VALUES (?, 'NOW', 'yf:NOW', 'ServiceNow', 'ETF')", (wl,))
    assert client.get(f"/watchlists/{wl}/suggestions", headers=H).json()["status"] == "pending"
    for _ in range(50):
        r = client.get(f"/watchlists/{wl}/suggestions", headers=H).json()
        if r["status"] == "ready":
            break
        time.sleep(0.1)
    assert r["status"] == "ready" and [s["symbol"] for s in r["items"]] == ["CRM"]
    # Watchlist d'un autre utilisateur : refusée
    assert client.get(f"/watchlists/{wl}/suggestions", headers={"X-User-Email": "b@exemple.be"}).status_code == 404
