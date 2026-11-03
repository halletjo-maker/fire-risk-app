"""Rachats d'actions, free cash-flow sur 3 ans, garde-fou MM200."""
import numpy as np
import pandas as pd

from app.services import decision, fundamentals, technical

FIN = {"years": ["2025", "2024", "2023", "2022"], "fcf": [120.0, 100.0, 90.0, 80.0],
       "repurchase": [50.0, 40.0, 30.0, None], "dividends": [30.0, 28.0, 25.0, 20.0],
       "shares_years": ["2025", "2024", "2023", "2022"], "shares": [940.0, 970.0, 1000.0, 1030.0]}


def test_share_trend_buyback_and_dilution():
    st = fundamentals.share_trend(FIN)
    assert st["years"] == 3 and st["buyback"] is True and -3.1 < st["pct_per_year"] < -2.9
    assert st["repurchased"] == 120.0
    dil = fundamentals.share_trend({"shares_years": ["2025", "2023"], "shares": [110.0, 100.0]})
    assert dil["buyback"] is False and dil["pct_per_year"] > 4
    assert fundamentals.share_trend({"shares_years": ["2025"], "shares": [1.0]}) is None


def test_fcf_average_and_trend():
    fa = fundamentals.fcf_average(FIN)
    assert fa["avg"] == (120 + 100 + 90) / 3 and fa["years"] == 3 and round(fa["trend_pct"]) == 33


def test_stock_uses_three_year_accounts(monkeypatch):
    from app.services.sources import boursorama, yahoo

    monkeypatch.setattr(yahoo, "info", lambda s: {"quoteType": "EQUITY", "longName": "X", "marketCap": 2000.0,
                                                   "dividendRate": 1.0, "freeCashflow": 10.0})
    monkeypatch.setattr(yahoo, "next_earnings", lambda s: None)
    monkeypatch.setattr(yahoo, "financials", lambda s: FIN)
    monkeypatch.setattr(boursorama, "find_listing", lambda *a, **k: None)
    r = fundamentals._stock({"id": "yf:X", "symbol": "X", "currency": "USD"}, {"price": 50.0})
    by = {c["key"]: c for c in r["criteria"]}
    assert "moyenne 3 ans" in by["fcf"]["label"] and round(by["fcf"]["value"], 2) == 5.17
    assert "hausse" in by["fcf"]["comment"]
    assert by["shares"]["score"] == 8 and "rachète" in by["shares"]["comment"]
    assert "Couvert" in by["dividend"]["comment"]
    assert r["shares_trend"]["buyback"] is True
    assert any(i["label"].startswith("Rachats d'actions") for i in r["info"])


def _df(prices):
    idx = pd.bdate_range(end="2026-10-30", periods=len(prices))
    p = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame({"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": 1e6})


def test_mm200_guard_blocks_buy_signal():
    # Longue baisse puis rebond au-dessus de la MM100, toujours sous une MM200 qui baisse
    prices = list(np.linspace(200, 100, 230)) + list(np.linspace(100, 120, 30))
    d = technical.indicators(_df(prices))
    lt = technical.long_trend(d)
    assert lt["below"] and lt["falling"] and lt["guard"] and technical.mm100_status(d)["above"]
    assert decision.signal(8.0) == "ACHAT" and decision.signal(8.0, guard=True) == "NEUTRE"
    assert decision.signal(4.0, guard=True) == "VENTE"
    tech = {"score": 8.5, "long_trend": lt, "inverse": False}
    d1 = decision.compute({"score": 8.0}, tech, {"score": 8.0})
    assert d1["signal"] == "NEUTRE" and d1["guard"] and d1["buy"]["level"] == "PRUDENCE"
    assert d1["notes"][0].startswith("🛡️ Garde-fou MM200")
    assert decision.compute({"score": 8.0}, {**tech, "inverse": True}, {"score": 8.0})["signal"] == "ACHAT"  # turbo PUT


def test_no_guard_in_uptrend():
    d = technical.indicators(_df(list(np.linspace(100, 200, 260))))
    assert technical.long_trend(d)["guard"] is False


def test_portfolio_flags_buybacks(client, monkeypatch):
    from app.database import get_conn
    from app.services import paper
    from app.services.sources import yahoo

    seen = []
    monkeypatch.setattr(yahoo, "financials", lambda s: seen.append(s) or FIN)
    with get_conn() as conn:
        conn.execute("INSERT INTO users (email) VALUES ('a@b.be')")
        pid = conn.execute("INSERT INTO portfolios (user_id, name, initial_cash, cash) VALUES (1, 'P', 5000, 5000)").lastrowid
        for sym in ("AAPL", "BTC-EUR"):
            conn.execute("INSERT INTO portfolio_positions (portfolio_id, symbol, name, qty, entry_price) VALUES (?, ?, ?, 1, 10)",
                         (pid, sym, sym))
    assert paper.refresh_share_trends(pid) == 2 and seen == ["AAPL"]   # pas de comptes pour une crypto
    assert paper.refresh_share_trends(pid) == 0                        # revu au plus une fois par mois
    with get_conn() as conn:
        s = paper.summary(conn, conn.execute("SELECT * FROM portfolios WHERE id = ?", (pid,)).fetchone())
    flags = {p["symbol"]: p["buyback"] for p in s["positions"]}
    assert flags == {"AAPL": True, "BTC-EUR": False}


def test_thin_fundamentals_weigh_less():
    full = {"score": 1.5, "coverage": 1.0, "criteria": [{"score": 1.5}] * 8}
    thin = {"score": 1.5, "coverage": 0.125, "criteria": [{"score": 1.5}] + [{"score": None}] * 7}
    tech, sent = {"score": 5.4, "inverse": False}, {"score": 5.3}
    d_full = decision.compute(full, tech, sent)
    d_thin = decision.compute(thin, tech, sent)
    w = {c["key"]: c["weight"] for c in d_thin["components"]}
    assert w["fundamental"] < 0.15 and abs(sum(w.values()) - 1) < 0.01
    assert d_thin["score"] > d_full["score"]
    assert any("trop incomplets (1 critère sur 8)" in n for n in d_thin["notes"])
    half = {"score": 6.0, "coverage": 0.5, "criteria": [{"score": 6}] * 4 + [{"score": None}] * 4}
    assert {c["key"]: c["weight"] for c in decision.compute(half, tech, sent)["components"]}["fundamental"] == 0.35
