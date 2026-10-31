"""Rapport mensuel des portefeuilles fictifs + réglages mail depuis l'application."""
from datetime import date

import pytest

from app.database import get_conn
from app.services import monthly
from app.services.mail import sender

H = {"X-User-Email": "a@exemple.be"}


@pytest.fixture()
def data(client, monkeypatch):
    monkeypatch.setattr(monthly, "benchmark", lambda y, m, since=None: 0.4 if since else 1.8)
    client.post("/watchlists", json={"name": "W"}, headers=H)
    with get_conn() as conn:
        uid = conn.execute("SELECT id FROM users WHERE email = 'a@exemple.be'").fetchone()[0]
        pid = conn.execute("INSERT INTO portfolios (user_id, name, initial_cash, cash, created_at) "
                           "VALUES (?, 'Fictif · Monde', 5000, 3000, '2026-09-20 10:00:00')", (uid,)).lastrowid
        for day, v in (("2026-09-30", 5100), ("2026-10-15", 5300), ("2026-10-31", 5355)):
            conn.execute("INSERT INTO portfolio_values VALUES (?, ?, ?)", (pid, day, v))
        def pos(sym, entry_at, status="OPEN", exit_at=None, pnl=None, exit_price=None, reason=None):
            conn.execute(
                "INSERT INTO portfolio_positions (portfolio_id, symbol, name, currency, qty, entry_price, entry_fx, entry_fee, "
                "entry_at, stop, stop_pct, target, last_price, last_fx, status, exit_price, exit_fx, exit_fee, exit_at, "
                "exit_reason, pnl_eur) VALUES (?, ?, ?, 'EUR', 10, 100, 1, 1, ?, 90, 10, 120, 110, 1, ?, ?, 1, 1, ?, ?, ?)",
                (pid, sym, f"Société {sym}", entry_at, status, exit_price, exit_at, reason, pnl))
        pos("AAA", "2026-10-02 09:00:00", "CLOSED", "2026-10-20 15:00:00", 198.0, 120, "Objectif de vente atteint")
        pos("BBB", "2026-10-03 09:00:00", "CLOSED", "2026-10-25 15:00:00", -102.0, 90, "Stop-loss touché")
        pos("CCC", "2026-09-25 09:00:00")
        pos("DDD", "2026-10-28 09:00:00")
    return client, uid, pid


def test_build_and_render(data):
    client, uid, pid = data
    r = monthly.build(uid, 2026, 10)
    p = r["portfolios"][0]
    assert r["label"] == "octobre 2026" and r["benchmark"] == 1.8
    assert (p["start"], p["end"], p["month_pct"]) == (5100, 5355, 5.0)
    assert p["total_pct"] == pytest.approx(7.1) and p["buys"] == 3 and p["sells"] == 2 and p["wins"] == 1
    assert p["realized"] == 96.0 and p["fees"] == 5.0  # 3 achats + 2 ventes à 1 €
    assert p["best"]["symbol"] == "AAA" and p["worst"]["symbol"] == "BBB" and len(p["open"]) == 2
    subject, text, html = monthly.render(r)
    assert subject == "📊 Rapport octobre 2026 — portefeuilles fictifs"
    assert "5 100,00 € → 5 355,00 € (+5,00 % sur le mois)" in text
    assert "ETF MSCI World +1,80 % sur le mois complet" in text and "Société AAA" in html and "MiFID" in html
    assert p["benchmark"] is None  # portefeuille créé avant le mois : repère du mois complet
    assert monthly.build(uid, 2026, 8) is None  # portefeuille pas encore créé


def test_portfolio_created_during_month(data):
    client, uid, pid = data
    with get_conn() as conn:
        conn.execute("UPDATE portfolios SET created_at = '2026-10-30 20:00:00' WHERE id = ?", (pid,))
        conn.execute("DELETE FROM portfolio_values WHERE day < '2026-10-30'")
    p = monthly.build(uid, 2026, 10)["portfolios"][0]
    assert p["start"] == 5000 and p["created_in_month"] and p["month_pct"] == pytest.approx(7.1)
    assert p["benchmark"] == 0.4  # repère calculé depuis la création
    text = monthly.render(monthly.build(uid, 2026, 10))[1]
    assert "depuis sa création le 30/10" in text and "sur la même période : +0,40 %" in text


def test_send_all_once_and_opt_out(data, monkeypatch):
    client, uid, pid = data
    sent = []
    monkeypatch.setattr(sender, "send", lambda to, subj, text, html=None: sent.append((to, subj)) or
                        {"delivered": True, "status": "Envoyé", "file": None})
    assert monthly.previous_month(date(2026, 11, 1)) == (2026, 10) and monthly.previous_month(date(2027, 1, 1)) == (2026, 12)
    assert monthly.send_all(date(2026, 11, 1)) == 1
    assert monthly.send_all(date(2026, 11, 2)) == 0  # déjà envoyé : pas de doublon
    assert sent == [("a@exemple.be", "📊 Rapport octobre 2026 — portefeuilles fictifs")]

    assert client.put("/users/me/preferences", json={"monthly_report": False}, headers=H).json() == {"monthly_report": False}
    assert client.get("/users/me", headers=H).json()["preferences"] == {"monthly_report": False}
    assert monthly.send_all(date(2026, 12, 1)) == 0


def test_send_now_endpoint(data, monkeypatch):
    client, uid, pid = data
    monkeypatch.setattr(sender, "send", lambda *a, **k: {"delivered": False, "status": "SMTP non configuré", "file": None})
    monkeypatch.setattr(monthly, "previous_month", lambda today=None: (2026, 10))
    r = client.post("/portfolios/report/send", headers=H).json()
    assert r == {"sent": False, "status": "SMTP non configuré", "label": "octobre 2026", "email": "a@exemple.be"}


def test_mail_settings_from_app(auth_client, monkeypatch):
    c = auth_client
    c.post("/users/register", json={"email": "jean@exemple.be", "password": "correct-horse-42"})
    assert c.get("/admin/mail").json()["configured"] is False
    monkeypatch.setattr(sender, "check_login", lambda u, p: "Gmail refuse ces identifiants." if p != "abcdefghijklmnop" else None)
    bad = c.put("/admin/mail", json={"user": "moi@gmail.com", "password": "mauvais-mdp"})
    assert bad.status_code == 400 and "refuse" in bad.json()["detail"]
    ok = c.put("/admin/mail", json={"user": "moi@gmail.com", "password": "abcd efgh ijkl mnop"})  # espaces de Google retirés
    assert ok.json() == {"configured": True, "source": "app", "user": "moi@gmail.com"}
    assert "password" not in ok.text and "abcdefghijklmnop" not in ok.text
    cfg = sender.smtp_config()
    assert (cfg["host"], cfg["port"], cfg["password"], cfg["from"]) == ("smtp.gmail.com", 587, "abcdefghijklmnop", "moi@gmail.com")
    assert c.get("/health").json()["config"]["smtp_configured"] is True
    assert c.delete("/admin/mail").json()["configured"] is False
