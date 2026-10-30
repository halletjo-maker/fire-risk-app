"""Liste « Monde 500 + cryptos » : composition, liste de secours, calendrier par zone, cryptos."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import paper, screens, world
from app.database import get_conn

H = {"X-User-Email": "a@exemple.be"}
BXL = ZoneInfo("Europe/Brussels")


def q(sym, name, cur, cap, fin=None, qt="EQUITY", short=None):
    return {"symbol": sym, "longName": name, "shortName": short or name, "currency": cur, "marketCap": cap,
            "quoteType": qt, "financialCurrency": fin or cur}


def nasdaq(sym, name, cap, country="United States"):
    return {"symbol": sym, "name": name, "marketCap": str(cap), "country": country, "ipoyear": ""}


def test_company_key():
    assert world.company_key("Apple Inc.") == world.company_key("APPLE INC.        ") == "apple"
    assert world.company_key("Alphabet Inc. Class C Capital Stock") == "alphabet"
    assert world.company_key("Nestlé S.A.") == "nestle"
    assert world.company_key("Bank of America Corp") != world.company_key("Bank of China Limited")


def test_build_live_filters_and_dedupes(monkeypatch):
    rows = [nasdaq("AAPL", "Apple Inc. Common Stock", 3e12), nasdaq("GOOGL", "Alphabet Inc. Class A Common Stock", 2e12),
            nasdaq("GOOG", "Alphabet Inc. Class C Capital Stock", 1.9e12), nasdaq("JPM", "JP Morgan Chase & Co. Common Stock", 6e11),
            nasdaq("SHEL", "Shell PLC American Depositary Shares", 2e11, country="United Kingdom")]
    monkeypatch.setattr(screens, "fetch_universe", lambda: rows)
    screens_by_region = {
        "jp": [q("7203.T", "Toyota Motor Corporation", "JPY", 4e13)],
        "nl": [q("SHELL.AS", "Shell plc", "EUR", 2e11, fin="USD"), q("ASML.AS", "ASML Holding N.V.", "EUR", 5e11)],
        "fr": [q("ACALS.PA", "CASA1,4%20JUL27", "EUR", 1e11), q("MC.PA", "LVMH Moët Hennessy", "EUR", 3e11)],
        "ch": [q("AAPL.SW", "Apple Inc.", "CHF", 3e12), q("JPM.SW", "JPMorgan Chase & Co.", "CHF", 6e11),
               q("NOVNEE.SW", "Novartis AG", "CHF", 2e11, fin="USD")],
        "gb": [q("TYT.L", "Toyota Motor Corp", "JPY", 4e13), q("AZN.L", "AstraZeneca PLC", "GBp", 2e11, fin="USD")],
        "ca": [q("AAPL.TO", "Apple Inc.", "CAD", 3e12, short="APPLE CDR (CAD HEDGED)"), q("RY.TO", "Royal Bank of Canada", "CAD", 2e11)],
        "de": [q("APC.DE", "Apple Inc.", "EUR", 3e12, fin="USD"), q("SAP.DE", "SAP SE", "EUR", 2.5e11),
               q("639.DE", "Spotify Technology", "EUR", 1e11, fin="USD")],
        "es": [q("XVALO.MC", "Vale S.A.", "EUR", 5e10, fin="USD"), q("ITX.MC", "Industria de Diseño Textil", "EUR", 1.5e11)],
    }
    monkeypatch.setattr(world, "_screen", lambda region, ex, size: screens_by_region.get(region, []))
    monkeypatch.setattr(world.time, "sleep", lambda s: None)
    monkeypatch.setattr(world, "US_QUOTA", 3)
    with pytest.raises(RuntimeError):  # composition trop petite pour être crédible
        world.build_live()
    monkeypatch.setattr(world, "crypto_members", lambda: [{"symbol": f"C{i}-EUR", "name": f"C{i}", "region": "crypto",
                                                           "zone": "crypto", "currency": "EUR", "type": "CRYPTO"} for i in range(400)])
    m = world.build_live()
    stocks = {x["symbol"]: x for x in m if x["type"] == "ACTION"}
    assert set(stocks) == {"AAPL", "GOOGL", "JPM", "7203.T", "SHELL.AS", "ASML.AS", "MC.PA", "NOVN.SW",
                           "AZN.L", "RY.TO", "SAP.DE", "ITX.MC"}
    assert stocks["7203.T"]["zone"] == "asia" and stocks["SAP.DE"]["zone"] == "europe" and stocks["RY.TO"]["zone"] == "americas"


def test_members_falls_back_to_snapshot(monkeypatch):
    def boom():
        raise RuntimeError("Yahoo indisponible")
    monkeypatch.setattr(world, "build_live", boom)
    m = world.members()
    assert len(m) > 450 and {x["zone"] for x in m} == {"asia", "europe", "americas", "crypto"}
    assert sum(1 for x in m if x["type"] == "CRYPTO") == 20


@pytest.mark.parametrize("when,expected", [
    (datetime(2026, 11, 2, 3, 0, tzinfo=BXL), {"crypto", "asia"}),                # lundi nuit
    (datetime(2026, 11, 2, 10, 0, tzinfo=BXL), {"crypto", "asia", "europe"}),
    (datetime(2026, 11, 2, 16, 0, tzinfo=BXL), {"crypto", "europe", "americas"}),
    (datetime(2026, 11, 2, 23, 30, tzinfo=BXL), {"crypto"}),
    (datetime(2026, 11, 1, 16, 0, tzinfo=BXL), {"crypto"}),                       # dimanche
])
def test_open_zones(when, expected):
    assert world.open_zones(when) == expected


def test_world_preset_and_zone_refresh(client, monkeypatch):
    from app.services.sources import yahoo
    from tests.test_screens import fake_df

    members = [
        {"symbol": "7203.T", "name": "Toyota", "region": "jp", "zone": "asia", "currency": "JPY", "type": "ACTION"},
        {"symbol": "SAP.DE", "name": "SAP", "region": "de", "zone": "europe", "currency": "EUR", "type": "ACTION"},
        {"symbol": "AAPL", "name": "Apple", "region": "us", "zone": "americas", "currency": "USD", "type": "ACTION"},
        {"symbol": "BTC-EUR", "name": "Bitcoin", "region": "crypto", "zone": "crypto", "currency": "EUR", "type": "CRYPTO"},
    ]
    monkeypatch.setattr(world, "members", lambda live=True: members)
    calls = []
    monkeypatch.setattr(yahoo, "history_many", lambda syms, period="1y": calls.append(sorted(syms)) or {s: fake_df() for s in syms})
    w = client.post("/watchlists/presets/world", headers=H).json()["watchlist"]
    assert (w["kind"], w["name"], w["item_count"]) == ("screen:world", "Monde 500 + cryptos", 4)
    items = {i["symbol"]: i for i in client.get(f"/watchlists/{w['id']}/items", headers=H).json()["items"]}
    assert items["BTC-EUR"]["zone"] == "crypto" and items["7203.T"]["currency"] == "JPY" and items["SAP.DE"]["region"] == "de"
    with get_conn() as conn:
        assert conn.execute("SELECT product_type FROM watchlist_items WHERE symbol = 'BTC-EUR'").fetchone()[0] == "CRYPTO"

    calls.clear()
    screens.refresh(zones={"crypto", "asia"})
    assert calls == [["7203.T", "BTC-EUR"]]


def test_crypto_fractional_buy_with_tiny_price(client, monkeypatch):
    monkeypatch.setattr(paper, "fx_rate", lambda ccy: 1.0)
    wl = client.post("/watchlists", json={"name": "Crypto"}, headers=H).json()["watchlist"]["id"]
    with get_conn() as conn:
        for sym, price in (("BTC-EUR", 68900.0), ("SHIB-EUR", 0.000004)):
            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, product_type, last_price, last_score, "
                "last_signal, buy_price, buy_kind, sell_price, stop_price, currency) VALUES (?,?,?,?, 'CRYPTO', ?, 8, 'ACHAT', ?, '≈', ?, ?, 'EUR')",
                (wl, sym, f"yf:{sym}", sym, price, price, price * 1.2, price * 0.9))
    pid = client.post("/portfolios", json={"watchlist_id": wl}, headers=H).json()["portfolio"]["id"]
    with get_conn() as conn:
        pos = {r["symbol"]: dict(r) for r in conn.execute("SELECT * FROM portfolio_positions WHERE portfolio_id = ?", (pid,))}
    assert 0 < pos["BTC-EUR"]["qty"] < 1 and pos["BTC-EUR"]["qty"] * 68900 == pytest.approx(499, abs=1.5)
    assert pos["SHIB-EUR"]["qty"] > 1e8 and pos["SHIB-EUR"]["stop"] == pytest.approx(0.0000036) and pos["SHIB-EUR"]["target"] > 0


def test_tiny_price_crypto_technical_summary():
    """SHIB ≈ 0,000004 € : graphique, volatilité et cibles ne tombent pas à zéro."""
    from app.services import technical
    from tests.test_screens import fake_df

    df = fake_df() * 4e-8  # cours ≈ 0,000004
    t = technical.quick_summary(df)
    assert t["price"] > 0 and all(r["close"] > 0 for r in t["chart"])
    v = screens.evaluate(df)
    assert v["buy_price"] > 0 and v["sell_price"] > v["stop_price"] > 0
