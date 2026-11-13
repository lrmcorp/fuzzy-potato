"""What the owner's Stockbit terminal shows about one Indonesian stock, read-only and cached:

- bandar detector (broker accumulation or distribution, top buyers versus sellers),
- foreign versus domestic flow (net foreign over the last month and per day),
- major-holder and insider filings (who bought or sold, and how much),
- the stock's Stockbit stream (latest community and news posts, unverified),
- daily price history, a fallback when Yahoo refuses this server.

Every value is parsed defensively: Stockbit's fields change without notice, and a field that cannot be
read is left out rather than guessed.
"""
from __future__ import annotations

import calendar
import logging
import re
import time
from datetime import datetime

from ..db import DB
from .stockbit import Stockbit, StockbitError, _num

log = logging.getLogger("arah.sbterm")
TTL = {"bandar": 1800, "foreign": 3600, "insider": 12 * 3600, "stream": 1800, "history": 12 * 3600}


def _val(v) -> float | None:
    """A number from Stockbit's mixed shapes: 12.3, "12.3", "1,234", {"raw": 12.3}, {"value": "12.3"}."""
    if isinstance(v, dict):
        for k in ("raw", "value", "amount", "number", "val"):
            if k in v:
                return _val(v[k])
        nums = [x for x in (_val(x) for x in v.values() if not isinstance(x, dict)) if x is not None]
        return nums[0] if nums else None
    if isinstance(v, str):
        v = v.replace(",", "").replace("%", "").strip()
    return _num(v)


def accdist_side(label: str | None) -> int:
    """+2 big accumulation, +1 accumulation, 0 neutral, -1 distribution, -2 big distribution."""
    s = (label or "").lower()
    big = "big" in s
    if "acc" in s:
        return 2 if big else 1
    if "dist" in s:
        return -2 if big else -1
    return 0


async def _cached(db: DB, kind: str, code: str, fetch):
    key = f"sbt:{kind}:{code}"
    hit = db.get(key)
    if hit and time.time() - hit.get("_at", 0) < TTL[kind]:
        return hit.get("v")
    try:
        v = await fetch()
    except (StockbitError, ValueError, KeyError, TypeError) as e:
        log.info("stockbit %s %s unavailable: %s", kind, code, e)
        return hit.get("v") if hit else None
    db.set(key, {"_at": int(time.time()), "v": v})
    return v


async def bandar(db: DB, sb: Stockbit, code: str) -> dict | None:
    async def fetch():
        d = (await sb.get(f"/marketdetectors/{code}")).get("bandar_detector") or {}
        if not d:
            return None
        part = lambda k: {"label": (d.get(k) or {}).get("accdist"), "pct": _val((d.get(k) or {}).get("percent")),
                          "amount": _val((d.get(k) or {}).get("amount"))}
        out = {"label": d.get("broker_accdist") or (d.get("avg") or {}).get("accdist"),
               "avg": part("avg"), "avg5": part("avg5"), "top1": part("top1"), "top3": part("top3"),
               "top5": part("top5"), "top10": part("top10"),
               "buyers": _val(d.get("total_buyer")), "sellers": _val(d.get("total_seller")), "value": _val(d.get("value"))}
        out["side"] = accdist_side(out["label"])
        return out
    return await _cached(db, "bandar", code, fetch)


async def foreign(db: DB, sb: Stockbit, code: str) -> dict | None:
    async def fetch():
        d = await sb.get(f"/findata-view/foreign-domestic/v1/chart-data/{code}"
                         "?market_type=MARKET_TYPE_REGULAR&period=PERIOD_RANGE_1M")
        s = d.get("summary") or {}
        if not s:
            return None
        return {"range": s.get("date_range"), "net_foreign": _val((s.get("net_foreign") or {}).get("value")),
                "foreign_buy": _val((s.get("foreign_buy") or {}).get("value")),
                "foreign_sell": _val((s.get("foreign_sell") or {}).get("value")),
                "net_domestic": _val((s.get("net_domestic") or {}).get("value"))}
    return await _cached(db, "foreign", code, fetch)


def _holder_date(s: str | None) -> int | None:
    for fmt in ("%d %b %y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return calendar.timegm(datetime.strptime(str(s).strip(), fmt).timetuple())
        except ValueError:
            continue
    return None


async def insider(db: DB, sb: Stockbit, code: str) -> list[dict] | None:
    async def fetch():
        d = await sb.get(f"/insider/company/majorholder?symbols={code}&page=1&limit=10")
        out = []
        for m in d.get("movement") or []:
            ch = m.get("changes") or {}
            cur = m.get("current") or {}
            action = str(m.get("action_type") or "").replace("ACTION_TYPE_", "").replace("_", " ").title()[:30]
            out.append({"name": _name(m.get("name")), "date": m.get("date"), "at": _holder_date(m.get("date")),
                        "action": action, "side": insider_side(action), "nationality": str(m.get("nationality") or "")[:20],
                        "change_shares": _val(ch.get("value") if isinstance(ch, dict) else ch) if ch else None,
                        "change_pct": _val(ch.get("percentage")) if isinstance(ch, dict) else None,
                        "now_pct": _val(cur.get("percentage")) if isinstance(cur, dict) else None,
                        "price": str(m.get("price_formatted") or "")[:20]})
        return out
    return await _cached(db, "insider", code, fetch)


def _name(v) -> str:
    """HENDRA TANUMIHARDJA -> Hendra Tanumihardja, keeping company forms such as PT and Tbk readable."""
    words = str(v or "").title().split()
    fix = {"Pt": "PT", "Tbk": "Tbk", "Ltd": "Ltd", "Llc": "LLC", "Bv": "BV", "Inc": "Inc", "Plc": "PLC", "Ii": "II"}
    return " ".join(fix.get(w.strip(".,"), w) for w in words)[:80]


def insider_side(action: str) -> int:
    a = action.lower()
    return 1 if ("buy" in a or "beli" in a or "acq" in a) else -1 if ("sell" in a or "jual" in a or "dispos" in a) else 0


_TAG = re.compile(r"<[^>]+>|\$[A-Z]{3,5}\b|\[%[^%\]]*%\]")
# Words that make a post about the stock or the market rather than politics or chatter.
_MARKET = ("asing", "akumulasi", "distribusi", "bandar", "broker", "laba", "dividen", "target", "support", "resist",
           "breakout", "volume", "kuartal", "rights", "buyback", "net buy", "net sell", "valuasi", "per ", "pbv", "nim", "kredit",
           "foreign", "earnings", "profit", "harga", "tp ", "entry", "cutloss", "naik", "turun")


async def stream(db: DB, sb: Stockbit, code: str) -> list[dict] | None:
    async def fetch():
        d = await sb.get(f"/stream/v3/symbol/{code}?category=STREAM_CATEGORY_ALL&limit=20")
        out = []
        for p in d.get("stream") or []:
            text = _TAG.sub(" ", str(p.get("title") or p.get("content") or "")).strip()
            text = " ".join(text.split())[:220]
            if not text:
                continue
            if not any(w in text.lower() for w in _MARKET):
                continue  # politics, jokes and personal chatter say nothing about the stock
            out.append({"text": text, "at": str(p.get("created_at") or "")[:19], "likes": int(_val(p.get("total_likes")) or 0),
                        "replies": int(_val(p.get("total_replies")) or 0), "type": str(p.get("type") or "")[:20],
                        "url": str(p.get("title_url") or "")[:200]})
        # The posts people liked most first ("replies" counts a whole thread, so it does not rank).
        return sorted(out, key=lambda x: -x["likes"])[:8]
    return await _cached(db, "stream", code, fetch)


async def daily_history(db: DB, sb: Stockbit, code: str) -> list[tuple[int, float, float, float, float, float]]:
    """About a year of daily candles: (day start UTC, open, high, low, close, volume)."""
    d = await sb.get(f"/charts/{code}/daily?timeframe=1y&chart_type=PRICE_CHART_TYPE_CANDLE")
    out = []
    for row in d.get("prices") or []:
        c, t = _val(row.get("value")), _val(row.get("date"))
        if not c or not t:
            continue
        t = t / 1000 if t > 1e11 else t
        # Stockbit stamps a day at 00:00 Jakarta (17:00 UTC the day before); key it by the Jakarta date.
        day = int((t + 7 * 3600) // 86400 * 86400)
        out.append((day, _val(row.get("open")) or c, _val(row.get("high")) or c, _val(row.get("low")) or c, c,
                    (_val(row.get("volume")) or 0) * 100))
    return out


async def snapshot(db: DB, sb: Stockbit, code: str) -> dict:
    """Everything above for one stock, each part independent of the others."""
    return {"bandar": await bandar(db, sb, code), "foreign": await foreign(db, sb, code),
            "insider": await insider(db, sb, code), "stream": await stream(db, sb, code), "at": int(time.time())}


def fact_lines(code: str, s: dict) -> list[tuple[str, str]]:
    """Plain English lines for the analysts, each with an id they can cite."""
    out = []
    b = s.get("bandar") or {}
    if b.get("label"):
        top5 = (b.get("top5") or {}).get("label")
        out.append((f"{code}.SB1", f"Stockbit bandar detector today: {b['label']}"
                    + (f"; top 5 brokers {top5}" if top5 else "")
                    + (f"; {int(b['buyers'])} buying brokers vs {int(b['sellers'])} selling" if b.get("buyers") and b.get("sellers") else "")))
    f = s.get("foreign") or {}
    if f.get("net_foreign") is not None:
        side = "net bought" if f["net_foreign"] > 0 else "net sold"
        out.append((f"{code}.SB2", f"Foreign investors {side} Rp {abs(f['net_foreign']):,.0f} of {code} over the last month"
                    + (f" ({f['range']})" if f.get("range") else "")))
    recent = [m for m in (s.get("insider") or []) if m.get("at") and time.time() - m["at"] < 120 * 86400][:3]
    for i, m in enumerate(recent, 3):
        out.append((f"{code}.SB{i}", f"Major-holder filing {m['date']}: {m['name']} {m['action'] or 'changed holding'}"
                    + (f" ({m['change_pct']:+.2f}% of shares)" if m.get("change_pct") is not None else "")
                    + (f", now {m['now_pct']:.2f}%" if m.get("now_pct") is not None else "")))
    busy = [p for p in (s.get("stream") or []) if p["likes"] >= 5][:2]
    for i, p in enumerate(busy, 6):
        out.append((f"{code}.SB{i}", f"Stockbit community post ({p['likes']} likes, unverified opinion): {p['text'][:160]}"))
    return out
