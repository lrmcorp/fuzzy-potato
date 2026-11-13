"""Which push notifications the owner wants, and the market events that trigger them.

Kinds, each switchable in Atur:
  harga     price alerts the owner set (always delivered, also at night)
  pilihan   a Pilihan ARAH pick touches its stop or target 1, new picks today, a held pick turns "Kurangi"
  pantauan  the decision for a watched stock changes
  pasar     morning outlook before the open, close summary, big moves in IHSG or the rupiah, changed AI answers
  agenda    the evening before an important date (BI Rate, inflation, MSCI, Fed)
  sistem    Stockbit disconnected, so prices are delayed

Quiet hours 21.00 to 06.00 WIB hold back pasar, agenda and sistem; harga, pilihan and pantauan still come.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from .db import DB

WIB = timezone(timedelta(hours=7))
KINDS = {
    "harga": ("Peringatan harga", "Saat harga melewati batas yang Anda pasang."),
    "pilihan": ("Pilihan ARAH", "Saham pilihan menyentuh batas rugi atau target 1, pilihan baru, atau saatnya mengurangi."),
    "pantauan": ("Saham pantauan", "Keputusan ARAH untuk saham yang Anda pantau berubah."),
    "pasar": ("Ringkasan pasar", "Pagi sebelum bursa buka, ringkasan penutupan, dan gerakan besar IHSG atau rupiah."),
    "agenda": ("Agenda besok", "Malam sebelum BI Rate, inflasi, rebalancing MSCI, atau keputusan The Fed."),
    "sistem": ("Koneksi data", "Saat Stockbit terputus dan harga jadi tertunda."),
}
QUIET_EXEMPT = {"harga", "pilihan", "pantauan"}
QUIET = (21, 6)
BIG_MOVE = {"IHSG": 2.0, "USDIDR": 1.0}  # percent in a day


def prefs(db: DB) -> dict:
    saved = db.get("push_prefs") or {}
    return {k: bool(saved.get(k, True)) for k in KINDS} | {"quiet": bool(saved.get("quiet", True))}


def set_prefs(db: DB, new: dict) -> dict:
    cur = prefs(db)
    for k, v in new.items():
        if k in cur:
            cur[k] = bool(v)
    db.set("push_prefs", cur)
    return cur


def allowed(db: DB, kind: str, now: float | None = None) -> bool:
    p = prefs(db)
    if kind in KINDS and not p[kind]:
        return False
    if p["quiet"] and kind not in QUIET_EXEMPT:
        h = datetime.fromtimestamp(now if now is not None else time.time(), WIB).hour
        if h >= QUIET[0] or h < QUIET[1]:
            return False
    return True


def once(db: DB, key: str, ttl: int = 20 * 3600) -> bool:
    """True the first time `key` is seen within ttl seconds; used so one event sends one message."""
    k = f"notified:{key}"
    hit = db.get(k)
    if hit and time.time() - hit < ttl:
        return False
    db.set(k, int(time.time()))
    return True


def big_moves(quotes: dict[str, float | None], day: str) -> list[tuple[str, float]]:
    """Assets whose change today passes the threshold, each at most once per day and direction."""
    return [(k, v) for k, v in quotes.items() if v is not None and k in BIG_MOVE and abs(v) >= BIG_MOVE[k]]


def pick_hits(rows: list[dict], price_of) -> list[tuple[dict, str, float]]:
    """Open picks whose live price is at or past the stop ("stop") or target 1 ("target")."""
    out = []
    for r in rows:
        p = price_of(r["asset"])
        if not p:
            continue
        if p <= r["stop"]:
            out.append((r, "stop", p))
        elif p >= r["t1"]:
            out.append((r, "target", p))
    return out
