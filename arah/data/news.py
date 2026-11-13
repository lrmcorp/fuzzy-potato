from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
import time
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx
from defusedxml import ElementTree as ET

from ..config import news_tiers
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
MOVERS = ("suku bunga", "bi-rate", "inflasi", "rupiah", "ihsg", "asing", "beli bersih", "jual bersih", "buyback",
          "rights issue", "tender offer", "msci", "ftse", "direksi", "komisaris", "pengendali", "dividen", "ipo",
          "target harga", "downgrade", "upgrade", "tarif", "apbn", "defisit", "rate", "fed", "fomc", "powell",
          "inflation", "cpi", "payrolls", "yields", "tariff", "sanction", "guidance", "insider", "form 4",
          "13f", "earnings", "default", "recession", "stimulus", "opec", "oil", "gold", "yuan", "yen", "pboc", "boj")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "as", "at", "by", "is", "with", "from",
         "yang", "di", "ke", "dan", "dari", "untuk", "ini", "itu", "pada", "dengan", "akan", "jadi", "dalam"}


# Phrases first: "suku bunga turun" is good news for stocks although "turun" alone is not.
_IMPACT_PHRASES = {
    1: ("rupiah menguat", "suku bunga turun", "bunga turun", "bi rate turun", "bi-rate turun", "inflasi turun", "inflasi melandai",
        "pangkas suku bunga", "rate cut", "cuts rates", "beli bersih", "net buy", "laba naik", "laba melonjak",
        "dividen", "buyback", "upgrade", "record high", "rekor tertinggi", "all time high"),
    -1: ("rupiah melemah", "suku bunga naik", "bunga naik", "bi rate naik", "inflasi naik", "inflasi melonjak", "rate hike", "raises rates",
         "jual bersih", "net sell", "laba turun", "gagal bayar", "downgrade", "rekor terendah", "keluar dari indeks"),
}
_IMPACT_WORDS = {
    1: ("naik", "menguat", "melonjak", "melesat", "tertinggi", "untung", "surplus", "tumbuh", "ekspansi", "rebound",
        "rally", "rallies", "rise", "rises", "jump", "jumps", "surge", "surges", "gain", "gains", "beat", "beats", "soar", "soars"),
    -1: ("turun", "melemah", "anjlok", "merosot", "ambles", "ambruk", "terendah", "terdepak", "didepak", "rugi", "defisit", "phk", "tarif", "sanksi", "resesi",
         "fall", "falls", "drop", "drops", "plunge", "plunges", "slump", "slumps", "loss", "losses", "miss", "misses",
         "recession", "sanction", "sanctions", "tariff", "tariffs", "default", "layoffs"),
}


def impact(title: str) -> str:
    """Positif, negatif or netral for investors, from the headline's words. A rule, not a reading of the article."""
    low = " " + " ".join(_word(title)) + " "
    score = 0
    for side, phrases in _IMPACT_PHRASES.items():
        for p in phrases:
            if f" {p} " in low:
                score += 2 * side  # a phrase is more specific than a single word
                low = low.replace(f" {p} ", " ")
    for side, words in _IMPACT_WORDS.items():
        score += side * sum(1 for w in words if f" {w} " in low)
    return "positif" if score > 0 else "negatif" if score < 0 else "netral"


# Names the press uses for the covered stocks, beside their ticker codes.
TICKER_ALIASES = {
    "BBCA": ("bca", "bank central asia"), "BBRI": ("bri", "bank rakyat indonesia"), "BMRI": ("bank mandiri",),
    "BBNI": ("bni", "bank negara indonesia"), "BRIS": ("bsi", "bank syariah indonesia"), "TLKM": ("telkom",),
    "ASII": ("astra international",), "ADRO": ("adaro", "alamtri"), "ANTM": ("antam", "aneka tambang"), "GOTO": ("goto",),
    "UNVR": ("unilever indonesia",), "ICBP": ("indofood cbp",), "INDF": ("indofood sukses makmur",), "KLBF": ("kalbe",),
    "UNTR": ("united tractors",), "PTBA": ("bukit asam",), "ITMG": ("indo tambangraya",), "MDKA": ("merdeka copper",),
    "INCO": ("vale indonesia",), "AMRT": ("alfamart", "sumber alfaria"), "CPIN": ("charoen pokphand",),
    "PGAS": ("pgn", "perusahaan gas negara"), "SMGR": ("semen indonesia",), "INKP": ("indah kiat",), "BRPT": ("barito pacific",),
    "AMMN": ("amman mineral",), "EXCL": ("xl axiata", "xlsmart"), "ISAT": ("indosat",), "MEDC": ("medco",), "AKRA": ("akr corporindo",),
    "NVDA": ("nvidia",), "AAPL": ("apple",), "MSFT": ("microsoft",), "GOOGL": ("alphabet", "google"), "AMZN": ("amazon",),
    "META": ("meta platforms",), "TSLA": ("tesla",), "AVGO": ("broadcom",), "JPM": ("jpmorgan",), "MA": ("mastercard",),
    "UNH": ("unitedhealth",), "XOM": ("exxon",), "LLY": ("eli lilly",), "JNJ": ("johnson & johnson",), "COST": ("costco",),
    "NFLX": ("netflix",), "AMD": ("amd",), "CRM": ("salesforce",), "ORCL": ("oracle",), "KO": ("coca-cola",),
    "WMT": ("walmart",), "BAC": ("bank of america",),
}


def tickers(title: str) -> list[str]:
    """Covered stocks a headline names, by ticker code (4 letters, written in capitals) or by the name the press uses."""
    raw = set(_word(title, lower=False))
    low = " " + " ".join(_word(title)) + " "
    out = []
    for code, names in TICKER_ALIASES.items():
        if (len(code) >= 4 and code in raw) or any(f" {' '.join(_word(n))} " in low for n in names):
            out.append(code)
    return out[:4]


def _word(text: str, lower: bool = True) -> list[str]:
    t = "".join(ch if ch.isalnum() else " " for ch in (text or ""))
    return (t.lower() if lower else t).split()


# Words that say the same move: "IHSG melonjak 2,66%" and "IHSG naik 2,66 persen" are one story.
_SAME = {**{w: "~up" for w in ("naik", "menguat", "melonjak", "melesat", "rebound", "rises", "rise", "gains", "jumps", "surges")},
         **{w: "~down" for w in ("turun", "melemah", "anjlok", "merosot", "ambles", "falls", "fall", "drops", "slides", "slumps")}}
_NUM = re.compile(r"\d+(?:[.,]\d+)+|\d{3,}")


def _tokens(title: str) -> set[str]:
    # Precise numbers stay whole ("2,66" -> "2.66", "5.250" -> "5.250"); years are left out, they match too much.
    nums = {"#" + n.replace(",", ".") for n in _NUM.findall(title) if not re.fullmatch(r"(19|20)\d\d", n)}
    word = "".join(ch.lower() if ch.isalnum() else " " for ch in _NUM.sub(" ", title))
    return {_SAME.get(w, w) for w in word.split() if len(w) > 2 and w not in _STOP} | nums


def _same_story(a: set[str], b: set[str]) -> bool:
    """Three shared words covering most of the shorter headline, or three shared words one of which is the same
    precise number (a percentage or a price): two outlets rarely print the same 2,66% about different things."""
    inter = a & b
    if len(inter) < 3:
        return False
    return len(inter) / min(len(a), len(b)) >= 0.6 or any(t.startswith("#") for t in inter)


def top_stories(db: DB, topics: list[str], limit: int = 30, max_age_h: int = 48) -> list[dict]:
    """The most important stories, one line per story however many outlets ran it, best first.
    Each carries `outlets` (how many sources ran it) and the freshest headline's link."""
    tiers = news_tiers()

    def tier(src: str) -> tuple[int, str] | None:
        """(tier, outlet): the outlet is the list entry that matched, so "ANTARA News" and "ANTARA Foto" are one outlet."""
        s = (src or "").lower()
        for k in (1, 2):
            for t in tiers[k]:
                if t in s:
                    return k, t
        return None

    # Only named outlets on the configured list: an unnamed or unknown source is not shown at all.
    rows = [dict(r, tier=t[0], outlet=t[1]) for r in headlines(db, topics, limit=400, max_age_h=max_age_h) if (t := tier(r["source"]))]
    stories: list[dict] = []
    for r in rows:  # newest first, so each story keeps its freshest headline
        tok = _tokens(r["title"])
        if not tok:
            continue
        for st in stories:
            if _same_story(tok, st["_tok"]):
                st["_src"].add(r["outlet"])
                # The shortest name an outlet used ("Kontan" over "kontan.co.id").
                old = st["_names"].get(r["outlet"])
                if not old or len(r["source"]) < len(old[1]):
                    st["_names"][r["outlet"]] = (r["tier"], r["source"])
                st["tier"] = min(st["tier"], r["tier"])
                st["_tok"] |= tok
                break
        else:
            stories.append(dict(r, _tok=set(tok), _src={r["outlet"]}, _names={r["outlet"]: (r["tier"], r["source"])}))
    now = time.time()
    for st in stories:
        outlets = len(st["_src"])
        age_h = max(0.0, (now - (st["published_at"] or now)) / 3600)
        low = st["title"].lower()
        st["outlets"] = outlets
        # Every outlet that ran the story, the most trusted tier first.
        st["sources"] = [n for _, n in sorted(st["_names"].values(), key=lambda x: (x[0], x[1].lower())) if n]
        st["impact"] = impact(st["title"])
        st["tickers"] = tickers(st["title"])
        st["score"] = (1.2 * math.log1p(outlets - 1) + (0.8 if st["tier"] == 1 else 0.4)
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
