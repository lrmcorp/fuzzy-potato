"""Today's price, minute by minute, from the fastest source available for each asset.

- Indonesian stocks and indices: the owner's Stockbit session when configured (realtime),
  otherwise Yahoo (about 10 to 15 minutes behind).
- Crypto: Binance's public market-data API (realtime), Yahoo as fallback.
- Everything else: Yahoo one-minute bars.
"""
from __future__ import annotations

import logging
import time

import httpx

from .data.stockbit import Stockbit, StockbitError
from .data.yahoo import YahooError, fetch_chart
from .db import DB
from .universe import BY_KEY, SYNTHETIC, Asset

log = logging.getLogger("arah.live")
BINANCE = "https://data-api.binance.vision/api/v3/klines"
BINANCE_PAIRS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}


class Live:
    def __init__(self, db: DB):
        self.db = db
        self.stockbit = Stockbit(db)
        self._cache: dict[str, tuple[float, dict]] = {}

    def source_for(self, asset: Asset) -> str:
        if asset.key in BINANCE_PAIRS:
            return "binance"
        if asset.country == "ID" and asset.klass in ("stock", "index") and self.stockbit.status().get("usable"):
            return "stockbit"
        return "yahoo"

    async def get(self, asset: Asset) -> dict:
        source = self.source_for(asset)
        ttl = 5 if source in ("binance", "stockbit") else 30
        hit = self._cache.get(asset.key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        out = None
        note = None
        if source == "stockbit":
            try:
                out = await self._stockbit(asset)
            except (StockbitError, httpx.HTTPError, ValueError) as e:
                note = {"id": "Stockbit tidak bisa dipakai saat ini, jadi data diambil dari sumber tertunda.",
                        "en": "Stockbit is unavailable right now, so this uses the delayed source."}
                log.warning("stockbit live failed for %s: %s", asset.key, e)
        elif source == "binance":
            try:
                out = await self._binance(asset)
            except (httpx.HTTPError, ValueError, KeyError) as e:
                log.warning("binance live failed for %s: %s", asset.key, e)
        if out is None:
            out = await self._yahoo(asset)
        if note:
            out["note"] = note
        out["at"] = int(time.time())
        out["decimals"] = asset.decimals
        out["unit"] = asset.unit
        self._cache[asset.key] = (time.time(), out)
        return out

    async def _stockbit(self, asset: Asset) -> dict:
        bars = await self.stockbit.intraday(asset.key)
        book = await self.stockbit.book(asset.key)
        last = book.get("last") or (bars[-1]["c"] if bars else None)
        if last is None:
            raise ValueError("no price")
        return {"key": asset.key, "source": "stockbit", "realtime": True, "bars": bars, "last": last,
                "prev": book.get("prev"), "chg_pct": book.get("chg_pct"), "book": book}

    async def _binance(self, asset: Asset) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(BINANCE, params={"symbol": BINANCE_PAIRS[asset.key], "interval": "1m", "limit": 300})
            r.raise_for_status()
            rows = r.json()
            d = await client.get(BINANCE.replace("klines", "ticker/24hr"), params={"symbol": BINANCE_PAIRS[asset.key]})
            d.raise_for_status()
            day = d.json()
        bars = [{"t": int(k[0] / 1000), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]),
                 "v": float(k[5])} for k in rows]
        return {"key": asset.key, "source": "binance", "realtime": True, "bars": bars, "last": bars[-1]["c"],
                "prev": float(day["openPrice"]), "chg_pct": float(day["priceChangePercent"])}

    async def _yahoo(self, asset: Asset) -> dict:
        async with httpx.AsyncClient() as client:
            if asset.key in SYNTHETIC:
                num, den = (BY_KEY[k] for k in SYNTHETIC[asset.key])
                ma, ra = await fetch_chart(client, num.symbol, "1m", "1d")
                mb, rb = await fetch_chart(client, den.symbol, "1m", "1d")
                lookup = {t: c for t, _, _, _, c, _ in rb}
                rows = [(t, c / lookup[t]) for t, _, _, _, c, _ in ra if t in lookup and lookup[t] > 0]
                bars = [{"t": t, "o": c, "h": c, "l": c, "c": c, "v": 0} for t, c in rows]
                pa, pb = ma.get("chartPreviousClose"), mb.get("chartPreviousClose")
                prev = pa / pb if pa and pb else None
            else:
                meta, rows = await fetch_chart(client, asset.symbol, "1m", "1d")
                bars = [{"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0} for t, o, h, l, c, v in rows]
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if not bars:
            raise YahooError(f"no intraday bars for {asset.key}")
        last = bars[-1]["c"]
        delayed = asset.country == "ID" and asset.klass in ("stock", "index")
        return {"key": asset.key, "source": "yahoo", "realtime": False, "bars": bars, "last": last, "prev": prev,
                "chg_pct": (last / prev - 1) * 100 if prev else None,
                "delay_min": 15 if delayed else 1}
