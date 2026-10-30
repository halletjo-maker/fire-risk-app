"""Module 9 — alertes mail (sans internet ni vrai serveur SMTP)."""
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes, policy

import pytest

from app.services import alerts as A
from app.services.decision import compute

H = {"X-User-Email": "a@exemple.be"}


def full(score=8.2, above=True, cross=None, senti=None, events=(), titles=("ServiceNow plonge",)):
    senti = score if senti is None else senti  # score global = score quand les 3 analyses sont égales
    f = {"score": score, "criteria": []}
    t = {"applicable": True, "score": score, "mm100": {"status": "CROISEMENT" if cross else ("AU-DESSUS" if above else "EN-DESSOUS"),
                                                      "above": above, "distance_pct": 3.0 if above else -3.0, "value": 120.0,
                                                      "cross": cross, "slope_pct": 1.0}}
    s = {"applicable": True, "score": senti, "inverse": False, "events": list(events),
         "items": [{"title": x, "sentiment_score": -0.8} for x in titles]}
    return {"product": {"id": "yf:NOW", "symbol": "NOW", "name": "ServiceNow", "currency": "USD"},
            "quote": {"price": 109.67, "change_pct": -1.2}, "fundamentals": f, "technical": t, "sentiment": s,
            "decision": compute(f, t, s)}


# ---------------------------------------------------------------- conditions
def test_signal_fort_fires_on_transition_only():
    fire, state, _ = A.evaluate("SIGNAL_FORT", None, full(score=8.2))
    assert fire and state == "ON"
    fire, state, _ = A.evaluate("SIGNAL_FORT", "ON", full(score=8.4))
    assert not fire and state == "ON"                       # reste vrai : pas de nouveau mail
    fire, state, _ = A.evaluate("SIGNAL_FORT", "ON", full(score=6.0))
    assert not fire and state == "OFF"
    assert A.evaluate("SIGNAL_FORT", "OFF", full(score=7.5))[0]


def test_alerte_baisse():
    assert A.evaluate("ALERTE_BAISSE", "OFF", full(score=4.9))[0]
    assert not A.evaluate("ALERTE_BAISSE", "OFF", full(score=5.0))[0]


def test_mm100_cross():
    # première vérification : seul un croisement récent déclenche
    assert not A.evaluate("MM100_CROISEMENT", None, full(above=True))[0]
    fire, state, ctx = A.evaluate("MM100_CROISEMENT", None, full(above=False, cross={"direction": "BAISSIER", "sessions_ago": 0}))
    assert fire and state == "BELOW" and ctx["direction"] == "BAISSIER"
    fire, state, ctx = A.evaluate("MM100_CROISEMENT", "BELOW", full(above=True))
    assert fire and ctx["direction"] == "HAUSSIER"
    assert not A.evaluate("MM100_CROISEMENT", "ABOVE", full(above=True))[0]


def test_negative_news_and_earnings():
    fire, _, ctx = A.evaluate("ACTUALITE_IMPORTANTE", "OFF", full(senti=2.4))
    assert fire and ctx["title"] == "ServiceNow plonge"
    assert not A.evaluate("ACTUALITE_IMPORTANTE", "OFF", full(senti=3.5))[0]
    soon = (date.today() + timedelta(days=1)).isoformat()
    ev = [{"type": "Earnings Date", "days": 1, "date": soon}]
    fire, state, _ = A.evaluate("RESULTATS_A_VENIR", None, full(events=ev))
    assert fire and state == soon
    assert not A.evaluate("RESULTATS_A_VENIR", soon, full(events=ev))[0]  # une seule fois par date


def test_frequency_window():
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    assert A.frequency_allows("immediate", two_hours_ago, now)
    assert not A.frequency_allows("daily", two_hours_ago, now)
    assert A.frequency_allows("daily", (now - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S"), now)
    assert not A.frequency_allows("weekly", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), now)


def test_mail_format():
    subject, text, html = A.compose("SIGNAL_FORT", {"score": 8.2}, full(score=8.2), "tok123", "Tech US")
    assert subject == "[SIGNAL ACHAT ✅] ServiceNow (NOW) — Score 8,2/10"
    body = text.split("\n\n")[0].split("\n")
    assert len(body) == 5                                      # résumé en 5 lignes max
    assert "/?analyse=yf:NOW" in text and "/api/alerts/unsubscribe/tok123" in text
    assert "Se désinscrire" in html and "MiFID II" in html


# ---------------------------------------------------------------- bout en bout
@pytest.fixture()
def setup(client, monkeypatch):
    """Utilisateur + watchlist + ServiceNow suivi, analyses simulées."""
    from app.database import get_conn
    from app.services import analysis

    state = {"full": full(score=8.2)}
    monkeypatch.setattr(analysis, "run", lambda pid, isin=None: state["full"])
    client.post("/users/login", json={"email": "a@exemple.be"})
    wl = client.post("/watchlists", json={"name": "Tech US"}, headers=H).json()["watchlist"]["id"]
    with get_conn() as conn:
        item = conn.execute("INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name) "
                            "VALUES (?, 'NOW', 'yf:NOW', 'ServiceNow')", (wl,)).lastrowid
    return client, item, state


def test_configure_alerts_api(setup):
    client, item, _ = setup
    r = client.get(f"/alerts/item/{item}", headers=H).json()
    assert [a["type"] for a in r["alerts"]] == list(A.TYPES) and not any(a["enabled"] for a in r["alerts"])
    r = client.put(f"/alerts/item/{item}", headers=H, json={"alerts": [
        {"type": "SIGNAL_FORT", "enabled": True, "frequency": "daily"},
        {"type": "MM100_CROISEMENT", "enabled": True, "frequency": "immediate"}]}).json()
    enabled = {a["type"]: a["frequency"] for a in r["alerts"] if a["enabled"]}
    assert enabled == {"SIGNAL_FORT": "daily", "MM100_CROISEMENT": "immediate"}
    bad = client.put(f"/alerts/item/{item}", headers=H, json={"alerts": [{"type": "X", "enabled": True}]})
    assert bad.status_code == 422
    assert client.get(f"/alerts/item/{item}", headers={"X-User-Email": "b@x.be"}).status_code == 404


def test_check_all_sends_to_outbox_and_respects_frequency(setup, monkeypatch, tmp_path):
    from app.services.mail import sender

    client, item, state = setup
    client.put(f"/alerts/item/{item}", headers=H, json={"alerts": [{"type": "SIGNAL_FORT", "enabled": True, "frequency": "daily"}]})
    now = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    assert A.check_all(now) == 1                                    # score 8,2 → mail
    files = list(sender.outbox_dir().glob("*.eml"))
    assert len(files) == 1
    msg = message_from_bytes(files[0].read_bytes(), policy=policy.default)
    assert msg["To"] == "a@exemple.be" and msg["Subject"].startswith("[SIGNAL ACHAT ✅] ServiceNow (NOW)")
    hist = client.get("/alerts/history", headers=H).json()["events"]
    assert hist[0]["delivered"] == 0 and "outbox" in hist[0]["status"]
    assert A.check_all(now + timedelta(minutes=15)) == 0             # toujours ≥ 7,5 : pas de doublon
    state["full"] = full(score=6.0); A.check_all(now + timedelta(hours=1))   # repasse sous 7,5
    state["full"] = full(score=8.0)
    assert A.check_all(now + timedelta(hours=2)) == 0                # 1×/jour : en attente
    assert A.check_all(now + timedelta(hours=25)) == 1               # délai écoulé, condition vraie → envoyé


def test_real_smtp_path(setup, monkeypatch):
    """Avec SMTP configuré : STARTTLS + login + envoi (serveur simulé)."""
    import smtplib

    client, item, _ = setup
    for k, v in {"SMTP_HOST": "smtp.test", "SMTP_PORT": "587", "SMTP_USER": "moi@gmail.com",
                 "SMTP_PASSWORD": "abcd efgh", "SMTP_FROM": "moi@gmail.com"}.items():
        monkeypatch.setenv(k, v)
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): calls.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): calls.append(("starttls",))
        def login(self, u, p): calls.append(("login", u))
        def send_message(self, m): calls.append(("send", m["To"], m["Subject"]))

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    r = client.post("/alerts/test", headers=H).json()
    assert r["delivered"] is True
    assert calls == [("connect", "smtp.test", 587), ("starttls",), ("login", "moi@gmail.com"),
                     ("send", "a@exemple.be", "[TEST ✅] Analyse Boursière — alertes mail")]


def test_unsubscribe_link(setup):
    from app.database import get_conn

    client, item, _ = setup
    client.put(f"/alerts/item/{item}", headers=H, json={"alerts": [{"type": "ALERTE_BAISSE", "enabled": True}]})
    with get_conn() as conn:
        token = conn.execute("SELECT unsubscribe_token FROM alerts").fetchone()[0]
    r = client.get(f"/alerts/unsubscribe/{token}")
    assert r.status_code == 200 and "Alerte désactivée" in r.text and "ServiceNow" in r.text
    with get_conn() as conn:
        assert conn.execute("SELECT enabled FROM alerts").fetchone()[0] == 0
    assert client.get("/alerts/unsubscribe/inconnu").status_code == 404
