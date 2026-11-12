from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx
from defusedxml import ElementTree as ET

from ..db import DB

log = logging.getLogger("arah.news")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def gnews(query: str, lang: str = "en", country: str = "US") -> str:
    ceid = f"{country}:{lang}"
    return f"https://news.google.com/rss/search?q={quote_plus(query + ' when:2d')}&hl={lang}&gl={country}&ceid={ceid}"


# topic -> (country desk, feed urls)
TOPICS: dict[str, tuple[str, list[str]]] = {
    "id_market": ("ID", [
        "https://www.cnbcindonesia.com/market/rss",
        gnews("IHSG OR rupiah OR \"Bank Indonesia\"", "id", "ID"),
    ]),
    "id_politics": ("ID", [
        gnews("pemerintah kebijakan ekonomi OR APBN OR DPR OR menteri keuangan", "id", "ID"),
    ]),
    "us_market": ("US", [gnews("\"Federal Reserve\" OR \"Treasury yields\" OR \"Wall Street\" stocks")]),
    "us_politics": ("US", [gnews("\"White House\" OR Congress tariffs OR sanctions OR budget economy")]),
    "jp": ("JP", [gnews("\"Bank of Japan\" OR yen OR Nikkei")]),
    "sg": ("SG", [gnews("\"Monetary Authority of Singapore\" OR \"Singapore dollar\" OR \"Singapore economy\"", "en", "SG")]),
    "global": ("GLOBAL", [gnews("geopolitics markets oil OR \"trade war\" OR conflict OR OPEC")]),
}


def parse_rss(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        source = (it.findtext("source") or "").strip()
        # Google News appends " - Publisher" to every title.
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        published = 0
        raw = it.findtext("pubDate")
        if raw:
            try:
                published = int(parsedate_to_datetime(raw).timestamp())
            except (TypeError, ValueError):
                published = 0
        items.append({"title": title, "source": source, "url": (it.findtext("link") or "").strip(),
                      "published_at": published})
    return items


async def fetch_feed(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        r = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
        return parse_rss(r.text)
    except httpx.HTTPError as e:
        log.warning("feed failed %s: %s", url[:60], e)
        return []


def _store(db: DB, topic: str, country: str, items: list[dict]) -> int:
    now = int(time.time())
    n = 0
    with db.tx() as c:
        for it in items:
            nid = hashlib.sha1(f"{topic}|{it['title']}".encode()).hexdigest()[:16]
            cur = c.execute(
                "INSERT OR IGNORE INTO news (id, topic, country, title, source, url, published_at, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (nid, topic, country, it["title"], it["source"] or "", it["url"], it["published_at"] or now, now),
            )
            n += cur.rowcount
    return n


async def refresh_news(db: DB, topics: list[str] | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    async with httpx.AsyncClient() as client:
        for topic in topics or list(TOPICS):
            country, urls = TOPICS[topic]
            batches = await asyncio.gather(*(fetch_feed(client, u) for u in urls))
            out[topic] = _store(db, topic, country, [it for b in batches for it in b])
    db.x("DELETE FROM news WHERE fetched_at < ?", (int(time.time()) - 14 * 86400,))
    db.set("news_at", int(time.time()))
    return out


async def refresh_ticker_news(db: DB, key: str, name: str, country: str) -> int:
    if country == "ID":
        url = gnews(f"\"{name}\" OR \"{key}\" saham", "id", "ID")
    else:
        url = gnews(f"\"{name}\" stock")
    async with httpx.AsyncClient() as client:
        items = await fetch_feed(client, url)
    return _store(db, f"t:{key}", country, items)


def headlines(db: DB, topics: list[str], limit: int = 20, max_age_h: int = 48) -> list[dict]:
    marks = ",".join("?" * len(topics))
    rows = db.q(
        f"SELECT id, topic, country, title, source, url, published_at FROM news WHERE topic IN ({marks}) "
        "AND published_at > ? ORDER BY published_at DESC LIMIT ?",
        (*topics, int(time.time()) - max_age_h * 3600, limit),
    )
    return [dict(r) for r in rows]
