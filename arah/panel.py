"""Extra market data for Ringkasan: IDX session status, foreign flow, commodities and macro.

Every number here comes from stored data. When a series is not available, its value is None and the page shows
"—" instead of a guess.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from .db import DB
from .signals import quote_info, snapshot
from .universe import BY_KEY, STOCKS

WIB = timezone(timedelta(hours=7))

# IDX regular-market sessions in WIB, Monday to Thursday and Friday. Pre-closing (15.50 to 16.00) counts as the
# end of Sesi 2. Exchange holidays are not known here, so a holiday on a weekday reads as a normal session day.
_SESSIONS = {
    "mon_thu": [("08:45", "pra", "Pra-pembukaan"), ("09:00", "sesi1", "Sesi 1"), ("12:00", "istirahat", "Istirahat"),
                ("13:30", "sesi2", "Sesi 2"), ("16:00", "tutup", "Tutup")],
    "fri": [("08:45", "pra", "Pra-pembukaan"), ("09:00", "sesi1", "Sesi 1"), ("11:30", "istirahat", "Istirahat"),
            ("14:00", "sesi2", "Sesi 2"), ("16:00", "tutup", "Tutup")],
}


def idx_session(now: float | None = None) -> dict:
    """{"key", "label", "open", "day"} for the IDX at the given time (default now)."""
    t = datetime.fromtimestamp(now if now is not None else time.time(), WIB)
    if t.weekday() >= 5:
        return {"key": "tutup", "label": "Tutup", "open": False, "day": False}
    hm = t.strftime("%H:%M")
    state = ("tutup", "Tutup")
    for start, key, label in _SESSIONS["fri" if t.weekday() == 4 else "mon_thu"]:
        if hm >= start:
            state = (key, label)
    return {"key": state[0], "label": state[1], "open": state[0] in ("sesi1", "sesi2"), "day": True}


# Commodities that matter to Indonesian stocks, in the brief's order. None means no feed is set up for it.
COMMODITY_KEYS = [("COAL", "Batu bara", None), ("CPO", "CPO (sawit)", "CPO"), ("NICKEL", "Nikel", None),
                  ("GOLD", "Emas", "GOLD"), ("BRENT", "Minyak Brent", "BRENT")]


def _row(db: DB, key: str | None, label: str, unit: str = "") -> dict:
    a = BY_KEY.get(key) if key else None
    s = snapshot(db, a) if a else None
    if not s:
        return {"key": key or label, "label": label, "price": None, "chg1m": None, "src": None, "unit": unit}
    return {"key": a.key, "label": label, "price": s["price"], "chg1m": s.get("chg1m"), "decimals": a.decimals,
            "src": s.get("src") or quote_info(db, a), "unit": unit}


def commodities(db: DB) -> list[dict]:
    return [_row(db, k, label) for _, label, k in COMMODITY_KEYS]


def macro(db: DB) -> list[dict]:
    bi = db.get("bi_rate") or {}
    return [
        {"key": "BIRATE", "label": "BI Rate", "price": bi.get("value"), "chg1m": None, "decimals": 2, "unit": "%",
         "src": {"source": bi.get("source"), "at": bi.get("at"), "delay_min": 0} if bi else None},
        _row(db, "DXY", "DXY"),
        _row(db, "US10Y", "Yield AS 10 thn", "%"),
    ]


def foreign_flow(db: DB, top: int = 5) -> dict:
    """IHSG's net foreign flow for the latest day (from the Stockbit job), and the five covered stocks foreign
    investors bought and sold most over the last month (from the cached per-stock Stockbit data)."""
    day = (db.get("sbt:foreign_day:IHSG") or {}).get("v")
    if day and not day.get("net_foreign") and not day.get("foreign_buy") and not day.get("foreign_sell"):
        day = None
    rows = []
    for a in STOCKS:
        if a.country != "ID":
            continue
        hit = db.get(f"sbt:foreign:{a.key}") or {}
        v = hit.get("v") or {}
        if v.get("net_foreign") is not None:
            rows.append({"key": a.key, "name": a.name, "net": v["net_foreign"], "at": hit.get("_at")})
    rows.sort(key=lambda r: -r["net"])
    buys = [r for r in rows if r["net"] > 0][:top]
    sells = [r for r in reversed(rows) if r["net"] < 0][:top]
    at = max((r["at"] or 0 for r in rows), default=0) or None
    return {"day": day, "buy": buys, "sell": sells, "covered": len(rows), "at": at, "source": "Stockbit" if rows or day else None}


IMPACT_SIDE = {"positif": "mendukung", "negatif": "menekan", "netral": "seimbang"}


def top_news(db: DB) -> dict:
    """Per region: the most important story of the last two days, with its direction, and how many stories there are."""
    from .data.news import COUNTRY_TOPICS, top_stories

    out = {}
    for c in ("ID", "US"):
        items = top_stories(db, COUNTRY_TOPICS[c], limit=30)
        top = items[0] if items else None
        out[c] = {"count": len(items), "href": f"#/berita/{c}",
                  "top": {"text": top["title"], "direction": IMPACT_SIDE.get(top.get("impact"), "seimbang"), "url": top["url"]}
                  if top else None}
    return out


def summary(db: DB) -> dict:
    return {"session": idx_session(), "foreign": foreign_flow(db), "commodities": commodities(db), "macro": macro(db),
            "factors": gauge_factors(db), "profile": db.get("risk_profile"), "news": top_news(db)}


def gauge_factors(db: DB) -> dict:
    """What moves the Menekan↔Mendukung gauge, each with its direction for the owner: +1 mendukung, -1 menekan,
    0 seimbang, None when there is no data. The model's forecast is added by the page from the gauge itself."""
    from .outlook import price_now

    def moved(key: str, label: str, good_when_up: int, period: str = "chg1m") -> dict:
        a = BY_KEY[key]
        s = snapshot(db, a)
        if not s or s.get(period) is None:
            return {"label": label, "side": None, "value": None, "kind": "pct", "href": f"#/a/{key}"}
        return {"label": label, "side": price_now(s, a) * good_when_up, "value": s[period], "kind": "pct", "href": f"#/a/{key}"}

    flow = (db.get("sbt:foreign_day:IHSG") or {}).get("v") or {}
    net = flow.get("net_foreign")
    if not net and not flow.get("foreign_buy") and not flow.get("foreign_sell"):
        net = None  # Stockbit answers zeros before the session or for an empty day
    vix = snapshot(db, BY_KEY["VIX"])
    v1w = vix.get("chg1w") if vix else None
    return {
        "ID": [moved("IHSG", "IHSG 1 bln", 1), moved("USDIDR", "USD/IDR 1 bln", -1),
               {"label": "Asing hari ini", "side": None if net is None else (1 if net > 0 else -1 if net < 0 else 0),
                "value": net, "kind": "idr", "href": "#/a/IHSG"}],
        "US": [moved("SPX", "S&P 500 1 bln", 1),
               # Fear falling is good for stocks; a move under 10% in a week is ordinary for the VIX.
               {"label": "VIX 1 mgg", "side": None if v1w is None else (-1 if v1w > 10 else 1 if v1w < -10 else 0),
                "value": v1w, "kind": "pct", "href": "#/a/VIX"},
               moved("US10Y", "Yield AS 10 thn 1 bln", -1)],
    }
