"""Identification et enchaînement des sources (fallback), sans internet."""
import pytest

from app.services import market
from app.services.sources import boursorama, google_finance, yahoo


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    from app.database import init_db

    init_db()


def _quote(source, **kw):
    base = {"symbol": "NOW", "name": "ServiceNow", "type": "ACTION", "exchange": "NYSE",
            "currency": "USD", "price": 100.0, "prev_close": 110.0, "change": -10.0,
            "change_pct": -9.09, "volume": 1000, "time": None, "source": source}
    return {**base, **kw}


@pytest.mark.parametrize(
    "q, kind",
    [("US81762P1021", "isin"), ("be0003470755", "isin"), ("US81762P1022", "nom"),
     ("NOW", "ticker"), ("now", "ticker"), ("SOLB.BR", "ticker"), ("^FCHI", "ticker"),
     ("ServiceNow", "nom"), ("turbo lvmh", "nom")],
)
def test_query_kind(q, kind):
    assert market.query_kind(q) == kind


def test_yahoo_first(monkeypatch):
    monkeypatch.setattr(yahoo, "quote", lambda s: _quote(yahoo.SOURCE))
    monkeypatch.setattr(google_finance, "quote", lambda *a: pytest.fail("ne doit pas être appelé"))
    r = market.get_quote("yf:NOW")
    assert r["source"] == "Yahoo Finance"
    assert r["sources"] == [{"name": "Yahoo Finance", "ok": True}]
    assert r["product"]["type_label"] == "Action"


def test_fallback_to_google_then_boursorama(monkeypatch):
    monkeypatch.setattr(yahoo, "quote", lambda s: None)
    monkeypatch.setattr(google_finance, "quote", lambda *a: _quote(google_finance.SOURCE, type=None))
    r = market.get_quote("yf:NOW")
    assert r["source"] == "Google Finance"
    assert [s["ok"] for s in r["sources"]] == [False, True]
    assert r["product"]["type"] == "ACTION"

    monkeypatch.setattr(google_finance, "quote", lambda *a: None)
    monkeypatch.setattr(boursorama, "search", lambda q, limit=5: [{"id": "bo:/cours/FF11-SOLB/", "symbol": "SOLB", "exchange": "Euronext Bruxelles"}])
    monkeypatch.setattr(boursorama, "quote", lambda p: _quote(boursorama.SOURCE, derivative=None))
    r = market.get_quote("yf:SOLB.BR")
    assert r["source"] == "Boursorama"
    assert [s["name"] for s in r["sources"]] == ["Yahoo Finance", "Google Finance", "Boursorama"]


def test_all_sources_down(monkeypatch):
    monkeypatch.setattr(yahoo, "quote", lambda s: None)
    monkeypatch.setattr(google_finance, "quote", lambda *a: None)
    monkeypatch.setattr(boursorama, "search", lambda q, limit=5: [])
    assert market.get_quote("yf:XYZ") is None


def test_search_derivatives_first(monkeypatch):
    monkeypatch.setattr(yahoo, "search", lambda *a, **k: pytest.fail("pas de Yahoo pour un turbo"))
    monkeypatch.setattr(boursorama, "search", lambda q, limit=8: [
        {"id": "bo:/a", "symbol": "MC", "name": "LVMH", "type": "ACTION"},
        {"id": "bo:/b", "symbol": None, "name": "MC/VONF PW OPEN", "type": "TURBO"},
    ])
    r = market.search("turbo lvmh")
    assert [c["type"] for c in r["candidates"]] == ["TURBO", "ACTION"]


def test_search_isin_and_euro_crypto(monkeypatch):
    monkeypatch.setattr(yahoo, "search", lambda q, limit=8: [
        {"id": "yf:BTC-USD", "symbol": "BTC-USD", "name": "Bitcoin USD", "type": "CRYPTO"}])
    r = market.search("bitcoin")
    assert [c["symbol"] for c in r["candidates"]] == ["BTC-EUR", "BTC-USD"]
    assert r["candidates"][0]["name"] == "Bitcoin EUR"

    monkeypatch.setattr(yahoo, "search", lambda q, limit=8: [
        {"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "type": "ACTION"}])
    r = market.search("US81762P1021")
    assert r["query_kind"] == "isin" and r["candidates"][0]["isin"] == "US81762P1021"


def test_analyze_not_found(monkeypatch):
    monkeypatch.setattr(yahoo, "search", lambda *a, **k: [])
    monkeypatch.setattr(boursorama, "search", lambda *a, **k: [])
    r = market.analyze("zzzzqqq")
    assert r["status"] == "not_found"
