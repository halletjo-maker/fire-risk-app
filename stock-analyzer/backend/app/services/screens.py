"""Listes larges (« screens ») : les 500 plus grosses sociétés introduites en Bourse aux USA
depuis 10 ans, mises à jour une fois par jour avec l'analyse technique seule.

Source de la composition : l'outil de filtrage public de Nasdaq (toutes les actions NYSE,
Nasdaq et AMEX avec leur année d'IPO). Les historiques sont téléchargés par lots de 100
(un appel Yahoo par lot), puis score technique, MM100, signal et cours Achat / Vente sont
calculés comme pour les autres watchlists. L'analyse complète (fondamentaux, actualités)
reste disponible en touchant un produit.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime

from ..config import get_settings
from ..database import get_conn
from . import targets, technical
from .decision import signal as signal_for
from .sources import yahoo
from .sources.http import fetch_text

logger = logging.getLogger(__name__)

# Listes proposées : clé d'URL → réglages
PRESETS = {
    "ipo10": {"kind": "screen:ipo10", "name": "IPO 10 ans", "years": 10, "size": 500, "color": "#06B6D4"},
    "ipo5": {"kind": "screen:ipo5", "name": "IPO 5 ans", "years": 5, "size": 100, "color": "#EC4899"},
}
BY_KIND = {v["kind"]: v for v in PRESETS.values()}
IPO_KIND = PRESETS["ipo10"]["kind"]
IPO_YEARS = 10
IPO_SIZE = 500
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
BATCH = 100
RESYNC_DAYS = 7

# Titres qui ne sont pas des actions ordinaires de sociétés
_NOT_STOCK = re.compile(
    r"%|\bnotes?\b|debentures?|preferred|\bpfd\b|warrants?|\brights?\b|\bunits?\b|subordinated|perpetual"
    r"|depositary shares?,? (?:each )?representing (?:a )?\d", re.I)
_SUFFIX = re.compile(
    r"\s+(?:Class [A-Z]\s+)?(?:Common Stock|Ordinary Shares|Common Shares|Subordinate Voting Shares"
    r"|American Depositary Shares|ADS)\b.*$", re.I)

_lock = threading.Lock()


# ── Composition ─────────────────────────────────────────────────────────────

def _cap(row: dict) -> float:
    try:
        return float(row.get("marketCap") or 0)
    except (TypeError, ValueError):
        return 0.0


def clean_name(name: str) -> str:
    return _SUFFIX.sub("", (name or "").strip()).strip(" ,") or (name or "").strip()


def select_recent_ipos(rows: list[dict], year: int | None = None, years: int = IPO_YEARS,
                       size: int = IPO_SIZE) -> list[dict]:
    """Les `size` plus fortes capitalisations introduites depuis `years` ans (une ligne par société)."""
    year = year or datetime.now().year
    best: dict[str, dict] = {}
    for r in rows:
        ipo, sym, name = (r.get("ipoyear") or "").strip(), (r.get("symbol") or "").strip(), r.get("name") or ""
        if not ipo.isdigit() or int(ipo) < year - years or not sym or "^" in sym:
            continue
        if _NOT_STOCK.search(name) or _cap(r) <= 0:
            continue
        company = clean_name(name).lower()
        if company not in best or _cap(r) > _cap(best[company]):  # une seule classe d'actions par société
            best[company] = r
    chosen = sorted(best.values(), key=_cap, reverse=True)[:size]
    return [{
        "symbol": r["symbol"].strip().replace("/", "-"),  # BRK/B (Nasdaq) → BRK-B (Yahoo)
        "name": clean_name(r["name"]),
        "ipo_year": int(r["ipoyear"]),
        "market_cap": _cap(r),
        "sector": r.get("sector") or None,
        "country": r.get("country") or None,
    } for r in chosen]


def fetch_universe() -> list[dict]:
    """Toutes les actions cotées aux USA avec leur année d'IPO (un seul appel Nasdaq)."""
    text = fetch_text(NASDAQ_URL, headers={"Accept": "application/json"}, timeout=40)
    try:
        rows = json.loads(text)["data"]["rows"]
    except (TypeError, ValueError, KeyError):
        rows = None
    if not rows:
        raise RuntimeError("Liste Nasdaq indisponible")
    return rows


def members_for(kind: str, rows: list[dict]) -> list[dict]:
    preset = BY_KIND[kind]
    return select_recent_ipos(rows, years=preset["years"], size=preset["size"])


def _write_members(conn, watchlist_id: int, members: list[dict]) -> None:
    """Aligne la composition : retire les sortants, ajoute les entrants, met à jour le rang."""
    existing = {r["symbol"]: r["id"] for r in conn.execute(
        "SELECT id, symbol FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,))}
    keep = {m["symbol"] for m in members}
    for sym, item_id in existing.items():
        if sym not in keep:
            conn.execute("DELETE FROM watchlist_items WHERE id = ?", (item_id,))
    for rank, m in enumerate(members):
        if m["symbol"] in existing:
            conn.execute("UPDATE watchlist_items SET position = ?, name = ?, ipo_year = ? WHERE id = ?",
                         (rank, m["name"], m["ipo_year"], existing[m["symbol"]]))
        else:
            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, product_id, name, product_type, position, ipo_year) "
                "VALUES (?, ?, ?, ?, 'ACTION', ?, ?)",
                (watchlist_id, m["symbol"], f"yf:{m['symbol']}", m["name"], rank, m["ipo_year"]),
            )
    conn.execute("UPDATE watchlists SET screen_synced_at = datetime('now'), updated_at = datetime('now') "
                 "WHERE id = ?", (watchlist_id,))


def create_preset_watchlist(user_id: int, key: str) -> int:
    preset = PRESETS[key]
    members = members_for(preset["kind"], fetch_universe())
    with get_conn() as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM watchlists WHERE user_id = ?", (user_id,))}
        name, n = preset["name"], 2
        while name in names:
            name, n = f"{preset['name']} {n}", n + 1
        pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM watchlists WHERE user_id = ?",
                           (user_id,)).fetchone()[0]
        wl_id = conn.execute("INSERT INTO watchlists (user_id, name, color, position, kind) VALUES (?, ?, ?, ?, ?)",
                             (user_id, name, preset["color"], pos, preset["kind"])).lastrowid
        _write_members(conn, wl_id, members)
    return wl_id


# ── Mise à jour quotidienne ─────────────────────────────────────────────────

def evaluate(df) -> dict | None:
    t = technical.quick_summary(df)
    if t is None:
        return None
    full = {"product": {"type": "ACTION"}, "quote": {"price": t["price"]}, "technical": t}
    lv = targets.compute(full) or {}
    return {"price": t["price"], "change": t["change_pct"], "score": t["score"], "signal": signal_for(t["score"]),
            **{k: lv.get(k) for k in ("buy_price", "buy_kind", "buy_note", "sell_price", "sell_note")}}


def _screen_ids(watchlist_id: int | None) -> list[int]:
    with get_conn() as conn:
        if watchlist_id is not None:
            rows = conn.execute("SELECT id FROM watchlists WHERE id = ? AND kind LIKE 'screen:%'", (watchlist_id,))
        else:
            rows = conn.execute("SELECT id FROM watchlists WHERE kind LIKE 'screen:%'")
        return [r["id"] for r in rows]


def refresh(watchlist_id: int | None = None, resync: bool = False) -> int:
    """Met à jour les listes larges (toutes, ou une seule). Renvoie le nombre de titres calculés."""
    if not _lock.acquire(blocking=False):
        logger.info("Mise à jour des listes larges déjà en cours")
        return 0
    try:
        ids = _screen_ids(watchlist_id)
        if not ids:
            return 0
        if resync:
            _resync(ids)
        marks = ",".join("?" * len(ids))
        with get_conn() as conn:
            symbols = [r["symbol"] for r in conn.execute(
                f"SELECT DISTINCT symbol FROM watchlist_items WHERE watchlist_id IN ({marks})", ids)]
        done = 0
        delay = get_settings().scraping_delay_seconds
        for start in range(0, len(symbols), BATCH):
            chunk = symbols[start:start + BATCH]
            histories = yahoo.history_many(chunk)
            with get_conn() as conn:
                for sym, df in histories.items():
                    try:
                        v = evaluate(df)
                    except Exception:
                        logger.exception("Analyse technique impossible : %s", sym)
                        continue
                    if v is None:
                        continue
                    _update(conn, ids, sym, v)
                    done += 1
            if start + BATCH < len(symbols):
                time.sleep(max(delay, 2))
        logger.info("Listes larges : %s titre(s) mis à jour", done)
        return done
    finally:
        _lock.release()


def _update(conn, ids: list[int], sym: str, v: dict) -> None:
    marks = ",".join("?" * len(ids))
    conn.execute(
        "UPDATE watchlist_items SET last_price = ?, last_change_pct = ?, last_score = ?, last_signal = ?, "
        "buy_price = ?, buy_kind = ?, buy_note = ?, sell_price = ?, sell_note = ?, last_refresh_at = datetime('now') "
        f"WHERE symbol = ? AND watchlist_id IN ({marks})",
        (v["price"], v["change"], v["score"], v["signal"], v["buy_price"], v["buy_kind"], v["buy_note"],
         v["sell_price"], v["sell_note"], sym, *ids),
    )


def _resync(ids: list[int]) -> None:
    """Composition revue au plus une fois par semaine (nouvelles IPO, sociétés retirées de la cote)."""
    with get_conn() as conn:
        due = [(r["id"], r["kind"]) for r in conn.execute(
            f"SELECT id, kind FROM watchlists WHERE id IN ({','.join('?' * len(ids))}) AND "
            f"(screen_synced_at IS NULL OR screen_synced_at < datetime('now', '-{RESYNC_DAYS} days'))", ids)
            if r["kind"] in BY_KIND]
    if not due:
        return
    try:
        rows = fetch_universe()
    except Exception as exc:
        logger.warning("Composition des listes IPO non mise à jour : %s", exc)
        return
    with get_conn() as conn:
        for wl_id, kind in due:
            _write_members(conn, wl_id, members_for(kind, rows))


def refresh_in_background(watchlist_id: int) -> None:
    threading.Thread(target=refresh, args=(watchlist_id,), daemon=True).start()
