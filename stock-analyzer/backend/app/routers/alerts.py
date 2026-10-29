"""Module 9 — configuration des alertes mail, historique, test, désinscription."""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from ..config import get_settings
from ..database import get_conn
from ..deps import current_user
from ..services import alerts as alerts_service
from ..services.mail import sender

router = APIRouter(prefix="/alerts", tags=["alertes"])


class AlertIn(BaseModel):
    type: str
    enabled: bool
    frequency: str = "immediate"

    @field_validator("type")
    @classmethod
    def v_type(cls, v: str) -> str:
        if v not in alerts_service.TYPES:
            raise ValueError("Type d'alerte inconnu")
        return v

    @field_validator("frequency")
    @classmethod
    def v_freq(cls, v: str) -> str:
        if v not in alerts_service.FREQUENCIES:
            raise ValueError("Fréquence inconnue")
        return v


class AlertsIn(BaseModel):
    alerts: list[AlertIn]


def _own_item(conn, item_id: int, user_id: int):
    row = conn.execute(
        "SELECT i.id, i.name, i.symbol, w.name AS watchlist FROM watchlist_items i "
        "JOIN watchlists w ON w.id = i.watchlist_id WHERE i.id = ? AND w.user_id = ?",
        (item_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return row


def _item_alerts(conn, item_id: int) -> list[dict]:
    existing = {r["alert_type"]: r for r in conn.execute(
        "SELECT alert_type, enabled, frequency, last_triggered_at FROM alerts WHERE item_id = ?", (item_id,))}
    out = []
    for t, meta in alerts_service.TYPES.items():
        r = existing.get(t)
        out.append({"type": t, **meta, "enabled": bool(r and r["enabled"]),
                    "frequency": r["frequency"] if r else "immediate",
                    "last_triggered_at": r["last_triggered_at"] if r else None})
    return out


@router.get("/item/{item_id}")
def get_item_alerts(item_id: int, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        item = _own_item(conn, item_id, user["id"])
        return {"item": dict(item), "alerts": _item_alerts(conn, item_id),
                "frequencies": alerts_service.FREQUENCY_LABELS, "smtp_configured": get_settings().smtp_configured}


@router.put("/item/{item_id}")
def set_item_alerts(item_id: int, payload: AlertsIn, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        _own_item(conn, item_id, user["id"])
        for a in payload.alerts:
            conn.execute(
                "INSERT INTO alerts (item_id, alert_type, enabled, frequency, unsubscribe_token) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(item_id, alert_type) DO UPDATE SET enabled = excluded.enabled, frequency = excluded.frequency",
                (item_id, a.type, 1 if a.enabled else 0, a.frequency, alerts_service.new_token()),
            )
        return {"alerts": _item_alerts(conn, item_id)}


@router.get("/history")
def history(limit: int = Query(20, ge=1, le=100), user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, alert_type, product_id, product, subject, delivered, status, sent_at FROM alert_events "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user["id"], limit)).fetchall()
    return {"events": [dict(r) for r in rows], "smtp_configured": get_settings().smtp_configured}


@router.post("/test")
def test_mail(user: dict = Depends(current_user)) -> dict:
    """Envoie un mail de test à l'adresse de l'utilisateur pour vérifier le SMTP."""
    base = get_settings().app_public_url.rstrip("/")
    text = ("Ceci est un mail de test de l'application Analyse Boursière.\n"
            "Si vous le lisez, les alertes par mail fonctionnent.\n\n"
            f"Ouvrir l'application : {base}")
    result = sender.send(user["email"], "[TEST ✅] Analyse Boursière — alertes mail", text)
    return result


@router.post("/check", status_code=202)
def check_now(background: BackgroundTasks, user: dict = Depends(current_user)) -> dict:
    """Lance tout de suite la vérification des alertes (sinon toutes les 15 minutes)."""
    background.add_task(alerts_service.check_all)
    return {"scheduled": True}


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str) -> HTMLResponse:
    """Lien du pied de mail : désactive cette alerte (sans connexion)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT a.id, a.alert_type, i.name FROM alerts a JOIN watchlist_items i ON i.id = a.item_id "
            "WHERE a.unsubscribe_token = ?", (token,)).fetchone()
        if row:
            conn.execute("UPDATE alerts SET enabled = 0 WHERE id = ?", (row["id"],))
    if row:
        meta = alerts_service.TYPES[row["alert_type"]]
        title, body = "Alerte désactivée", (f"Vous ne recevrez plus l'alerte « {meta['icon']} {meta['label']} » "
                                             f"pour {row['name'].rstrip('.')}. Vous pouvez la réactiver depuis la watchlist.")
    else:
        title, body = "Lien invalide", "Cette alerte n'existe plus (produit retiré ou watchlist supprimée)."
    base = escape(get_settings().app_public_url.rstrip("/"))
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title></head><body style="margin:0;background:#0D1117;color:#E6EDF3;font-family:Inter,Roboto,Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:16px">
<div style="max-width:420px;background:#161B22;border:1px solid #30363D;border-radius:12px;padding:24px">
<h1 style="margin:0 0 8px;font-size:20px">{escape(title)}</h1><p style="margin:0 0 16px;color:#8B949E;line-height:1.5">{escape(body)}</p>
<a href="{base}" style="display:inline-block;background:#00FF88;color:#0D1117;font-weight:700;text-decoration:none;padding:10px 16px;border-radius:8px">Ouvrir l'application</a>
</div></body></html>"""
    return HTMLResponse(page, status_code=200 if row else 404)
