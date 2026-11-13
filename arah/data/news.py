from __future__ import annotations

import asyncio
import hashlib
import logging
import math
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


def site(domains: list[str], query: str, lang: str = "en", country: str = "US") -> str:
    """Google News limited to named publishers: their stories, found through one reliable host."""
    return gnews("(" + " OR ".join(f"site:{d}" for d in domains) + ") " + query, lang, country)


ID_PRESS = ["kontan.co.id", "bisnis.com", "bloombergtechnoz.com", "investor.id", "katadata.co.id", "idxchannel.com",
            "emitennews.com", "cnbcindonesia.com", "detik.com", "kompas.com", "tempo.co", "antaranews.com"]
GLOBAL_PRESS = ["reuters.com", "bloomberg.com", "ft.com", "wsj.com", "cnbc.com", "apnews.com", "marketwatch.com",
                "barrons.com", "nikkei.com", "scmp.com", "straitstimes.com", "economist.com"]

# topic -> (country desk, feed urls). Direct publisher feeds where they publish one, Google News for the rest.
# A feed that stops answering is skipped and reported by `arah selfcheck`; it never stops the others.
TOPICS: dict[str, tuple[str, list[str]]] = {
    "id_market": ("ID", [
        "https://www.cnbcindonesia.com/market/rss",
        "https://www.cnbcindonesia.com/news/rss",
        "https://www.antaranews.com/rss/ekonomi-bursa.xml",
        gnews("IHSG OR rupiah OR \"Bank Indonesia\"", "id", "ID"),
        site(ID_PRESS, "IHSG OR saham OR rupiah OR obligasi", "id", "ID"),
        gnews("\"BI-Rate\" OR \"suku bunga\" OR inflasi OR \"neraca perdagangan\" OR \"cadangan devisa\"", "id", "ID"),
    ]),
    # Market-wrap headlines carry the day's foreign net buy or sell figure in the title itself.
    "id_flow": ("ID", [gnews('asing "beli bersih" OR "jual bersih" saham IHSG', "id", "ID"),
                       gnews('asing "net buy" OR "net sell" IHSG', "id", "ID")]),
    "id_politics": ("ID", [
        "https://www.antaranews.com/rss/ekonomi.xml",
        gnews("pemerintah kebijakan ekonomi OR APBN OR DPR OR menteri keuangan", "id", "ID"),
        gnews("Prabowo OR Danantara OR \"Purbaya\" OR OJK OR BEI kebijakan pasar", "id", "ID"),
    ]),
    # What insiders and the companies themselves do: owners and directors buying or selling, buybacks,
    # rights issues, tender offers, index entries and exits, and analysts changing their calls.
    "id_insider": ("ID", [
        gnews('direksi OR komisaris OR "pemegang saham pengendali" OR "pemegang saham utama" '
              '"membeli saham" OR "menjual saham" OR "tambah kepemilikan" OR "kurangi kepemilikan"', "id", "ID"),
        gnews('"keterbukaan informasi" OR "aksi korporasi" OR buyback OR "rights issue" OR "tender offer" OR "private placement" saham', "id", "ID"),
        gnews('MSCI OR FTSE OR "LQ45" rebalancing OR "masuk indeks" OR "keluar indeks" saham Indonesia', "id", "ID"),
        gnews('"target harga" OR "rekomendasi beli" OR "rekomendasi jual" OR upgrade OR downgrade saham analis', "id", "ID"),
        gnews('IPO OR "pencatatan saham" OR "dividen" BEI emiten', "id", "ID"),
    ]),
    # Commodities that move Indonesian exports, the rupiah and the big IDX sectors.
    "id_commodity": ("ID", [
        gnews('"batu bara" OR nikel OR CPO OR sawit OR timah OR tembaga harga ekspor', "id", "ID"),
    ]),
    "us_market": ("US", [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
        gnews("\"Federal Reserve\" OR \"Treasury yields\" OR \"Wall Street\" stocks"),
        site(GLOBAL_PRESS, "stocks OR Fed OR Treasury OR dollar"),
    ]),
    "us_official": ("US", [
        "https://www.federalreserve.gov/feeds/press_all.xml",
        gnews("\"Fed chair\" OR FOMC OR \"Fed governor\" OR \"CPI report\" OR \"jobs report\" OR \"nonfarm payrolls\""),
    ]),
    "us_politics": ("US", [gnews("\"White House\" OR Congress tariffs OR sanctions OR budget economy")]),
    "us_insider": ("US", [
        gnews('"insider buying" OR "insider selling" OR "Form 4" OR "13F" OR "activist investor" stock'),
        gnews('"raises guidance" OR "cuts guidance" OR "share buyback" OR "earnings beat" OR "earnings miss"'),
        gnews('upgrade OR downgrade "price target" analyst stock'),
    ]),
    "jp": ("JP", [
        "https://asia.nikkei.com/rss/feed/nar",
        gnews("\"Bank of Japan\" OR yen OR Nikkei"),
    ]),
    "sg": ("SG", [
        "https://www.straitstimes.com/news/business/rss.xml",
        gnews("\"Monetary Authority of Singapore\" OR \"Singapore dollar\" OR \"Singapore economy\"", "en", "SG"),
    ]),
    "cn": ("CN", [gnews("China economy OR yuan OR PBOC OR \"Chinese stocks\""),
                  site(["scmp.com", "reuters.com", "bloomberg.com", "caixinglobal.com"], "China economy OR yuan OR stimulus")]),
    "global": ("GLOBAL", [
        "https://www.ecb.europa.eu/rss/press.html",
        "https://oilprice.com/rss/main",
        gnews("geopolitics markets oil OR \"trade war\" OR conflict OR OPEC"),
        site(GLOBAL_PRESS, "emerging markets OR \"risk-off\" OR \"safe haven\" OR gold"),
    ]),
}

# What each country's desk, page and brief read.
COUNTRY_TOPICS = {
    "ID": ["id_market", "id_insider", "id_politics", "id_commodity"],
    "US": ["us_market", "us_official", "us_insider", "us_politics"],
    "JP": ["jp"], "SG": ["sg"], "CN": ["cn"], "GLOBAL": ["global"],
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
    sem = asyncio.Semaphore(6)
    feeds: dict[str, int] = {}

    async def one(client: httpx.AsyncClient, url: str) -> list[dict]:
        async with sem:
            items = await fetch_feed(client, url)
        feeds[url] = len(items)
        return items

    async with httpx.AsyncClient() as client:
        for topic in topics or list(TOPICS):
            country, urls = TOPICS[topic]
            batches = await asyncio.gather(*(one(client, u) for u in urls))
            out[topic] = _store(db, topic, country, [it for b in batches for it in b])
    db.x("DELETE FROM news WHERE fetched_at < ?", (int(time.time()) - 14 * 86400,))
    db.set("news_at", int(time.time()))
    db.set("news_feeds", {"at": int(time.time()), "feeds": feeds})
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


# Ranking: many outlets on one story, a primary or major source, market-moving words, and freshness.
TIER1 = ("reuters", "bloomberg", "financial times", "wall street journal", "wsj", "cnbc", "associated press",
         "ap news", "nikkei", "federal reserve", "european central bank", "bank indonesia", "kontan", "bisnis",
         "investor.id", "katadata", "antara", "idx channel", "idxchannel", "straits times", "south china morning post",
         "scmp", "marketwatch", "barron", "economist", "tempo", "kompas")
MOVERS = ("suku bunga", "bi-rate", "inflasi", "rupiah", "ihsg", "asing", "beli bersih", "jual bersih", "buyback",
          "rights issue", "tender offer", "msci", "ftse", "direksi", "komisaris", "pengendali", "dividen", "ipo",
          "target harga", "downgrade", "upgrade", "tarif", "apbn", "defisit", "rate", "fed", "fomc", "powell",
          "inflation", "cpi", "payrolls", "yields", "tariff", "sanction", "guidance", "insider", "form 4",
          "13f", "earnings", "default", "recession", "stimulus", "opec", "oil", "gold", "yuan", "yen", "pboc", "boj")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "as", "at", "by", "is", "with", "from",
         "yang", "di", "ke", "dan", "dari", "untuk", "ini", "itu", "pada", "dengan", "akan", "jadi", "dalam"}


def _tokens(title: str) -> set[str]:
    word = "".join(ch.lower() if ch.isalnum() else " " for ch in title)
    return {w for w in word.split() if len(w) > 2 and w not in _STOP}


def top_stories(db: DB, topics: list[str], limit: int = 30, max_age_h: int = 48) -> list[dict]:
    """The most important stories, one line per story however many outlets ran it, best first.
    Each carries `outlets` (how many sources ran it) and the freshest headline's link."""
    rows = headlines(db, topics, limit=400, max_age_h=max_age_h)
    stories: list[dict] = []
    for r in rows:  # newest first, so each story keeps its freshest headline
        tok = _tokens(r["title"])
        if not tok:
            continue
        for st in stories:
            inter = len(tok & st["_tok"])
            if inter >= 3 and inter / min(len(tok), len(st["_tok"])) >= 0.6:
                st["_src"].add((r["source"] or r["url"][:40]).lower())
                st["_tok"] |= tok
                break
        else:
            stories.append(dict(r, _tok=set(tok), _src={(r["source"] or r["url"][:40]).lower()}))
    now = time.time()
    for st in stories:
        outlets = len(st["_src"])
        age_h = max(0.0, (now - (st["published_at"] or now)) / 3600)
        low = st["title"].lower()
        st["outlets"] = outlets
        st["score"] = (1.2 * math.log1p(outlets - 1) + (0.6 if any(t in src for src in st["_src"] for t in TIER1) else 0)
                       + 0.5 * min(2, sum(1 for m in MOVERS if m in low)) + 1.0 * math.exp(-age_h / 18))
    stories.sort(key=lambda x: -x["score"])
    # Keep every topic in view: no single topic may take more than half the list.
    out, per = [], {}
    for st in stories:
        if per.get(st["topic"], 0) >= max(3, limit // 2):
            continue
        per[st["topic"]] = per.get(st["topic"], 0) + 1
        out.append({k: v for k, v in st.items() if not k.startswith("_")})
        if len(out) >= limit:
            break
    return out
