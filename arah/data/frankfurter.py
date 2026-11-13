"""Daily exchange rates from the European Central Bank, via the free Frankfurter API (no key).

A second source for the currency pairs when Yahoo refuses this server: it fills the same daily
series ARAH reads, under the Yahoo symbol, so every page and forecast keeps working. Yahoo's own
bars take over again on the days it answers.
"""
from __future__ import annotations

import calendar
import logging
import time
from datetime import date, timedelta

import httpx

from ..db import DB

log = logging.getLogger("arah.frankfurter")
URL = "https://api.frankfurter.dev/v1"
# Yahoo symbol -> (base, quote). ECB publishes all of these currencies.
PAIRS = {
    "IDR=X": ("USD", "IDR"), "JPYIDR=X": ("JPY", "IDR"), "SGDIDR=X": ("SGD", "IDR"), "EURIDR=X": ("EUR", "IDR"),
    "JPY=X": ("USD", "JPY"), "SGD=X": ("USD", "SGD"), "CNY=X": ("USD", "CNY"),
}
YEARS = 10


def _daily(db: DB, symbol: str) -> tuple[int, int | None]:
    r = db.one("SELECT COUNT(*) n, MAX(ts) m FROM bars WHERE symbol=? AND interval='1d'", (symbol,))
    return r["n"], r["m"]


def needs_fill(db: DB, symbol: str) -> bool:
    n, last = _daily(db, symbol)
    return n < 300 or last is None or time.time() - last > 3 * 86400


def parse(data: dict, quote: str) -> list[tuple[int, float]]:
    out = []
    for day, rates in sorted((data.get("rates") or {}).items()):
        v = (rates or {}).get(quote)
        try:
            d = date.fromisoformat(day)
        except ValueError:
            continue
        if isinstance(v, (int, float)) and v > 0:
            out.append((calendar.timegm(d.timetuple()), float(v)))
    return out


async def fill(db: DB, symbols: list[str]) -> dict[str, int]:
    """Fill missing or stale daily FX history. Returns {symbol: rows written}."""
    todo = [s for s in symbols if s in PAIRS and needs_fill(db, s)]
    if not todo or time.time() - db.get("frankfurter_try_at", 0) < 1800:
        return {}
    db.set("frankfurter_try_at", int(time.time()))
    start = (date.today() - timedelta(days=365 * YEARS)).isoformat()
    written: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for sym in todo:
            base, quote = PAIRS[sym]
            n, last = _daily(db, sym)
            since = start if n < 300 or last is None else date.fromtimestamp(last - 7 * 86400).isoformat()
            try:
                r = await client.get(f"{URL}/{since}..", params={"base": base, "symbols": quote})
                r.raise_for_status()
                rows = parse(r.json(), quote)
            except (httpx.HTTPError, ValueError) as e:
                log.warning("frankfurter %s failed: %s", sym, e)
                continue
            if rows:
                with db.tx() as c:
                    # Only days Yahoo has not given: its bars stay the reference when present.
                    c.executemany("INSERT OR IGNORE INTO bars (symbol, interval, ts, o, h, l, c, v) VALUES (?,?,?,?,?,?,?,?)",
                                  [(sym, "1d", t, v, v, v, v, 0.0) for t, v in rows])
                written[sym] = len(rows)
    if written:
        log.info("filled daily FX history from the ECB: %s", written)
    return written
