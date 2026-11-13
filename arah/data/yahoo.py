from __future__ import annotations

import asyncio
import logging
import os
import time
from urllib.parse import quote

import httpx
import numpy as np

from ..db import DB

log = logging.getLogger("arah.yahoo")

BASE = os.environ.get("ARAH_YAHOO_BASE", "https://query1.finance.yahoo.com").rstrip("/")
# Yahoo serves the same API from a second host; a 429 on one is tried once on the other.
ALT_BASE = "https://query2.finance.yahoo.com" if "query1.finance.yahoo.com" in BASE else BASE
# Yahoo answers 429 to detailed browser user agents but serves a bare one.
HEADERS = {"User-Agent": "Mozilla/5.0"}
FIRST_RANGE = {"1h": "730d", "1d": "10y"}
# Yahoo rejects hourly requests that reach back more than 730 days.
REFRESH_RANGE = {"1h": "5d", "1d": "1mo"}
MIN_REFRESH_GAP = {"1h": 600, "1d": 1800}


class YahooError(Exception):
    pass


class Gate:
    """One shared brake for every Yahoo call.

    Yahoo blocks an address that asks too often (HTTP 429), and retrying straight away only keeps the
    block going. So: at most two requests at a time with a short gap, no retry on 429, and after a 429
    on both hosts every Yahoo call pauses (15 minutes, doubling up to 2 hours while it persists).
    The pause is kept in the database so a restart does not start hammering again."""

    def __init__(self) -> None:
        self.db: DB | None = None
        self.sem = asyncio.Semaphore(2)
        self.gap = 0.4
        self._last = 0.0
        self._until = 0.0
        self._step = 0

    def attach(self, db: DB) -> None:
        self.db = db
        st = db.get("yahoo_pause") or {}
        self._until, self._step = float(st.get("until", 0)), int(st.get("step", 0))

    def paused_until(self) -> float:
        return self._until if self._until > time.time() else 0.0

    def pause(self) -> None:
        self._step = min(self._step + 1, 4)
        self._until = time.time() + 900 * 2 ** (self._step - 1)
        log.warning("Yahoo answered 429: pausing Yahoo calls until %s", time.strftime("%H:%M", time.localtime(self._until)))
        if self.db:
            self.db.set("yahoo_pause", {"until": int(self._until), "step": self._step})

    def ok(self) -> None:
        if self._step:
            self._step = 0
            if self.db:
                self.db.set("yahoo_pause", {"until": 0, "step": 0})


GATE = Gate()


class RateLimited(YahooError):
    pass


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    last: Exception | None = None
    for attempt in range(3):
        if GATE.paused_until():
            raise RateLimited(f"Yahoo paused after a 429 until {time.strftime('%H:%M', time.localtime(GATE.paused_until()))}")
        try:
            async with GATE.sem:
                wait = GATE._last + GATE.gap - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                GATE._last = time.monotonic()
                r = await client.get(url, params=params, headers=HEADERS, timeout=25)
                if r.status_code == 429 and ALT_BASE != BASE and url.startswith(BASE):
                    r = await client.get(ALT_BASE + url[len(BASE):], params=params, headers=HEADERS, timeout=25)
            if r.status_code == 429:
                GATE.pause()
                raise RateLimited("Yahoo answered 429 (too many requests from this server)")
            if r.status_code == 404:
                raise YahooError(f"not found: {url}")
            if r.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            GATE.ok()
            return r.json()
        except YahooError:
            raise
        except (httpx.HTTPError, ValueError) as e:
            last = e
            await asyncio.sleep(1.5 * (attempt + 1))
    raise YahooError(f"request failed: {last}")


async def fetch_chart(client: httpx.AsyncClient, symbol: str, interval: str, rng: str) -> tuple[dict, list[tuple]]:
    data = await _get_json(
        client, f"{BASE}/v8/finance/chart/{quote(symbol)}", {"range": rng, "interval": interval}
    )
    try:
        res = data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        raise YahooError(f"empty chart for {symbol}")
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        c = (q.get("close") or [None])[i]
        if c is None or c <= 0:
            continue
        o = (q.get("open") or [None])[i]
        h = (q.get("high") or [None])[i]
        l = (q.get("low") or [None])[i]
        v = (q.get("volume") or [None])[i]
        rows.append((int(t), o or c, h or c, l or c, float(c), v or 0))
    return res.get("meta", {}), rows


def _bucket(ts: int, interval: str, gmtoffset: int = 0) -> int:
    # The live bar carries the timestamp of the last trade; snap it to the
    # bar start so a refresh overwrites it instead of adding a duplicate.
    if interval == "1h":
        return ts - ts % 3600
    # Daily bars are keyed by the exchange's local calendar date.
    return (ts + gmtoffset) // 86400 * 86400


async def refresh_symbol(db: DB, client: httpx.AsyncClient, symbol: str, interval: str, force: bool = False) -> int:
    stamp_key = f"fetched:{symbol}:{interval}"
    last_fetch = db.get(stamp_key, 0)
    if not force and time.time() - last_fetch < MIN_REFRESH_GAP[interval]:
        return 0
    have = db.one("SELECT COUNT(*) n, MAX(ts) m FROM bars WHERE symbol=? AND interval=?", (symbol, interval))
    stale = have["m"] is None or time.time() - have["m"] > 20 * 86400
    rng = FIRST_RANGE[interval] if have["n"] < 200 or stale else REFRESH_RANGE[interval]
    meta, rows = await fetch_chart(client, symbol, interval, rng)
    gmt = int(meta.get("gmtoffset") or 0)
    if rows:
        with db.tx() as c:
            c.executemany(
                "INSERT INTO bars (symbol, interval, ts, o, h, l, c, v) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(symbol, interval, ts) DO UPDATE SET o=excluded.o, h=excluded.h, "
                "l=excluded.l, c=excluded.c, v=excluded.v",
                [(symbol, interval, _bucket(r[0], interval, gmt), *r[1:]) for r in rows],
            )
    price = meta.get("regularMarketPrice")
    if price:
        db.x(
            "INSERT INTO quotes (symbol, price, prev_close, market_ts, currency, fetched_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, prev_close=excluded.prev_close, "
            "market_ts=excluded.market_ts, currency=excluded.currency, fetched_at=excluded.fetched_at",
            (symbol, price, meta.get("previousClose") or meta.get("chartPreviousClose"),
             meta.get("regularMarketTime"), meta.get("currency"), int(time.time())),
        )
    db.set(stamp_key, int(time.time()))
    return len(rows)


async def refresh_many(db: DB, symbols: list[str], intervals: tuple[str, ...] = ("1h", "1d"),
                       force: bool = False) -> dict[str, str]:
    """Refresh bars for many symbols. Returns {symbol: error} for the ones that failed."""
    errors: dict[str, str] = {}
    sem = asyncio.Semaphore(4)

    async def one(client: httpx.AsyncClient, sym: str, iv: str) -> None:
        async with sem:
            try:
                await refresh_symbol(db, client, sym, iv, force)
            except RateLimited as e:  # expected while paused: one line, not one per symbol
                errors[sym] = str(e)[:160]
            except Exception as e:  # one bad symbol must not stop the batch
                errors[sym] = str(e)[:160]
                log.warning("refresh %s %s failed: %s", sym, iv, e)

    real = [s for s in symbols if not s.startswith("SYN:")]
    async with httpx.AsyncClient(http2=False) as client:
        await asyncio.gather(*(one(client, s, iv) for s in real for iv in intervals))
    return errors


def build_synthetic(db: DB, symbol: str, num_symbol: str, den_symbol: str) -> int:
    """Rebuild a cross rate as numerator / denominator on the bars both legs share."""
    total = 0
    for interval in ("1h", "1d"):
        a, b = load_bars(db, num_symbol, interval, 6000), load_bars(db, den_symbol, interval, 6000)
        den = dict(zip(b["ts"].tolist(), b["c"].tolist()))
        rows = [(symbol, interval, int(t), c / den[t], c / den[t], c / den[t], c / den[t], 0.0)
                for t, c in zip(a["ts"].tolist(), a["c"].tolist()) if t in den and den[t] > 0]
        with db.tx() as c:
            c.execute("DELETE FROM bars WHERE symbol=? AND interval=?", (symbol, interval))
            c.executemany("INSERT INTO bars (symbol, interval, ts, o, h, l, c, v) VALUES (?,?,?,?,?,?,?,?)", rows)
        total += len(rows)
    qa, qb = quote_of(db, num_symbol), quote_of(db, den_symbol)
    if qa and qb and qa["price"] and qb["price"]:
        prev = (qa["prev_close"] / qb["prev_close"]) if qa["prev_close"] and qb["prev_close"] else None
        db.x(
            "INSERT INTO quotes (symbol, price, prev_close, market_ts, currency, fetched_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, prev_close=excluded.prev_close, "
            "market_ts=excluded.market_ts, fetched_at=excluded.fetched_at",
            (symbol, qa["price"] / qb["price"], prev, min(qa["market_ts"] or 0, qb["market_ts"] or 0), "IDR", int(time.time())),
        )
    return total


def spike_mask(c: np.ndarray, k: float = 6.0, max_run: int = 5) -> np.ndarray:
    """True for bad ticks: a jump far outside normal moves that is undone by an equal jump back.

    Covers single bars and short flat runs (Yahoo sometimes serves several wrong
    daily closes in a row). A real shock is kept: prices keep moving after it
    instead of sitting still and then snapping back.
    """
    bad = np.zeros(len(c), dtype=bool)
    if len(c) < 30:
        return bad
    r = np.diff(np.log(c))
    nz = r[r != 0]
    if len(nz) < 20:
        return bad
    sigma = 1.4826 * np.median(np.abs(nz - np.median(nz))) or nz.std()
    i = 0
    while i < len(r) - 1:
        if abs(r[i]) > k * sigma:
            for run in range(1, max_run + 1):
                j = i + run
                if j >= len(r):
                    break
                calm = np.all(np.abs(r[i + 1:j]) < 2.5 * sigma)
                if calm and abs(r[j]) > k * sigma and abs(r[i:j + 1].sum()) < 0.35 * abs(r[i]):
                    bad[i + 1:j + 1] = True
                    i = j
                    break
        i += 1
    return bad


def load_bars(db: DB, symbol: str, interval: str, limit: int = 3000, clean: bool = True) -> dict[str, np.ndarray]:
    rows = db.q(
        "SELECT ts, o, h, l, c, v FROM bars WHERE symbol=? AND interval=? ORDER BY ts DESC LIMIT ?",
        (symbol, interval, limit),
    )
    rows = rows[::-1]
    out = {
        "ts": np.array([r["ts"] for r in rows], dtype=np.int64),
        "o": np.array([r["o"] for r in rows], dtype=float),
        "h": np.array([r["h"] for r in rows], dtype=float),
        "l": np.array([r["l"] for r in rows], dtype=float),
        "c": np.array([r["c"] for r in rows], dtype=float),
        "v": np.array([r["v"] or 0 for r in rows], dtype=float),
    }
    if clean and len(rows):
        # Yahoo's FX series carry bad ticks, sometimes for days. Exchange-traded prices are
        # cleaner, and their sharp reversals are usually real, so they get a much higher bar.
        fx = symbol.endswith("=X")
        keep = ~spike_mask(out["c"], k=6.0 if fx else 14.0, max_run=5 if fx else 1)
        out = {k: v[keep] for k, v in out.items()}
    return out


def quote_of(db: DB, symbol: str) -> dict | None:
    row = db.one("SELECT * FROM quotes WHERE symbol=?", (symbol,))
    return dict(row) if row else None


FUND_TYPES = "trailingPeRatio,trailingPbRatio,trailingMarketCap,annualTotalRevenue,annualNetIncome,annualDilutedEPS"


async def fetch_fundamentals(db: DB, symbol: str, max_age: int = 86400) -> dict:
    """Valuation and growth figures from Yahoo's timeseries endpoint, cached for a day."""
    key = f"fund:{symbol}"
    cached = db.get(key)
    if cached and time.time() - cached.get("_at", 0) < max_age:
        return cached
    now = int(time.time())
    out: dict = {"_at": now}
    try:
        async with httpx.AsyncClient() as client:
            data = await _get_json(
                client,
                f"{BASE}/ws/fundamentals-timeseries/v1/finance/timeseries/{quote(symbol)}",
                {"type": FUND_TYPES, "period1": now - 6 * 365 * 86400, "period2": now},
            )
        for series in data.get("timeseries", {}).get("result", []):
            name = (series.get("meta", {}).get("type") or [None])[0]
            points = [p for p in series.get(name, []) if p and p.get("reportedValue")]
            if name and points:
                out[name] = [
                    {"date": p["asOfDate"], "value": p["reportedValue"]["raw"]} for p in points
                ]
    except RateLimited:
        return cached or {}  # paused: try again later instead of remembering "no data" for a day
    except YahooError as e:
        log.info("no fundamentals for %s: %s", symbol, e)
    db.set(key, out)
    return out
