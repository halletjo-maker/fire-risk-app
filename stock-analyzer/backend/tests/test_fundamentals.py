"""Module 3 — lecture des sources et calcul du score fondamental (sans internet)."""
from pathlib import Path

import pytest

from app.services import fundamentals as F
from app.services import market
from app.services.sources import boursorama, coingecko, google_finance, justetf, yahoo

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    from app.database import init_db

    init_db()


def test_parse_consensus():
    c = boursorama.parse_consensus((FIX / "boursorama_consensus.html").read_text())
    assert c["analysts"] == 17
    assert c["median_rating"] == pytest.approx(3.53)
    assert c["target_median"] == pytest.approx(24.27)
    assert c["upside_pct"] == pytest.approx(1.88)
    assert c["eps_est"] == pytest.approx(2.23)
    assert c["revenue_growth_pct"] == pytest.approx(-4)
    assert c["ebit_margin_pct"] == pytest.approx(457 / 4088 * 100, abs=0.01)
    assert c["net_debt_to_ebitda"] == pytest.approx(1741 / 763, abs=0.01)
    assert c["opinions"]["vendre"] == 5


def test_parse_justetf():
    j = justetf.parse_profile((FIX / "justetf_iwda.html").read_text())
    assert j["ter_pct"] == pytest.approx(0.20)
    assert j["holdings"] == 1252
    assert j["fund_size"] == pytest.approx(133_172e6)
    assert j["index"] == "MSCI World"
    assert j["replication"].startswith("Physique")
    assert j["ytd_pct"] == pytest.approx(18.67)


def test_tier_and_format():
    assert F.tier(12, [(10, 1), (20, 2)], 3) == 2
    assert F.tier(25, [(10, 1), (20, 2)], 3) == 3
    assert F.pct(-5.25, 1) == "−5,2 %" or F.pct(-5.25, 1) == "−5,3 %"
    assert F.big(133_172e6, "EUR") == "133,2 Md EUR"


STOCK = {"id": "yf:SOLB.BR", "symbol": "SOLB.BR", "type": "ACTION", "currency": "EUR", "name": "Solvay"}


def test_stock_falls_back_to_boursorama(monkeypatch):
    """Yahoo refuse (limite de fréquence) → le consensus Boursorama suffit pour noter."""
    monkeypatch.setattr(yahoo, "info", lambda s: None)
    monkeypatch.setattr(yahoo, "next_earnings", lambda s: None)
    monkeypatch.setattr(google_finance, "stats", lambda *a: {"per": 10.0, "market_cap": 2.5e9, "source": "Google Finance"})
    monkeypatch.setattr(boursorama, "find_listing", lambda s, kinds=("ACTION",): {"id": "bo:/cours/FF11-SOLB/"})
    monkeypatch.setattr(boursorama, "consensus", lambda p: boursorama.parse_consensus((FIX / "boursorama_consensus.html").read_text()))
    r = F.analyze(STOCK, {"price": 23.82})
    assert r["applicable"] and r["score"] is not None
    by_key = {c["key"]: c for c in r["criteria"]}
    assert by_key["per"]["value"] == pytest.approx(23.82 / 2.23)  # PER recalculé au cours actuel
    assert by_key["growth"]["source"] == "Boursorama"
    assert by_key["debt"]["score"] == 5.5  # 2,28 × → endettement à surveiller
    assert [s["ok"] for s in r["sources"]] == [False, True, True]
    assert 4 < r["score"] < 7


def test_stock_with_losses(monkeypatch):
    monkeypatch.setattr(yahoo, "info", lambda s: {"quoteType": "EQUITY", "longName": "X", "trailingEps": -1.2,
                                                  "revenueGrowth": 0.3, "targetMeanPrice": 20})
    monkeypatch.setattr(yahoo, "next_earnings", lambda s: None)
    monkeypatch.setattr(boursorama, "find_listing", lambda *a, **k: None)
    r = F.analyze({**STOCK, "id": "yf:XYZ", "symbol": "XYZ"}, {"price": 10.0})
    per = next(c for c in r["criteria"] if c["key"] == "per")
    assert per["score"] == 2 and "perd" in per["comment"]


def test_etf_scores_and_leverage_cap(monkeypatch):
    profile = justetf.parse_profile((FIX / "justetf_iwda.html").read_text())
    monkeypatch.setattr(justetf, "profile", lambda isin: profile)
    etf = {"id": "yf:IWDA.AS", "symbol": "IWDA.AS", "type": "ETF", "isin": "IE00B4L5Y983",
           "currency": "EUR", "name": "iShares Core MSCI World"}
    r = F.analyze(etf, {"price": 131.5})
    assert r["score"] >= 8 and r["verdict"] == "Solide"
    lev = {**etf, "id": "yf:LQQ.PA", "name": "Amundi Nasdaq-100 Daily (2x) Leveraged"}
    r = F.analyze(lev, {"price": 1000})
    assert r["score"] <= 4 and any("levier" in n for n in r["notes"])


def test_turbo_barrier_risk():
    d = {"underlying": "LVMH", "direction": "PUT", "issuer": "SOCIETE GENERALE", "barrier_distance_pct": 3.5,
         "leverage": 25.0, "spread_pct": 1.5, "maturity": "Illimité"}
    r = F.analyze({"id": "bo:/x", "type": "TURBO", "name": "T"}, {"price": 1}, d)
    assert r["verdict"] == "Fragile"
    assert next(c for c in r["criteria"] if c["key"] == "barrier")["score"] == 2.5


def test_crypto_capped(monkeypatch):
    monkeypatch.setattr(coingecko, "market", lambda s, vs="eur": {
        "market_cap": 1.4e12, "volume_24h": 1e11, "rank": 1, "circulating_supply": 20e6,
        "max_supply": 21e6, "ath_change_pct": -30, "currency": "EUR", "source": "CoinGecko"})
    r = F.analyze({"id": "yf:BTC-EUR", "symbol": "BTC-EUR", "type": "CRYPTO", "currency": "EUR"}, {"price": 1})
    assert r["score"] == 8.0  # plafonné : actif sans flux de trésorerie


def test_index_not_applicable():
    r = F.analyze({"id": "yf:^FCHI", "type": "INDICE"}, {"price": 1})
    assert r["applicable"] is False and r["score"] is None


def test_euro_listing_preferred_for_isin(monkeypatch):
    monkeypatch.setattr(yahoo, "search", lambda q, limit=8: [
        {"id": "yf:IWDA.L", "symbol": "IWDA.L", "name": "iShares Core MSCI World", "type": "ETF",
         "exchange": "London", "exchange_code": "LSE", "source": "Yahoo Finance"}])
    monkeypatch.setattr(boursorama, "search", lambda q, limit=10: [
        {"type": "ETF", "symbol": "SWDA", "exchange": "MIL"},
        {"type": "ETF", "symbol": "EUNL", "exchange": "XETRA"},
        {"type": "ETF", "symbol": "IWDA", "exchange": "Euronext Amsterdam"}])
    r = market.search("IE00B4L5Y983")
    assert [c["symbol"] for c in r["candidates"]] == ["IWDA.AS", "EUNL.DE", "IWDA.L"]
    assert r["candidates"][0]["isin"] == "IE00B4L5Y983"
