"""Pages publiques du site (sans compte) : portefeuille témoin, demande d'accès."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..database import get_conn
from ..services import auth
from ..services.mail import sender
from .portfolios import full_detail
from .users import _client_ip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public", tags=["site public"])

MAX_PENDING = 200


@router.get("/portfolio")
def showcase() -> dict:
    """Portefeuille témoin : performance, lignes et dernières opérations, sans rien de personnel."""
    with get_conn() as conn:
        pf = conn.execute("SELECT * FROM portfolios WHERE is_public = 1 ORDER BY id LIMIT 1").fetchone()
        if pf is None:
            raise HTTPException(status_code=404, detail="Aucun portefeuille témoin pour le moment.")
        s = full_detail(conn, pf)
    value = s["value"] or 0
    return {
        "list": s["watchlist"]["name"] if s["watchlist"] else None,
        "started": s["created_at"][:10], "last_run_at": s["last_run_at"], "note": s["note"],
        "initial_cash": s["initial_cash"], "value": s["value"], "pnl_pct": s["pnl_pct"],
        "cash_pct": round(s["cash"] / value * 100, 1) if value else None,
        "fees_paid": s["fees_paid"], "max_positions": s["max_positions"],
        "positions": [{
            "name": p["name"], "symbol": p["symbol"], "entry_at": p["entry_at"], "pnl_pct": p["pnl_pct"],
            "weight_pct": round(p["value_eur"] / value * 100, 1) if value else None,
        } for p in s["positions"]],
        "trades": [{k: t[k] for k in ("name", "symbol", "entry_at", "exit_at", "exit_reason", "pnl_pct")}
                   for t in s["trades"][:15]],
        "history": s["history"], "benchmark_label": s["benchmark_label"],
        "stats": {"closed": s["stats"]["closed"], "wins": s["stats"]["wins"]},
    }


class AccessRequestIn(BaseModel):
    email: EmailStr
    message: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=200)  # champ piège invisible : rempli = robot


DONE = {"ok": True, "message": "Merci ! Ta demande est enregistrée. Si elle est acceptée, tu recevras une invitation par mail."}


def _notify_admins(email: str, message: str | None) -> None:
    with get_conn() as conn:
        admins = [r["email"] for r in conn.execute("SELECT email FROM users WHERE is_admin = 1")]
    text = (f"Nouvelle demande d'accès à MM100 : {email}\n\n"
            + (f"Son message : {message}\n\n" if message else "")
            + "Pour accepter ou refuser : menu de l'application → « Inviter un ami » → Demandes d'accès.\n")
    for to in admins:
        sender.send(to, f"Demande d'accès : {email}", text)


@router.post("/access-request", status_code=202)
def access_request(payload: AccessRequestIn, request: Request, background: BackgroundTasks) -> dict:
    """Formulaire « Demander une invitation » de la page d'accueil. Réponse identique dans tous les cas."""
    if payload.website:
        return DONE
    ip = _client_ip(request)
    if auth.throttle.blocked(f"access:{ip}", f"access:{ip}"):
        raise HTTPException(status_code=429, detail="Trop de demandes depuis cette connexion. Réessaie plus tard.")
    auth.throttle.fail(f"access:{ip}", f"access:{ip}")  # 5 demandes par connexion en 15 min
    email = payload.email.strip().lower()
    message = (payload.message or "").strip() or None
    with get_conn() as conn:
        known = conn.execute("SELECT 1 FROM users WHERE email = ? AND password_hash IS NOT NULL", (email,)).fetchone()
        pending = conn.execute("SELECT COUNT(*) FROM invite_requests").fetchone()[0]
        if known or pending >= MAX_PENDING:
            return DONE
        added = conn.execute("INSERT OR IGNORE INTO invite_requests (email, message) VALUES (?, ?)",
                             (email, message)).rowcount
    if added:
        background.add_task(_notify_admins, email, message)
        from ..services import push
        push.notify_admins("access", "Nouvelle demande d'accès", f"{email} demande une invitation à MM100.", "/")
    return DONE
