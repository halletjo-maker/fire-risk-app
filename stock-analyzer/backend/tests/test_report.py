"""Module 7 — rapport justificatif (sans internet)."""
import pytest

from app.services import report as R
from app.services.decision import compute


def chart(n=40, close=100.0, spread=2.0):
    return [{"t": f"2026-01-{i:02d}", "open": close, "high": close + spread / 2, "low": close - spread / 2,
             "close": close} for i in range(1, n + 1)]


def full(kind="ACTION", support=95.0, resistance=110.0, price=100.0, derivative=None, mm=None, f_crit=None):
    tech = {"applicable": True, "score": 6.0, "inverse": bool(derivative and derivative.get("direction") == "PUT"),
            "analysed": {"name": "LVMH Moët Hennessy - Louis Vuitton, SE", "symbol": "MC.PA", "id": "yf:MC.PA"},
            "mm100": mm or {"status": "AU-DESSUS", "above": True, "distance_pct": 4.0, "value": 96.0,
                            "cross": None, "slope_pct": 1.0},
            "levels": {"support": support, "resistance": resistance}, "chart": chart(),
            "criteria": [{"key": "mm100", "label": "★ Position vs MM100", "display": "x", "score": 8.5, "comment": "c"},
                         {"key": "macd", "label": "MACD", "display": "x", "score": 3.0, "comment": "c"}],
            "currency": "EUR", "sources": [{"name": "Yahoo Finance", "ok": True}]}
    fund = {"applicable": True, "score": 8.0, "criteria": f_crit or [
        {"key": "per", "label": "Valorisation (PER)", "display": "12", "score": 9.0, "comment": "c"}],
        "info": [], "sources": [{"name": "Boursorama (consensus)", "ok": True}]}
    senti = {"applicable": True, "score": 5.0, "verdict": "Neutre", "items": [{}],
             "counts": {"positif": 1, "neutre": 0, "negatif": 0}, "events": [], "sources": []}
    return {"product": {"id": "yf:X", "symbol": "X", "name": "Exemple SA", "type": kind, "currency": "EUR"},
            "quote": {"price": price}, "derivative": derivative, "fundamentals": fund, "technical": tech,
            "sentiment": senti, "decision": compute(fund, tech, senti)}


def test_summary_has_three_sentences():
    s = R.executive_summary(full())
    assert len(s) == 3
    assert "score global" in s[0] and "MM100" not in s[0]
    assert "moyenne mobile 100 jours" in s[1] and "fondamentaux sont solides" in s[1]


def test_strengths_and_weaknesses():
    strengths, weaknesses = R.strengths_weaknesses(full())
    assert [x["label"] for x in strengths] == ["Valorisation (PER)", "Position vs MM100"]
    assert [x["label"] for x in weaknesses] == ["MACD"]


def test_stop_losses_support_recommended():
    sl = R.stop_losses(full(support=95.0))
    keys = [lv["key"] for lv in sl["levels"]]
    assert keys == ["support", "pct5", "pct8", "pct12"]
    support = sl["levels"][0]
    assert support["price"] == pytest.approx(95 * 0.99)          # 1 % sous le support
    assert support["distance_pct"] == pytest.approx(-5.9, abs=0.05)
    assert sl["recommended"] == "support" and support["recommended"]
    assert [lv["price"] for lv in sl["levels"][1:]] == [95.0, 92.0, 88.0]


def test_stop_losses_far_support_uses_volatility():
    sl = R.stop_losses(full(support=70.0))  # support à −30 % : trop loin
    assert sl["recommended"] in ("pct5", "pct8", "pct12")
    assert sl["atr_pct"] == pytest.approx(2.0, abs=0.01)         # (haut − bas) / cours = 2 %
    assert sl["recommended"] == "pct5"                            # 2 × ATR = 4 % → −5 %
    assert any("éloigné" in n for n in sl["notes"])


def test_put_turbo_stop_on_underlying_resistance():
    d = {"direction": "PUT", "strike": 562.9, "parity": 40, "leverage": 2.1, "barrier_distance_pct": 40}
    f = full(kind="TURBO", price=4.5, support=376.0, resistance=399.5, derivative=d,
             f_crit=[{"key": "barrier", "label": "Distance à la barrière", "display": "40 %", "score": 9, "comment": "c"}])
    sl = R.stop_losses(f)
    stop = sl["levels"][0]
    trigger = 399.5 * 1.01
    assert stop["label"] == "Résistance du sous-jacent"
    assert stop["price"] == pytest.approx((562.9 - trigger) / 40, abs=1e-3)
    assert "LVMH dépasse" in stop["detail"]
    assert any("barrière" in n for n in sl["notes"])
    assert "côté produit" in R.executive_summary(f)[1]


def test_mm100_plain_language():
    txt = R.mm100_text(full(mm={"status": "CROISEMENT", "above": False, "distance_pct": -2.0, "value": 102.0,
                                "cross": {"direction": "BAISSIER", "sessions_ago": 0}, "slope_pct": -0.5}))
    assert "passé dessous aujourd'hui" in txt and "orientée à la baisse" in txt


def test_alternatives_roles(monkeypatch):
    monkeypatch.setattr(R, "_peers", lambda s: ["P1", "P2"])
    snaps = {s: {"id": f"yf:{s}", "symbol": s, "name": s, "type": "ACTION", "currency": "EUR", "price": 1,
                 "change_pct": 0, "technical_score": score, "mm100_status": "AU-DESSUS", "mm100_distance_pct": 2}
             for s, score in [("P1", 4), ("P2", 7), ("XDWT.DE", 6), ("AD.AS", 5), ("SAN.PA", 8), ("IBE.MC", 3),
                              ("UNA.AS", 6), ("ELI.BR", 2)]}
    monkeypatch.setattr(R, "_snapshot", lambda s: snaps.get(s))
    f = full()
    f["fundamentals"]["info"] = [{"label": "Secteur", "display": "Technology · Software"}]
    alts = R.alternatives(f)
    assert [a["role"] for a in alts] == ["same", "sector", "defensive"]
    assert alts[0]["symbol"] == "P2"           # meilleur score technique des pairs
    assert alts[1]["symbol"] == "XDWT.DE"      # ETF sectoriel technologie
    assert alts[2]["symbol"] == "SAN.PA"       # meilleure valeur défensive
    assert "au-dessus de sa MM100" in alts[0]["reason"]


def test_turbo_volatility_scaled_by_leverage():
    d = {"direction": "CALL", "strike": 50.0, "parity": 10, "leverage": 5.0}
    f = full(kind="TURBO", price=5.0, support=None, derivative=d,
             f_crit=[{"key": "leverage", "label": "Effet de levier", "display": "× 5", "score": 8, "comment": "c"}])
    sl = R.stop_losses(f)
    assert sl["atr_pct"] == pytest.approx(10.0, abs=0.01)   # 2 % du sous-jacent × levier 5
    assert sl["recommended"] == "pct12"
    assert any("Très volatil" in n for n in sl["notes"])
