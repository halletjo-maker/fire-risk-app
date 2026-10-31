"""Filtre de marché (MSCI World vs MM100) et courbe de comparaison des portefeuilles fictifs."""
import pytest

from app.database import get_conn
from app.services import paper, regime

H = {"X-User-Email": "a@exemple.be"}


def series(last_factor, n=120, start="2026-06-01"):
    """n clôtures à 100 puis une dernière à 100 × last_factor."""
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    out = [((d0 + timedelta(days=i)).isoformat(), 100.0) for i in range(n - 1)]
    out.append(((d0 + timedelta(days=n - 1)).isoformat(), 100.0 * last_factor))
    return out


def test_regime(monkeypatch):
    monkeypatch.setattr(regime, "closes", lambda: series(0.9))
    r = regime.regime()
    assert r["available"] and r["ok"] is False and r["distance_pct"] < 0
    monkeypatch.setattr(regime, "closes", lambda: series(1.05))
    assert regime.regime()["ok"] is True
    monkeypatch.setattr(regime, "closes", lambda: series(1.0, n=50))
    assert regime.regime() == {"available": False, "ok": True, "label": regime.LABEL}


def test_indexed(monkeypatch):
    monkeypatch.setattr(regime, "closes", lambda: [("2026-10-28", 100.0), ("2026-10-30", 102.0), ("2026-11-02", 99.0)])
    # Base = clôture du jour de création (ou la précédente) ; jours sans cotation = dernière connue
    assert regime.indexed(["2026-10-30", "2026-10-31", "2026-11-02"], "2026-10-29", 5000) == [5100.0, 5100.0, 4950.0]


@pytest.fixture()
def portfolio(client, monkeypatch):
    monkeypatch.setattr(paper, "fx_rate", lambda ccy: 1.0)
    wl = client.post("/watchlists", json={"name": "W"}, headers=H).json()["watchlist"]["id"]
    with get_conn() as conn:
        conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, last_price, last_score, "
                     "last_signal, buy_price, buy_kind, sell_price, stop_price, currency) "
                     "VALUES (?, 'AAA', 'yf:AAA', 'AAA', 100, 8, 'ACHAT', 100, '≈', 120, 90, 'EUR')", (wl,))
    return client, wl


def test_bear_market_blocks_buys_not_sells(portfolio, monkeypatch):
    client, wl = portfolio
    monkeypatch.setattr(regime, "closes", lambda: series(0.9))
    pid = client.post("/portfolios", json={"watchlist_id": wl}, headers=H).json()["portfolio"]["id"]
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["open_count"] == 0 and "Achats suspendus" in d["note"] and d["regime"]["ok"] is False

    monkeypatch.setattr(regime, "closes", lambda: series(1.05))  # le marché se reprend
    paper.run(pid)
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["open_count"] == 1 and d["note"] is None

    monkeypatch.setattr(regime, "closes", lambda: series(0.9))  # rechute : la vente à l'objectif reste possible
    with get_conn() as conn:
        conn.execute("UPDATE watchlist_items SET last_price = 121")
    paper.run(pid)
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["open_count"] == 0 and d["stats"]["closed"] == 1


def test_detail_has_benchmark_curve(portfolio, monkeypatch):
    client, wl = portfolio
    pid = client.post("/portfolios", json={"watchlist_id": wl}, headers=H).json()["portfolio"]["id"]
    with get_conn() as conn:
        day = conn.execute("SELECT day FROM portfolio_values").fetchone()[0]
        created = conn.execute("SELECT substr(created_at, 1, 10) FROM portfolios").fetchone()[0]
    monkeypatch.setattr(regime, "closes", lambda: [(created, 50.0), ("2099-01-01", 60.0)])
    d = client.get(f"/portfolios/{pid}", headers=H).json()["portfolio"]
    assert d["benchmark_label"] == "ETF MSCI World"
    assert d["history"] == [{"day": day, "value_eur": pytest.approx(4999, abs=1), "benchmark_eur": 5000.0}]
