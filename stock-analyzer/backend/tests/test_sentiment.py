"""Module 5 — sentiment des titres et score (sans internet)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import sentiment as S
from app.services.sources import news, yahoo


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    from app.database import init_db

    init_db()


@pytest.mark.parametrize("title, label", [
    ("ServiceNow shares plunge 25% after earnings revive AI disruption fears", "negatif"),
    ("Citigroup maintains ServiceNow at Buy, lowers price target to $157 from $170", "negatif"),
    ("Solvay cuts 2026 guidance as Solvay stock trades at EUR 23.42", "negatif"),
    ("ServiceNow se fait étriller suite à ses prévisions", "negatif"),
    ("Les valeurs du secteur informatique reculent, ServiceNow n'ayant pas répondu aux attentes", "negatif"),
    ("LVMH s'effondre en Bourse", "negatif"),
    ("Renault et Airbus propulsent le Cac 40 près des 8.000 points", "positif"),
    ("Nvidia bondit après des résultats supérieurs aux attentes", "positif"),
    ("Apple beats estimates and raises its guidance", "positif"),
    ("CAC 40 : la Bourse de Paris finit dans le vert", "positif"),
    ("Journée à l'équilibre pour Solvay", "neutre"),
    ("Bitcoin, Ethereum et XRP évoluent latéralement", "neutre"),
])
def test_title_sentiment(title, label):
    assert S.score_title(title)["label"] == label


def test_negation_flips():
    assert S.score_title("Les ventes ne sont pas en hausse")["score"] < 0
    assert S.score_title("Shares did not fall")["score"] > 0


@pytest.mark.parametrize("name, expected", [
    ("ServiceNow, Inc.", "ServiceNow"),
    ("Solvay SA", "Solvay"),
    ("LVMH Moët Hennessy - Louis Vuitton, Société Européenne", "LVMH"),
    ("CAC 40", "CAC 40"),
    ("Apple Inc.", "Apple"),
])
def test_clean_name(name, expected):
    assert S.clean_name(name) == expected


def test_search_term_by_type():
    assert S.search_term({"type": "TURBO"}, {"underlying": "LVMH"}) == "LVMH"
    assert S.search_term({"type": "CRYPTO", "name": "Bitcoin EUR"}) == "Bitcoin"
    assert S.search_term({"type": "ETF", "name": "iShares X"}, None, {"index": "MSCI World"}) == "MSCI World"


def _item(title, hours, lang="fr"):
    return {"title": title, "url": "u", "source": "s", "lang": lang, "via": news.GOOGLE,
            "published": datetime.now(timezone.utc) - timedelta(hours=hours)}


def test_analyze_filters_and_scores(monkeypatch):
    fr = [
        _item("Solvay plonge après un avertissement", 2),
        _item("Solvay plonge après un avertissement", 3),          # doublon
        _item("SOLVAY Cours Action SOLB, Cotation Bourse Euronext Bruxelles", 4),  # page de cotation
        _item("Solvay recule encore", 10),
        _item("Solvay chute de 5 %", 90),                           # plus de 72 h
        _item("Résultats de la Bourse de Bruxelles", 1),            # ne cite pas Solvay
    ]
    en = [
        _item("John Smith Obituary - Solvay, NY", 1, "en"),          # homonyme sans contexte boursier
        _item("JPMorgan cuts target for Solvay stock", 5, "en"),
    ]
    monkeypatch.setattr(news, "google_news", lambda q, lang="fr", days=3: fr if lang == "fr" else en)
    monkeypatch.setattr(news, "newsapi", lambda *a, **k: None)
    monkeypatch.setattr(yahoo, "calendar", lambda s: {"Earnings Date": [date.today() + timedelta(days=1)]})
    r = S.analyze({"id": "yf:SOLB.BR", "type": "ACTION", "name": "Solvay SA", "currency": "EUR"},
                  events_symbol="SOLB.BR")
    titles = [i["title"] for i in r["items"]]
    assert titles == ["Solvay plonge après un avertissement", "JPMorgan cuts target for Solvay stock", "Solvay recule encore"]
    assert r["counts"]["negatif"] == 3
    assert r["score"] < 4 and r["verdict"] == "Négatif"
    assert any("Seulement 3" in n for n in r["notes"])           # peu d'articles → prudence
    assert r["events"][0]["label"] == "Résultats trimestriels" and r["events"][0]["days"] == 1
    assert any("Résultats trimestriels dans 1 jour" in n for n in r["notes"])


def test_no_news_is_neutral(monkeypatch):
    monkeypatch.setattr(news, "google_news", lambda *a, **k: [])
    monkeypatch.setattr(news, "newsapi", lambda *a, **k: None)
    r = S.analyze({"id": "yf:XYZ", "type": "ACTION", "name": "Xyz Corp", "currency": "USD"})
    assert r["score"] == 5.0 and r["items"] == []


def test_put_inverts_sentiment(monkeypatch):
    items = [_item("LVMH plonge", 1), _item("LVMH chute encore", 2), _item("LVMH recule", 3),
             _item("LVMH dévisse", 4), _item("LVMH au plus bas", 5)]
    monkeypatch.setattr(news, "google_news", lambda q, lang="fr", days=3: items if lang == "fr" else [])
    monkeypatch.setattr(news, "newsapi", lambda *a, **k: None)
    turbo = {"id": "bo:/t", "type": "TURBO", "name": "LVMH/SGE P-WT OPEN", "currency": "EUR"}
    put = S.analyze(turbo, {"underlying": "LVMH", "direction": "PUT"})
    assert put["inverse"] and put["underlying_score"] < 4
    assert put["score"] == pytest.approx(10 - put["underlying_score"], abs=0.11)
    assert put["verdict"] == "Positif"
    call = S.analyze({**turbo, "id": "bo:/c"}, {"underlying": "LVMH", "direction": "CALL"})
    assert not call["inverse"] and call["verdict"] == "Négatif"
