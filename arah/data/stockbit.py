"""Realtime IDX prices from the owner's own Stockbit session, read-only.

The session API that serves charts also places orders and moves cash, so every request goes
through an allowlist of read-only paths before a token is touched. The tokens follow the
rules documented by the idx project (github.com/fzn0x/idx, docs/stockbit.md): the access token
lasts about a day, the refresh token about a week, and every refresh replaces both, so this
process must be the only one using the session.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from urllib.parse import unquote

import httpx

from ..db import DB
from . import relay

log = logging.getLogger("arah.stockbit")
EXODUS = relay.base("stockbit", "https://exodus.stockbit.com")
READ_PREFIXES = ("/charts/", "/company-price-feed/")
PACE = 1.0
TTL = 5.0
INDEX_CODES = {"IHSG": "IHSG", "LQ45": "LQ45"}


class StockbitError(Exception):
    pass


def _is_jwt(v: object) -> bool:
    if not isinstance(v, str):
        return False
    parts = v.split(".")
    return len(parts) == 3 and parts[0].startswith("eyJ") and all(parts[1:])


def _find_token(v: object, slot: str) -> str | None:
    """A JWT stored under `slot`, either as a bare string or as {"token": ...}, anywhere in the tree."""
    if isinstance(v, dict):
        hit = v.get(slot)
        if _is_jwt(hit):
            return hit
        if isinstance(hit, dict) and _is_jwt(hit.get("token")):
            return hit["token"]
        for child in v.values():
            found = _find_token(child, slot)
            if found:
                return found
    elif isinstance(v, list):
        for child in v:
            found = _find_token(child, slot)
            if found:
                return found
    return None


def parse_session(raw: str) -> dict | None:
    """Accepts the `credentialStorage` cookie value (percent-encoded JSON) or a bare refresh token."""
    raw = (raw or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    for candidate in (unquote(raw), raw):
        try:
            v = json.loads(candidate)
        except ValueError:
            continue
        access = _find_token(v, "access")
        if access:
            return {"access": access, "refresh": _find_token(v, "refresh") or ""}
    return {"access": "", "refresh": raw} if _is_jwt(raw) else None


def token_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        return None


def is_read_path(path: str) -> bool:
    return path.startswith(READ_PREFIXES) and ".." not in path and "%2e" not in path.lower()


class Stockbit:
    def __init__(self, db: DB):
        self.db = db
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._cache: dict[str, tuple[float, dict]] = {}
        self._seed_from_env()

    def _seed_from_env(self) -> None:
        raw = os.environ.get("STOCKBIT_SESSION", "")
        if not raw:
            return
        digest = hashlib.sha256(raw.encode()).hexdigest()
        # A new value in the settings replaces the stored pair; the same value does not, because
        # the stored pair has rotated past it.
        if self.db.get("stockbit_seed") == digest:
            return
        session = parse_session(raw)
        if not session:
            log.warning("STOCKBIT_SESSION is set but holds no token")
            return
        self.db.set("stockbit_session", session)
        self.db.set("stockbit_seed", digest)
        self.db.set("stockbit_error", None)

    @property
    def session(self) -> dict | None:
        s = self.db.get("stockbit_session")
        return s if s and (s.get("access") or s.get("refresh")) else None

    def status(self) -> dict:
        s = self.session
        if not s:
            return {"configured": False}
        now = time.time()
        a, r = token_exp(s.get("access", "")), token_exp(s.get("refresh", ""))
        return {"configured": True, "access_until": a, "refresh_until": r,
                "usable": bool((a and a > now) or (r and r > now)), "error": self.db.get("stockbit_error")}

    async def _refresh(self, client: httpx.AsyncClient, s: dict) -> dict:
        if not s.get("refresh") or (token_exp(s["refresh"]) or 0) < time.time():
            raise StockbitError("the Stockbit session has expired; sign in again and update STOCKBIT_SESSION")
        r = await client.post(f"{EXODUS}/login/refresh", content="{}", headers=self._headers(s["refresh"]))
        if r.status_code == 401 or (r.status_code == 403 and r.headers.get("content-type", "").startswith("application/json")):
            self.db.set("stockbit_error", {"at": int(time.time()), "kind": "refused"})
            raise StockbitError("Stockbit refused the refresh token; sign in again and update STOCKBIT_SESSION")
        if r.status_code != 200:
            raise StockbitError(f"refresh failed with HTTP {r.status_code}")
        body = r.json()
        access = _find_token(body, "access")
        if not access:
            raise StockbitError("refresh answer carried no access token")
        new = {"access": access, "refresh": _find_token(body, "refresh") or s["refresh"]}
        self.db.set("stockbit_session", new)
        return new

    @staticmethod
    def _headers(bearer: str) -> dict:
        return {"authorization": f"Bearer {bearer}", "accept": "application/json",
                "origin": "https://stockbit.com", "referer": "https://stockbit.com/",
                "content-type": "application/json", "user-agent": "Mozilla/5.0", **relay.headers()}

    async def get(self, path: str) -> dict:
        if not is_read_path(path):
            raise StockbitError(f"refused a non read-only path: {path}")
        hit = self._cache.get(path)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
        async with self._lock:
            hit = self._cache.get(path)
            if hit and time.time() - hit[0] < TTL:
                return hit[1]
            s = self.session
            if not s:
                raise StockbitError("no Stockbit session configured")
            wait = PACE - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            async with httpx.AsyncClient(timeout=15) as client:
                if not s.get("access") or (token_exp(s["access"]) or 0) < time.time() + 60:
                    s = await self._refresh(client, s)
                r = await client.get(EXODUS + path, headers=self._headers(s["access"]))
                if r.status_code == 401 or (r.status_code == 403 and r.headers.get("content-type", "").startswith("application/json")):
                    s = await self._refresh(client, s)
                    r = await client.get(EXODUS + path, headers=self._headers(s["access"]))
                self._last = time.monotonic()
            if r.status_code == 403 and relay.ON and r.text.strip() == "forbidden":
                raise StockbitError("the relay refused ARAH's key: ARAH_RELAY_KEY must equal the Worker's RELAY_KEY")
            if r.status_code == 403:
                raise StockbitError("Stockbit's CDN refused this server (HTTP 403); not retried"
                                    + ("" if relay.ON else ". Setting up the Cloudflare relay usually fixes this"))
            if r.status_code != 200:
                raise StockbitError(f"HTTP {r.status_code} for {path.split('?')[0]}")
            data = r.json().get("data") or {}
            self.db.set("stockbit_error", None)
            self._cache[path] = (time.time(), data)
            return data

    @staticmethod
    def code(asset_key: str) -> str:
        return INDEX_CODES.get(asset_key, asset_key)

    async def intraday(self, asset_key: str) -> list[dict]:
        """Today's one-minute candles, realtime during the session."""
        data = await self.get(f"/charts/{self.code(asset_key)}/daily?timeframe=1d&chart_type=PRICE_CHART_TYPE_CANDLE")
        out = []
        for row in data.get("prices") or []:
            close = _num(row.get("value"))
            t = _num(row.get("date"))
            if close is None or not t:
                continue
            out.append({"t": int(t / 1000), "o": _num(row.get("open")) or close, "h": _num(row.get("high")) or close,
                        "l": _num(row.get("low")) or close, "c": close, "v": (_num(row.get("volume")) or 0) * 100})
        return sorted(out, key=lambda b: b["t"])

    async def book(self, asset_key: str) -> dict:
        """Last price, day range and the top of the order book."""
        d = await self.get(f"/company-price-feed/v2/orderbook/companies/{self.code(asset_key)}")

        def side(rows):
            return [{"price": _num(x.get("price")), "lots": int((_num(x.get("volume")) or 0) / 100)}
                    for x in (rows or [])[:5] if _num(x.get("price"))]

        return {"last": _num(d.get("lastprice")), "prev": _num(d.get("previous")), "open": _num(d.get("open")),
                "high": _num(d.get("high")), "low": _num(d.get("low")), "chg_pct": _num(d.get("percentage_change")),
                "bids": side(d.get("bid")), "offers": side(d.get("offer")),
                "foreign_net": _num(d.get("fnet")) if str(d.get("has_foreign_bs")).lower() == "true" else None}


def _num(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None
