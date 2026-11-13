"""This week's high-impact economic events, with a plain reason each one matters."""
from __future__ import annotations

import logging
import time
from datetime import datetime

import httpx

from ..db import DB

log = logging.getLogger("arah.calendar")
URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
COUNTRY = {"USD": "US", "JPY": "JP", "CNY": "CN", "SGD": "SG", "IDR": "ID", "EUR": "EU", "GBP": "GB"}

# keyword in the event title -> (Indonesian, English) reason it matters to the owner
WHY = [
    (("fomc", "federal funds", "fed chair", "powell"),
     ("Arah suku bunga AS. Bunga AS yang tinggi biasanya menekan rupiah dan saham Indonesia.",
      "The path of US interest rates. High US rates usually weigh on the rupiah and Indonesian stocks.")),
    (("cpi", "pce", "inflation", "ppi"),
     ("Data inflasi. Inflasi yang tinggi membuat bank sentral menahan bunga tinggi lebih lama.",
      "Inflation data. High inflation keeps central banks' rates high for longer.")),
    (("non-farm", "unemployment", "jobless", "employment"),
     ("Data tenaga kerja. Hasil yang kuat mengangkat dolar, hasil yang lemah meringankan tekanan pada rupiah.",
      "Jobs data. A strong result lifts the dollar, a weak one eases pressure on the rupiah.")),
    (("gdp",), ("Pertumbuhan ekonomi. Menunjukkan apakah negara itu sedang kuat atau melambat.",
                "Economic growth. Shows whether that economy is strong or slowing.")),
    (("retail sales", "consumer"), ("Belanja masyarakat. Petunjuk kekuatan permintaan di negara itu.",
                                    "Consumer spending. A read on demand in that country.")),
    (("ecb", "main refinancing", "boe", "official bank rate", "monetary policy"),
     ("Keputusan bunga bank sentral besar. Menggerakkan dolar dan arus dana ke negara berkembang.",
      "A major central bank's rate decision. Moves the dollar and money flows into emerging markets.")),
    (("boj", "bank of japan"), ("Keputusan bank sentral Jepang. Menggerakkan yen dan bursa Tokyo.",
                               "The Bank of Japan's decision. Moves the yen and Tokyo stocks.")),
    (("pboc", "loan prime", "people's bank"), ("Keputusan bunga China. Menggerakkan yuan dan bursa China.",
                                              "China's rate decision. Moves the yuan and Chinese stocks.")),
    (("pmi", "ism", "industrial production", "manufacturing"),
     ("Kesehatan industri. Petunjuk awal arah ekonomi.", "Factory health. An early read on the economy.")),
    (("trade balance", "exports", "imports"), ("Data perdagangan. Berpengaruh pada nilai mata uang negara itu.",
                                              "Trade data. Affects that country's currency.")),
]
DEFAULT_WHY = ("Rilis penting yang bisa menggerakkan pasar negara itu.", "A major release that can move that country's markets.")


def why_for(title: str) -> dict:
    low = title.lower()
    for keys, (i, e) in WHY:
        if any(k in low for k in keys):
            return {"id": i, "en": e}
    return {"id": DEFAULT_WHY[0], "en": DEFAULT_WHY[1]}


def pick(raw: list) -> list[dict]:
    out = []
    for ev in raw if isinstance(raw, list) else []:
        if not isinstance(ev, dict) or ev.get("country") not in COUNTRY:
            continue
        # The feed marks few Asian releases "High", so Japan and China also keep "Medium".
        wanted = ("High",) if ev["country"] in ("USD", "EUR", "GBP") else ("High", "Medium")
        if ev.get("impact") not in wanted:
            continue
        try:
            ts = int(datetime.fromisoformat(str(ev.get("date"))).timestamp())
        except ValueError:
            continue
        title = str(ev.get("title") or "").strip()[:120]
        if title:
            out.append({"at": ts, "country": COUNTRY[ev["country"]], "title": title, "why": why_for(title),
                        "forecast": str(ev.get("forecast") or "")[:20], "previous": str(ev.get("previous") or "")[:20]})
    out.sort(key=lambda e: e["at"])
    merged: list[dict] = []
    for e in out:
        # "CPI m/m" and "Core CPI m/m" land in the same minute and mean the same to a newcomer.
        last = merged[-1] if merged else None
        if last and last["at"] == e["at"] and last["country"] == e["country"] and last["why"] == e["why"]:
            last["title"] = f"{last['title']}, {e['title']}"[:120]
        else:
            merged.append(e)
    return merged


async def refresh_calendar(db: DB, max_age: int = 6 * 3600) -> bool:
    cached = db.get("calendar") or {}
    if time.time() - cached.get("at", 0) < max_age:
        return True
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(URL, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            events = pick(r.json())
    except (httpx.HTTPError, ValueError) as e:
        log.warning("calendar fetch failed: %s", e)
        return False
    db.set("calendar", {"at": int(time.time()), "events": events})
    return True


def upcoming(db: DB, limit: int = 30) -> list[dict]:
    """Events from now on. Empty when the feed is older than two days, so stale dates are never shown."""
    data = db.get("calendar") or {}
    if time.time() - data.get("at", 0) > 2 * 86400:
        return []
    now = time.time()
    return [e for e in data.get("events", []) if e["at"] >= now - 3600][:limit]
