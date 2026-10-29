"""Module 4 — analyse technique sur des courbes simulées (sans internet)."""
import numpy as np
import pandas as pd
import pytest

from app.services import technical as T


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    from app.database import init_db

    init_db()


def make_df(closes, volume=1000.0):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range(end="2026-10-29", periods=len(closes))
    return pd.DataFrame({"open": closes, "high": closes * 1.01, "low": closes * 0.99,
                         "close": closes, "volume": volume}, index=idx)


def wave(n, start, end, amp=0.02, period=15):
    base = np.linspace(start, end, n)
    return base * (1 + amp * np.sin(np.arange(n) * 2 * np.pi / period))


def test_uptrend_above_mm100():
    d = T.indicators(make_df(wave(300, 50, 100)))
    mm = T.mm100_status(d)
    assert mm["status"] == "AU-DESSUS" and mm["above"] and mm["distance_pct"] > 0
    assert mm["slope_pct"] > 0
    crit = {c["key"]: c for c in T.score_criteria(d, mm)}
    assert crit["mm100"]["score"] >= 8
    assert crit["mm100"]["weight"] == 35  # critère principal
    assert crit["trend"]["display"] == "Haussier"


def test_downtrend_below_mm100():
    d = T.indicators(make_df(wave(300, 100, 50)))
    mm = T.mm100_status(d)
    assert mm["status"] == "EN-DESSOUS" and mm["distance_pct"] < 0
    crit = {c["key"]: c for c in T.score_criteria(d, mm)}
    assert crit["mm100"]["score"] <= 3
    assert crit["trend"]["display"] == "Baissier"


def test_recent_cross_detected():
    closes = list(np.full(250, 100.0)) + [100 + i for i in range(1, 8)]  # remonte fortement
    closes[240:250] = [95.0] * 10  # était sous la MM100 juste avant
    closes[250:] = [110.0] * 7
    d = T.indicators(make_df(closes))
    mm = T.mm100_status(d)
    # cassure vers le haut il y a 6 séances → hors fenêtre de 5 → AU-DESSUS
    assert mm["status"] == "AU-DESSUS"
    closes[-2:] = [110.0, 110.0]
    closes[-3] = 95.0  # sous la MM100 il y a 2 séances
    d = T.indicators(make_df(closes))
    mm = T.mm100_status(d)
    assert mm["status"] == "CROISEMENT" and mm["cross"]["direction"] == "HAUSSIER"
    assert mm["cross"]["sessions_ago"] == 1
    crit = {c["key"]: c for c in T.score_criteria(d, mm)}
    assert "⚡" in crit["mm100"]["display"]


def test_short_history_has_no_mm100():
    d = T.indicators(make_df(wave(60, 50, 60)))
    assert T.mm100_status(d) is None
    crit = {c["key"]: c for c in T.score_criteria(d, None)}
    assert crit["mm100"]["score"] is None


def test_supports_resistances():
    d = make_df(wave(200, 100, 100, amp=0.05, period=20))
    price = float(d["close"].iloc[-1])
    lv = T.supports_resistances(d, price)
    assert lv["support"] < price < lv["resistance"]


def test_put_turbo_inverts_score(monkeypatch):
    from app.services import market

    monkeypatch.setattr(market, "search", lambda q: {"candidates": [
        {"id": "yf:MC.PA", "symbol": "MC.PA", "name": "LVMH", "type": "ACTION", "exchange_code": "PAR"}]})
    monkeypatch.setattr(T, "load_history", lambda p: (make_df(wave(300, 100, 50)), [{"name": "Yahoo Finance", "ok": True}]))
    turbo = {"id": "bo:/x", "type": "TURBO", "name": "LVMH PUT"}
    put = T.analyze(turbo, {"price": 1}, {"underlying": "LVMH", "direction": "PUT"})
    assert put["inverse"] and put["analysed"]["symbol"] == "MC.PA"
    assert put["score"] == pytest.approx(10 - put["underlying_score"], abs=0.11)
    assert put["score"] >= 6  # sous-jacent baissier = favorable à un put

    call = T.analyze({**turbo, "id": "bo:/y"}, {"price": 1}, {"underlying": "LVMH", "direction": "CALL"})
    assert not call["inverse"] and call["score"] <= 4


def test_chart_payload():
    d = T.indicators(make_df(wave(300, 50, 100)))
    series = T.chart_series(d)
    assert len(series) == T.CHART_BARS
    last = series[-1]
    assert {"t", "open", "high", "low", "close", "m50", "m100", "m200", "rsi", "macd", "sig", "hist"} <= set(last)
    assert last["m100"] is not None
