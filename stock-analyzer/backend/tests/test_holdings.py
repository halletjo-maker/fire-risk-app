"""Mes positions : FIFO, valeur au 31/12/2025, franchise et taxe estimée, alertes."""
from datetime import date

import pytest

from app.services import holdings

H = {"X-User-Email": "a@exemple.be"}


def tx(i, kind, day, qty, price, pid="yf:ABC", fx=1.0, fees=0.0):
    return {"id": i, "product_id": pid, "symbol": pid[3:], "name": pid[3:], "currency": "EUR", "kind": kind,
            "day": day, "qty": qty, "price": price, "fx": fx, "fees_eur": fees}


def test_fifo_after_2026_and_fees_not_deductible():
    txs = [tx(1, "BUY", "2026-02-01", 10, 100, fees=5), tx(2, "BUY", "2026-03-01", 10, 120, fees=5),
           tx(3, "SELL", "2026-06-01", 15, 150, fees=5)]
    r = holdings.compute(txs, {}, {"yf:ABC": {"price": 160, "fx": 1.0}})
    # FIFO : 10 à 100 puis 5 à 120 → gain fiscal 10×50 + 5×30 = 650 (frais ignorés)
    assert round(sum(x["gain"] for x in r["realized"]), 2) == 650
    pos = r["positions"][0]
    assert pos["qty"] == 5 and pos["cost_eur"] == 600 and pos["value_eur"] == 800 and pos["avg_price"] == 120
    assert pos["tax_gain_eur"] == 200 and pos["pnl_eur"] == 800 - 600 - 15   # économique : frais inclus


def test_pre_2026_uses_value_at_31_12_2025_or_higher_cost():
    refs = {"yf:ABC": {"ref_price": 80, "ref_fx": 1.0}}
    txs = [tx(1, "BUY", "2023-05-01", 10, 50), tx(2, "SELL", "2026-04-01", 4, 100)]
    r = holdings.compute(txs, refs, {})
    assert r["realized"][0]["gain"] == 4 * (100 - 80)           # gains d'avant 2026 exonérés
    # Prix d'achat plus élevé que le cours du 31/12/2025 : on le garde (ventes jusqu'en 2030)
    txs = [tx(1, "BUY", "2024-05-01", 10, 90), tx(2, "SELL", "2026-04-01", 10, 100)]
    assert holdings.compute(txs, refs, {})["realized"][0]["gain"] == 10 * (100 - 90)
    txs = [tx(1, "BUY", "2024-05-01", 10, 90), tx(2, "SELL", "2031-04-01", 10, 100)]
    assert holdings.compute(txs, refs, {})["realized"][0]["gain"] == 10 * (100 - 80)
    # Vente avant 2026 : pas concernée
    txs = [tx(1, "BUY", "2024-05-01", 10, 90), tx(2, "SELL", "2025-04-01", 10, 100)]
    assert holdings.compute(txs, refs, {})["realized"] == []


def test_pre_2026_pool_sold_before_newer_lots_and_currency():
    refs = {"yf:US": {"ref_price": 110, "ref_fx": 1.1}}          # 100 € au 31/12/2025
    txs = [tx(1, "BUY", "2025-01-10", 5, 88, "yf:US", fx=1.1), tx(2, "BUY", "2026-02-01", 5, 132, "yf:US", fx=1.1),
           tx(3, "SELL", "2026-09-01", 6, 165, "yf:US", fx=1.1)]
    g = [round(x["gain"], 2) for x in holdings.compute(txs, refs, {})["realized"]]
    assert g == [5 * (150 - 100), 1 * (150 - 120)]


def test_tax_years_franchise_losses_and_carry():
    rows = [{"year": 2026, "gain": 7000}, {"year": 2026, "gain": -1000},
            {"year": 2027, "gain": 15000}, {"year": 2028, "gain": 12000}]
    y = {x["year"]: x for x in holdings.tax_years(rows, today=date(2028, 6, 1))}
    assert y[2026]["net"] == 6000 and y[2026]["tax"] == 0 and y[2026]["franchise_left"] == 4000
    assert y[2027]["carry"] == 1000 and y[2027]["franchise"] == 11000 and y[2027]["tax"] == 400   # (15000-11000)×10 %
    assert y[2028]["carry"] == 0 and y[2028]["tax"] == 200          # crédit de 2026 déjà consommé en 2027
    y = {x["year"]: x for x in holdings.tax_years([], today=date(2029, 1, 1))}
    assert [y[k]["carry"] for k in (2026, 2027, 2028, 2029)] == [0, 1000, 2000, 3000]


def test_api_flow_and_alerts(client, monkeypatch):
    from app.database import get_conn
    from app.services import push
    from app.services.mail import sender

    monkeypatch.setattr(holdings, "close_on", lambda symbol, day: 80.0)
    monkeypatch.setattr(holdings, "fx_on", lambda cur, day: 1.0)
    monkeypatch.setattr(holdings, "refresh_quotes", lambda: 0)
    body = {"product_id": "yf:ABC", "symbol": "ABC", "name": "Abc SA", "currency": "EUR",
            "kind": "BUY", "day": "2024-03-01", "qty": 10, "price": 50, "fees_eur": 3}
    r = client.post("/holdings/tx", json=body, headers=H)
    assert r.status_code == 201 and r.json()["positions"][0]["ref_price"] == 80
    bad = client.post("/holdings/tx", json={**body, "kind": "SELL", "day": "2026-03-01", "qty": 11}, headers=H)
    assert bad.status_code == 400 and "10" in bad.json()["detail"]
    with get_conn() as conn:
        conn.execute("INSERT INTO holding_quotes (product_id, price, fx, stop_price, sell_price) VALUES ('yf:ABC', 81, 1, 79, 95)")
    s = client.get("/holdings", headers=H).json()
    assert s["totals"]["value_eur"] == 810 and s["positions"][0]["tax_gain_eur"] == 10   # base = 80 au 31/12/2025
    mails, pushes = [], []
    monkeypatch.setattr(sender, "send", lambda to, subj, text, html=None, attachments=None: mails.append(subj) or {"delivered": True, "status": "ok"})
    monkeypatch.setattr(push, "notify_later", lambda *a, **k: pushes.append(a))
    assert holdings.check_alerts("2026-11-02") == 1 and "approche de son stop" in mails[0]
    assert holdings.check_alerts("2026-11-02") == 0                 # une fois par jour
    tid = s["transactions"][0]["id"]
    assert client.delete(f"/holdings/tx/{tid}", headers=H).json()["positions"] == []
    assert client.get("/holdings", headers={"X-User-Email": "b@exemple.be"}).json()["positions"] == []  # privé
