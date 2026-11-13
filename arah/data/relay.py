"""Optional relay (a Cloudflare Worker the owner runs, see deploy/cloudflare/) for Yahoo and Stockbit,
used when those sites refuse this server's address. Off unless ARAH_RELAY_URL and ARAH_RELAY_KEY are set."""
from __future__ import annotations

import os

URL = os.environ.get("ARAH_RELAY_URL", "").strip().rstrip("/")
KEY = os.environ.get("ARAH_RELAY_KEY", "").strip()
ON = bool(URL.startswith("https://") and len(KEY) >= 24)


def base(service: str, direct: str) -> str:
    return f"{URL}/{service}" if ON else direct


def headers() -> dict:
    return {"x-relay-key": KEY} if ON else {}
