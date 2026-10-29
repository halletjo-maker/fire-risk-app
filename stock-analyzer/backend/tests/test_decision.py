"""Module 6 — score global et décision ACHAT / VENTE."""
import pytest

from app.services import decision as D


def comp(score, **extra):
    return {"score": score, **extra}


def test_weights_and_thresholds():
    d = D.compute(comp(8), comp(8), comp(8))
    assert d["score"] == 8.0 and d["buy"]["level"] == "FAVORABLE" and d["signal"] == "ACHAT"
    assert d["buy"]["label"] == "CONDITIONS FAVORABLES À L'ACHAT"
    assert d["sell"]["score"] == 2.0 and d["sell"]["label"] == "CONDITIONS DÉFAVORABLES À LA VENTE"
    # 0,35 × 10 + 0,45 × 5 + 0,20 × 0 = 5,75
    d = D.compute(comp(10), comp(5), comp(0))
    assert d["score"] == pytest.approx(5.8, abs=0.06)
    assert d["buy"]["level"] == "PRUDENCE" and d["buy"]["label"] == "PRUDENCE"
    assert [c["weight"] for c in d["components"]] == [0.35, 0.45, 0.2]


@pytest.mark.parametrize("score, lvl", [(7.5, "FAVORABLE"), (7.4, "PRUDENCE"), (5.0, "PRUDENCE"), (4.9, "DEFAVORABLE")])
def test_level_boundaries(score, lvl):
    assert D.level(score) == lvl


def test_strong_warning_when_unfavorable():
    d = D.compute(comp(2), comp(2), comp(2))  # global 2 → vente 8
    assert d["buy"]["level"] == "DEFAVORABLE" and d["buy"]["warning"].startswith("⚠️ AVERTISSEMENT")
    assert d["signal"] == "VENTE"
    assert d["sell"]["level"] == "FAVORABLE"


def test_missing_component_reweighted():
    d = D.compute({"score": None}, comp(6), comp(8))
    assert d["missing"] == ["Fondamental"]
    weights = {c["key"]: c["weight"] for c in d["components"]}
    assert weights["technical"] == pytest.approx(0.45 / 0.65, abs=0.001)
    assert d["score"] == pytest.approx(6 * 0.45 / 0.65 + 8 * 0.20 / 0.65, abs=0.06)
    assert any("Non applicable" in n for n in d["notes"])


def test_divergence_and_mm100_phrases():
    tech = comp(4.3, mm100={"above": False, "cross": {"direction": "BAISSIER", "sessions_ago": 0}})
    d = D.compute(comp(8), tech, comp(3.6))
    assert "cassure récente de la MM100 à la baisse" in d["buy"]["cons"]
    assert "fondamentaux solides" in d["buy"]["pros"]
    assert any("divergent" in n for n in d["notes"])
    # l'onglet vente lit les mêmes arguments à l'envers
    assert d["sell"]["pros"] == d["buy"]["cons"]


def test_derivative_wording_and_earnings_note():
    f = {"score": 8.6, "criteria": [{"key": "barrier"}, {"key": "leverage"}]}
    s = comp(6.5, events=[{"type": "Earnings Date", "days": 1}])
    d = D.compute(f, comp(6.1, inverse=True), s)
    assert any("produit peu risqué" in p for p in d["buy"]["pros"])
    assert any("favorable au put" in p for p in d["buy"]["pros"])
    assert any("48 h" in n for n in d["notes"])


def test_nothing_available():
    assert D.compute(None, None, None)["available"] is False
