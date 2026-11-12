"""Bank rates from BCA's public rates page: what the owner actually pays at the bank."""
from __future__ import annotations

import logging
import re
import time

import httpx

from ..db import DB

log = logging.getLogger("arah.bca")
URL = "https://www.bca.co.id/id/informasi/kurs"
ROW = re.compile(r'data-value-buy="([\d.\-]+)"\s+data-value-sell="([\d.\-]+)"\s+data-text=([A-Z]{3})')
# Asset key -> BCA currency code. BCA quotes the offshore yuan (CNH).
ASSET_CURRENCY = {"USDIDR": "USD", "CNYIDR": "CNH", "SGDIDR": "SGD", "JPYIDR": "JPY", "EURIDR": "EUR"}


def parse(html: str) -> dict[str, dict]:
    """{currency: {buy, sell}} from the e-Rate column, the first of the three numbers in each attribute.

    "buy" is what the bank pays you for foreign currency, "sell" what you pay to get it.
    """
    out: dict[str, dict] = {}
    for buy, sell, cur in ROW.findall(html):
        if cur in out or cur == "IDR":
            continue
        try:
            b, s = float(buy.split("-")[0]), float(sell.split("-")[0])
        except ValueError:
            continue
        # A wrong parse would put money figures on screen, so the pair must look like a real quote.
        if b > 0 and b < s < b * 1.1:
            out[cur] = {"buy": b, "sell": s}
    return out


async def refresh_bca(db: DB, max_age: int = 1500) -> bool:
    cached = db.get("bca_rates") or {}
    if time.time() - cached.get("at", 0) < max_age:
        return True
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(URL, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "id"})
            r.raise_for_status()
        rates = parse(r.text)
    except httpx.HTTPError as e:
        log.warning("BCA rates fetch failed: %s", e)
        return False
    if "USD" not in rates:
        log.warning("BCA rates page had no usable USD row; keeping the previous rates")
        return False
    db.set("bca_rates", {"at": int(time.time()), "rates": rates})
    return True


def bca_rate(db: DB, asset_key: str, max_age: int = 36 * 3600) -> dict | None:
    """Latest BCA e-Rate for an asset, or None when missing or older than a day and a half."""
    cur = ASSET_CURRENCY.get(asset_key)
    data = db.get("bca_rates") or {}
    row = (data.get("rates") or {}).get(cur or "")
    if not row or time.time() - data.get("at", 0) > max_age:
        return None
    return {"currency": cur, "buy": row["buy"], "sell": row["sell"], "mid": (row["buy"] + row["sell"]) / 2, "at": data["at"]}
