"""Notifications to the owner's phone or browser (Web Push), without a third-party account.

The server's signing key pair (VAPID) is made once and kept in the database; browsers that the owner
allows send their subscription here. A subscription the push service reports as gone is dropped.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time

from .db import DB

log = logging.getLogger("arah.push")
CONTACT = "mailto:owner@arah.invalid"  # required by the protocol; no real address is shared


def _keys(db: DB) -> dict:
    keys = db.get("vapid")
    if keys:
        return keys
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    raw = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    keys = {"private_pem": pem, "public": base64.urlsafe_b64encode(raw).decode().rstrip("=")}
    db.set("vapid", keys)
    return keys


def public_key(db: DB) -> str:
    return _keys(db)["public"]


def subscriptions(db: DB) -> list[dict]:
    return db.get("push_subs") or []


def subscribe(db: DB, sub: dict) -> int:
    if not isinstance(sub, dict) or not str(sub.get("endpoint", "")).startswith("https://"):
        raise ValueError("not a push subscription")
    keys = sub.get("keys") or {}
    if not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("subscription has no keys")
    subs = [s for s in subscriptions(db) if s["endpoint"] != sub["endpoint"]]
    subs.append({"endpoint": sub["endpoint"], "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}, "at": int(time.time())})
    db.set("push_subs", subs[-10:])  # one owner, a few devices
    return len(subs[-10:])


def unsubscribe(db: DB, endpoint: str) -> None:
    db.set("push_subs", [s for s in subscriptions(db) if s["endpoint"] != endpoint])


def _send_one(db: DB, sub: dict, payload: str) -> bool:
    from pywebpush import WebPushException, webpush

    try:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload,
                vapid_private_key=_keys(db)["private_pem"], vapid_claims={"sub": CONTACT}, ttl=6 * 3600, timeout=15)
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            unsubscribe(db, sub["endpoint"])
        log.warning("push failed (%s): %s", status, str(e)[:120])
        return False


async def notify(db: DB, title: str, body: str, url: str = "/", tag: str | None = None) -> int:
    """Send to every subscribed device. Returns how many accepted it."""
    subs = subscriptions(db)
    if not subs:
        return 0
    payload = json.dumps({"title": title[:80], "body": body[:240], "url": url, "tag": tag or url})
    sent = await asyncio.gather(*(asyncio.to_thread(_send_one, db, s, payload) for s in subs))
    log.info("push sent to %d of %d devices", sum(sent), len(subs))
    db.set("push_last", {"at": int(time.time()), "title": title[:80], "sent": sum(sent)})
    return sum(sent)
