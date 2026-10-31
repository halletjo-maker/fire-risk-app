"""Portefeuilles fictifs : capital virtuel, achats et ventes automatiques (simulation)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_conn
from ..deps import current_user
from ..services import paper

router = APIRouter(prefix="/portfolios", tags=["portefeuilles fictifs"])


class PortfolioIn(BaseModel):
    watchlist_id: int
    capital: float = Field(default=5000, ge=500, le=1_000_000)
    max_positions: int = Field(default=10, ge=1, le=30)
    name: str | None = Field(default=None, max_length=50)


def _own(conn, pid: int, user_id: int):
    pf = conn.execute("SELECT * FROM portfolios WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
    if pf is None:
        raise HTTPException(status_code=404, detail="Portefeuille introuvable")
    return pf


@router.get("")
def list_portfolios(user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY id", (user["id"],)).fetchall()
        out = []
        for pf in rows:
            s = paper.summary(conn, pf)
            s.pop("positions")
            out.append(s)
    return {"portfolios": out}


@router.post("", status_code=201)
def create(payload: PortfolioIn, background: BackgroundTasks, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        wl = conn.execute("SELECT id, name FROM watchlists WHERE id = ? AND user_id = ?",
                          (payload.watchlist_id, user["id"])).fetchone()
        if wl is None:
            raise HTTPException(status_code=404, detail="Watchlist introuvable")
        name = (payload.name or "").strip() or f"Fictif · {wl['name']}"
        pid = conn.execute(
            "INSERT INTO portfolios (user_id, watchlist_id, name, initial_cash, cash, max_positions) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], wl["id"], name, payload.capital, payload.capital, payload.max_positions)).lastrowid
        pf = conn.execute("SELECT * FROM portfolios WHERE id = ?", (pid,)).fetchone()
        result = paper.summary(conn, pf)
    background.add_task(paper.run, pid)  # premiers achats sur les cours actuels
    return {"portfolio": result}


class ReportIn(BaseModel):
    period: str = Field(default="previous", pattern="^(previous|current)$")


@router.post("/report/send")
def send_report(payload: ReportIn | None = None, user: dict = Depends(current_user)) -> dict:
    """Envoi immédiat : « previous » = mois dernier complet, « current » = du 1er à aujourd'hui."""
    from ..services import monthly

    if payload and payload.period == "current":
        now = monthly.datetime.now(monthly.TZ)
        result = monthly.send_for_user(user["id"], now.year, now.month, force=True, until_day=now.day)
    else:
        year, month = monthly.previous_month()
        result = monthly.send_for_user(user["id"], year, month, force=True)
    if result.get("status") == "Aucun portefeuille fictif sur cette période":
        result["status"] = ("Aucun portefeuille fictif le mois dernier : choisis « Mois en cours »."
                            if not (payload and payload.period == "current") else "Aucun portefeuille fictif.")
    return result


@router.get("/{pid}")
def detail(pid: int, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        pf = _own(conn, pid, user["id"])
        s = paper.summary(conn, pf)
        s["trades"] = [dict(r) for r in conn.execute(
            "SELECT id, symbol, name, currency, qty, entry_price, entry_at, exit_price, exit_at, exit_reason, pnl_eur, "
            "ROUND((exit_price * qty / exit_fx - exit_fee) / (entry_price * qty / entry_fx + entry_fee) * 100 - 100, 2) "
            "AS pnl_pct FROM portfolio_positions WHERE portfolio_id = ? AND status = 'CLOSED' "
            "ORDER BY exit_at DESC LIMIT 100", (pid,))]
        s["history"] = [dict(r) for r in conn.execute(
            "SELECT day, value_eur FROM portfolio_values WHERE portfolio_id = ? ORDER BY day", (pid,))]
        closed = [t["pnl_eur"] for t in s["trades"] if t["pnl_eur"] is not None]
        s["stats"] = {"closed": len(closed), "wins": sum(1 for x in closed if x > 0),
                      "realized_eur": round(sum(closed), 2)}
    return {"portfolio": s}


@router.post("/{pid}/run")
def run_now(pid: int, user: dict = Depends(current_user)) -> dict:
    """Applique les règles tout de suite (sur les derniers cours connus)."""
    with get_conn() as conn:
        _own(conn, pid, user["id"])
    return paper.run(pid)


@router.delete("/{pid}")
def delete(pid: int, user: dict = Depends(current_user)) -> dict:
    with get_conn() as conn:
        _own(conn, pid, user["id"])
        conn.execute("DELETE FROM portfolios WHERE id = ?", (pid,))
    return {"ok": True}
