"""Assembles the daily brief: where the world is heading, the key assets, and why."""
from __future__ import annotations

import logging
import time

from .agents import WORLD_KEYS, get_insight, run_team
from .config import Settings
from .data.news import headlines
from .db import DB
from .extras import events_for_brief, weekly_report
from .outlook import build_simple
from .service import all_horizons, build_view
from .signals import both, fmt_num, fmt_pct, snapshot
from .universe import BY_KEY, COUNTRIES, HEADLINE_KEYS

log = logging.getLogger("arah.brief")

STANCE_NAMES = {
    "risk_on": {"id": "Berani ambil risiko", "en": "Risk-on"},
    "risk_off": {"id": "Menghindari risiko", "en": "Risk-off"},
    "mixed": {"id": "Campur aduk", "en": "Mixed"},
}


def rule_world(snaps: dict) -> dict:
    """World stance from prices alone, used when the analyst team is unavailable."""
    def chg(key: str, field: str = "chg1d") -> float:
        s = snaps.get(key)
        return (s or {}).get(field) or 0.0

    stocks = [chg(k) for k in ("SPX", "NASDAQ", "N225", "STI", "IHSG") if snaps.get(k)]
    avg = sum(stocks) / len(stocks) if stocks else 0.0
    vix = (snaps.get("VIX") or {}).get("price") or 0.0
    score = avg / 0.7 - chg("VIX") / 10 - chg("DXY") / 0.5 * 0.5
    stance = "risk_on" if score > 0.8 else "risk_off" if score < -0.8 else "mixed"
    up = sum(1 for x in stocks if x > 0)
    points = [{"text": both(lambda lang: (
        f"{up} dari {len(stocks)} bursa utama naik pada sesi terakhir, rata-rata {fmt_pct(avg)}."
        if lang == "id" else f"{up} of {len(stocks)} major stock markets rose last session, {fmt_pct(avg, 'en')} on average."))}]
    if vix:
        calm = vix < 18
        points.append({"text": both(lambda lang: (
            f"Indeks kecemasan VIX di {vix:.0f}: pasar {'tenang' if calm else 'waspada' if vix < 26 else 'cemas'}."
            if lang == "id" else f"The VIX fear gauge is at {vix:.0f}: markets are {'calm' if calm else 'wary' if vix < 26 else 'anxious'}."))})
    if snaps.get("DXY"):
        d = chg("DXY", "chg1w")
        points.append({"text": both(lambda lang: (
            f"Dolar AS {fmt_pct(d)} seminggu terhadap mata uang utama: {'tekanan' if d > 0 else 'kelonggaran'} bagi rupiah."
            if lang == "id" else
            f"The US dollar is {fmt_pct(d, 'en')} on the week against major currencies: {'pressure on' if d > 0 else 'relief for'} the rupiah."))})
    if snaps.get("US10Y"):
        y = snaps["US10Y"]["price"]
        points.append({"text": both(lambda lang: (
            f"Imbal hasil obligasi AS 10 tahun di {fmt_num(y, 2)}%." if lang == "id"
            else f"The US 10-year bond yield is at {y:.2f}%."))})
    summary = {
        "risk_on": both(lambda lang: "Pasar global sedang berani mengambil risiko: saham naik dan kecemasan mereda." if lang == "id"
                        else "Global markets are taking risk: stocks are up and anxiety is fading."),
        "risk_off": both(lambda lang: "Pasar global sedang menghindari risiko: saham tertekan dan investor mencari tempat aman." if lang == "id"
                         else "Global markets are avoiding risk: stocks are under pressure and investors want safety."),
        "mixed": both(lambda lang: "Pasar global bergerak campur aduk, belum ada arah bersama yang jelas." if lang == "id"
                      else "Global markets are mixed, with no clear common direction yet."),
    }[stance]
    return {"stance": stance, "summary": summary, "points": points}


def rule_headline(world: dict, usd: dict | None) -> dict:
    stance = world["stance"]
    d = (usd or {}).get("direction", "flat")

    def make(lang: str) -> str:
        if lang == "id":
            w = {"risk_on": "Dunia sedang berani ambil risiko", "risk_off": "Dunia sedang menghindari risiko",
                 "mixed": "Arah dunia masih campur aduk"}[stance]
            u = {"up": "dolar cenderung menguat terhadap rupiah", "down": "rupiah cenderung menguat terhadap dolar",
                 "flat": "arah dolar terhadap rupiah belum jelas"}[d]
            return f"{w}; {u} minggu ini."
        w = {"risk_on": "The world is taking risk", "risk_off": "The world is avoiding risk",
             "mixed": "The world is sending mixed signals"}[stance]
        u = {"up": "the dollar leans stronger against the rupiah", "down": "the rupiah leans stronger against the dollar",
             "flat": "the dollar's path against the rupiah is unclear"}[d]
        return f"{w}; {u} this week."

    return both(make)


async def build_brief(db: DB, settings: Settings, slot: str = "manual", use_llm: bool = True) -> dict:
    snaps: dict = {k: snapshot(db, BY_KEY[k]) for k in WORLD_KEYS}
    team = None
    if use_llm and settings.llm_enabled:
        try:
            team = await run_team(db, settings)
        except Exception:
            log.exception("analyst team failed; falling back to rules")
    assets = []
    for k in HEADLINE_KEYS:
        a = BY_KEY[k]
        ins = get_insight(db, k)
        view = build_view(db, a, "1w", insight=ins, with_chart=False, snaps=snaps)
        if view.get("error"):
            continue
        view["horizons"] = all_horizons(db, a, ins, snaps)
        view.pop("facts", None)
        assets.append(view)
    world = (team or {}).get("world") or rule_world(snaps)
    world["name"] = STANCE_NAMES[world["stance"]]
    usd = next((v for v in assets if v["key"] == "USDIDR"), None)
    tiles = [{"key": k, "name": BY_KEY[k].name, "name_en": BY_KEY[k].nm("en"), "decimals": BY_KEY[k].decimals, "price": s["price"],
              "chg1d": s["chg1d"], "chg1w": s["chg1w"]} for k in WORLD_KEYS if (s := snaps.get(k))]
    countries = {}
    for c, info in COUNTRIES.items():
        desk = ((team or {}).get("desks") or {}).get(c)
        topics = {"ID": ["id_market", "id_politics"], "US": ["us_market", "us_politics"], "JP": ["jp"], "SG": ["sg"], "CN": ["cn"]}[c]
        countries[c] = {
            "name": {"id": info["name_id"], "en": info["name_en"]},
            "summary": desk["summary"] if desk else None,
            "mood": desk["mood"] if desk else None,
            "events": desk["events"] if desk else [],
            "headlines": [{"title": h["title"], "source": h["source"], "url": h["url"], "at": h["published_at"]}
                          for h in headlines(db, topics, limit=6)],
        }
    recs = db.latest_report("recs") or {"ID": [], "US": [], "screened": {"ID": 0, "US": 0}}
    brief = {
        "at": int(time.time()), "slot": slot,
        "mode": "team" if team and team.get("world") else "rules",
        "model": (team or {}).get("model"),
        "headline": (team or {}).get("headline") or rule_headline(world, usd),
        "outlook": (team or {}).get("outlook"),
        "simple": build_simple(db, snaps),
        "events": events_for_brief(db, (team or {}).get("desks")),
        "foreign": (((team or {}).get("desks") or {}).get("ID") or {}).get("foreign"),
        "report": weekly_report(db),
        "world": world, "tiles": tiles, "assets": assets, "countries": countries,
        "recs": {c: [{k: r[k] for k in ("key", "name", "price", "decimals", "strengths", "p_up_1m")} for r in recs.get(c, [])[:3]]
                 for c in ("ID", "US")},
        "recs_screened": recs.get("screened"),
    }
    db.save_report("brief", brief)
    return brief
