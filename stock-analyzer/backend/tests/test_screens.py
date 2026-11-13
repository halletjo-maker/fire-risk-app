"""Liste « IPO 10 ans » : sélection Nasdaq, création, mise à jour quotidienne groupée."""
import numpy as np
import pandas as pd

from app.services import screens

H = {"X-User-Email": "a@exemple.be"}


def row(sym, name, ipo, cap):
    return {"symbol": sym, "name": name, "ipoyear": str(ipo) if ipo else "", "marketCap": str(cap),
            "sector": "Technology", "country": "United States"}


ROWS = [
    row("ARM", "Arm Holdings plc American Depositary Shares", 2023, 243e9),
    row("CRWD", "CrowdStrike Holdings Inc. Class A Common Stock", 2019, 267e9),
    row("TBB", "AT&T Inc. 5.350% Global Notes due 2066", 2017, 126e9),
    row("XPRF", "Foo Corp 6.25% Series A Cumulative Preferred Stock", 2020, 5e9),
    row("SPCW", "Some SPAC Warrants", 2021, 1e9),
    row("OLD", "Old Corp Common Stock", 2010, 900e9),
    row("NOYR", "No Year Inc. Common Stock", None, 50e9),
    row("SNOW", "Snowflake Inc. Class A Common Stock", 2020, 70e9),
    row("SNOWB", "Snowflake Inc. Class B Common Stock", 2020, 3e9),   # même société : on garde la plus grosse ligne
    row("BRK/X", "Brkx Holdings Class B Common Stock", 2022, 10e9),
    row("UNTY", "Unity Software Inc. Common Stock", 2020, 17e9),      # « Unity » ≠ « Units »
    row("ZERO", "Zero Cap Inc. Common Stock", 2024, 0),
]


def test_select_recent_ipos():
    out = screens.select_recent_ipos(ROWS, year=2026, size=10)
    assert [m["symbol"] for m in out] == ["CRWD", "ARM", "SNOW", "UNTY", "BRK-X"]
    assert out[0]["name"] == "CrowdStrike Holdings Inc." and out[0]["ipo_year"] == 2019
    assert out[1]["name"] == "Arm Holdings plc"
    assert [m["symbol"] for m in screens.select_recent_ipos(ROWS, year=2026, size=2)] == ["CRWD", "ARM"]


def fake_df(trend=0.3, n=260, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(trend, 1, n))
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close,
                         "volume": rng.integers(1e5, 2e5, n)}, index=idx)


def test_create_and_daily_refresh(client, monkeypatch):
    from app.services import watchlist as wl_service
    from app.services.sources import yahoo

    monkeypatch.setattr(screens, "fetch_universe", lambda: ROWS)
    calls = []

    def many(symbols, period="1y"):
        calls.append(list(symbols))
        return {s: fake_df(0.4 if s != "ARM" else -0.4, seed=len(s)) for s in symbols if s != "UNTY"}

    monkeypatch.setattr(yahoo, "history_many", many)
    monkeypatch.setattr(screens, "BATCH", 2)
    monkeypatch.setattr(screens.time, "sleep", lambda s: None)

    r = client.post("/watchlists/presets/ipo10", headers=H)
    assert r.status_code == 201
    w = r.json()["watchlist"]
    assert w["kind"] == "screen:ipo10" and w["item_count"] == 5 and w["name"] == "IPO 10 ans"
    assert client.post("/watchlists/presets/ipo10", headers=H).status_code == 409
    assert client.post("/watchlists/presets/inconnue", headers=H).status_code == 404

    items = client.get(f"/watchlists/{w['id']}/items", headers=H).json()["items"]
    assert [(i["symbol"], i["ipo_year"]) for i in items][:2] == [("CRWD", 2019), ("ARM", 2023)]
    assert [len(c) for c in calls] == [2, 2, 1]  # téléchargement par lots
    by = {i["symbol"]: i for i in items}
    assert by["CRWD"]["last_score"] is not None and by["CRWD"]["last_signal"] in ("ACHAT", "NEUTRE", "VENTE")
    assert by["CRWD"]["buy_price"] is not None and by["CRWD"]["sell_price"] > 0
    assert by["UNTY"]["last_score"] is None  # historique introuvable : la ligne reste en attente

    # Le rafraîchissement « 15 minutes » ignore les listes larges
    seen = []
    monkeypatch.setattr(wl_service, "refresh_product", lambda pid: seen.append(pid))
    wl_service.refresh_all()
    assert seen == []

    # Bouton ↻ : mise à jour légère de la liste
    calls.clear()
    assert client.post(f"/watchlists/{w['id']}/refresh", headers=H).status_code == 202
    assert sum(len(c) for c in calls) == 5

    # Duplication : la copie reste une liste large
    dup = client.post(f"/watchlists/{w['id']}/duplicate", headers=H).json()["watchlist"]
    assert dup["kind"] == "screen:ipo10" and dup["item_count"] == 5


def test_weekly_resync_updates_membership(client, monkeypatch):
    from app.database import get_conn
    from app.services.sources import yahoo

    monkeypatch.setattr(screens, "fetch_universe", lambda: ROWS)
    monkeypatch.setattr(yahoo, "history_many", lambda symbols, period="1y": {})
    w = client.post("/watchlists/presets/ipo10", headers=H).json()["watchlist"]
    # Composition récente : pas de nouvelle lecture Nasdaq
    monkeypatch.setattr(screens, "fetch_universe", lambda: [ROWS[1]])
    screens.refresh(resync=True)
    assert len(client.get(f"/watchlists/{w['id']}/items", headers=H).json()["items"]) == 5
    with get_conn() as conn:
        conn.execute("UPDATE watchlists SET screen_synced_at = datetime('now', '-8 days')")
    screens.refresh(resync=True)
    assert [i["symbol"] for i in client.get(f"/watchlists/{w['id']}/items", headers=H).json()["items"]] == ["CRWD"]


def test_nasdaq_unavailable(client, monkeypatch):
    def boom():
        raise RuntimeError("Liste Nasdaq indisponible")
    monkeypatch.setattr(screens, "fetch_universe", boom)
    assert client.post("/watchlists/presets/ipo10", headers=H).status_code == 503


def test_second_preset_ipo5(client, monkeypatch):
    """Liste « IPO 5 ans » : 100 sociétés, en plus de la liste sur 10 ans."""
    from app.services.sources import yahoo

    monkeypatch.setattr(screens, "fetch_universe", lambda: ROWS)
    monkeypatch.setattr(yahoo, "history_many", lambda symbols, period="1y": {})
    a = client.post("/watchlists/presets/ipo10", headers=H).json()["watchlist"]
    b = client.post("/watchlists/presets/ipo5", headers=H)
    assert b.status_code == 201
    b = b.json()["watchlist"]
    assert (b["kind"], b["name"]) == ("screen:ipo5", "IPO 5 ans") and a["id"] != b["id"]
    year = __import__("datetime").datetime.now().year
    syms = [i["symbol"] for i in client.get(f"/watchlists/{b['id']}/items", headers=H).json()["items"]]
    assert syms == [m["symbol"] for m in screens.select_recent_ipos(ROWS, year=year, years=5, size=100)]
    assert all(i["ipo_year"] >= year - 5 for i in client.get(f"/watchlists/{b['id']}/items", headers=H).json()["items"])
    assert screens.PRESETS["ipo5"]["size"] == 100
