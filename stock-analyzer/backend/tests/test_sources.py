"""Lecture des pages des sources (échantillons réels enregistrés, sans internet)."""
from pathlib import Path

import pytest

from app.services.sources import boursorama, google_finance
from app.services.sources.parsing import fr_number

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("7 970,00", 7970.0),
        ("7 970,00 PTS", 7970.0),
        ("-0,30 %", -0.30),
        ("+1,35%", 1.35),
        ("537.58 EUR", 537.58),
        ("1.234,56", 1234.56),
        ("59,61 M", 59_610_000),
        ("112,86 Md", 112_860_000_000),
        ("2 522 MEUR", 2_522_000_000),
        ("−0,75", -0.75),
        ("", None),
        ("abc", None),
    ],
)
def test_fr_number(text, expected):
    assert fr_number(text) == pytest.approx(expected) if expected is not None else fr_number(text) is None


def test_boursorama_turbo_page():
    data = boursorama.parse_quote_page((FIX / "boursorama_turbo.html").read_text(), "/bourse/produits-de-bourse/cours/3rPDE000FG0GUF0")
    assert data["type"] == "TURBO"
    assert data["isin"] == "DE000FG0GUF0"
    assert data["price"] == pytest.approx(4.495)
    assert data["change_pct"] == pytest.approx(1.35)
    d = data["derivative"]
    assert d["issuer"] == "SOCIETE GENERALE"
    assert d["direction"] == "PUT"
    assert d["underlying"] == "LVMH"
    assert d["barrier"] == pytest.approx(537.58)
    assert d["leverage"] == pytest.approx(2.13)
    # Put : la barrière est au-dessus du cours du sous-jacent (383,85)
    assert d["barrier_distance_pct"] == pytest.approx((537.58 - 383.85) / 383.85 * 100, abs=0.01)


def test_boursorama_action_page():
    data = boursorama.parse_quote_page((FIX / "boursorama_action.html").read_text(), "/cours/FF11-SOLB/")
    assert data["type"] == "ACTION"
    assert data["name"] == "SOLVAY"
    assert data["isin"] == "BE0003470755"
    assert data["symbol"] == "SOLB"
    assert data["price"] == pytest.approx(23.82)
    assert data["volume"] == 271866
    assert data["derivative"] is None


def test_boursorama_search(monkeypatch):
    html = (FIX / "boursorama_search.html").read_text()
    monkeypatch.setattr(boursorama, "fetch_text", lambda *a, **k: html)
    results = boursorama.search("turbo lvmh")
    assert results[0]["type"] == "ACTION" and results[0]["symbol"] == "MC"
    assert results[0]["exchange"] == "Euronext Paris"
    turbo = next(r for r in results if r["isin"] == "DE000BD30139")
    assert turbo["type"] == "TURBO" and turbo["exchange"] is None
    assert turbo["id"] == "bo:/bourse/produits-de-bourse/cours/2rPDE000BD30139"


@pytest.mark.parametrize(
    "name, nature, expected",
    [
        ("CAC40/SGE P-WT OPEN", None, "TURBO"),
        ("MC/VONF PW OPEN", None, "TURBO"),
        ("LVMH 458.6TCIOPENV", None, "TURBO"),
        ("MC/SGE WT 07.26", None, "WARRANT"),
        ("MC/SGE OPEN", None, "AUTRE"),
        ("CAC4010430BON0327S", None, "AUTRE"),
        ("X", "Turbos Illimités Best Put", "TURBO"),
        ("X", "Warrants Call", "WARRANT"),
        ("X", "Bonus", "AUTRE"),
    ],
)
def test_derivative_type(name, nature, expected):
    assert boursorama.derivative_type(name, nature) == expected


def test_google_page_ignores_top_banner():
    data = google_finance.parse_quote_page((FIX / "google_now.html").read_text(), anchor="NOW:NYSE")
    assert data["name"] == "ServiceNow"
    assert data["price"] == pytest.approx(108.80)
    assert data["change_pct"] == pytest.approx(-27.22)
    assert data["currency"] == "USD"


def test_google_codes():
    assert google_finance.google_code("SOLB.BR") == ["SOLB:EBR"]
    assert google_finance.google_code("NOW", "NYQ") == ["NOW:NYSE"]
    assert google_finance.google_code("BTC-EUR") == ["BTC-EUR"]
    assert google_finance.google_code("^FCHI") == ["PX1:INDEXEURO"]


def test_fetch_text_never_raises(monkeypatch):
    """Même une erreur hors « requests » (ex. certificat introuvable) renvoie None."""
    from app.services.sources import http

    def boom(*a, **k):
        raise OSError("Could not find a suitable TLS CA certificate bundle")

    monkeypatch.setattr(http._session, "get", boom)
    monkeypatch.setenv("SCRAPING_DELAY_SECONDS", "0")
    assert http.fetch_text("https://exemple.invalid/x") is None
