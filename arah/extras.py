"""Small owner-facing tools built on the summary: exchange calculator, weekly report card,
answer-change alerts, and the context handed to the "ask" agent."""
from __future__ import annotations

import time

from .data.bca import ASSET_CURRENCY, bca_rate
from .data.calendar import upcoming
from .db import DB
from .outlook import card
from .signals import both, fmt_num
from .universe import HEADLINE_KEYS

CALC_ASSETS = {"USD": "USDIDR", "CNY": "CNYIDR", "SGD": "SGDIDR", "JPY": "JPYIDR", "EUR": "EURIDR"}
CUR_NAMES = {"USD": ("dolar AS", "US dollars"), "CNY": ("yuan", "yuan"), "SGD": ("dolar Singapura", "Singapore dollars"),
             "JPY": ("yen", "yen"), "EUR": ("euro", "euros")}


def calc(db: DB, amount_idr: float, currency: str) -> dict | None:
    """What a rupiah amount buys today and the likely range in a month, with a plain suggestion."""
    key = CALC_ASSETS.get(currency)
    c = card(db, key, {}) if key else None
    if not c:
        return None
    bca = c.get("bca")
    # Buying foreign currency uses the bank's selling rate; without BCA data the market rate stands in.
    rate = bca["sell"] if bca else c["price"]
    spread = rate / c["price"] if c["price"] else 1.0
    lo_rate, hi_rate = c["next"]["range"][0] * spread, c["next"]["range"][1] * spread
    now_amt = amount_idr / rate
    # "bad" for a currency pair means the rupiah is likely to weaken; neutral means no side reaches 60%.
    plan = {"bad": "now", "good": "wait"}.get(c["next"]["state"], "split")
    nid, nen = CUR_NAMES[currency]
    texts = {
        "now": ("Tukar sekarang lebih masuk akal: rupiah lebih mungkin melemah sebulan ke depan.",
                "Exchanging now makes more sense: the rupiah is more likely to weaken over the next month."),
        "wait": ("Tidak perlu buru-buru: rupiah lebih mungkin menguat sebulan ke depan. Tukar bertahap jika butuh segera.",
                 "No need to hurry: the rupiah is more likely to strengthen over the next month. Exchange in parts if you need it soon."),
        "split": ("Tukar bertahap, misalnya separuh sekarang dan separuh bulan depan: arah rupiah belum cukup kuat untuk dipertaruhkan.",
                  "Exchange in parts, for example half now and half next month: the rupiah's direction is too weak to bet on."),
    }[plan]
    return {
        "currency": currency, "asset": key, "amount_idr": amount_idr, "rate": rate, "source": "bca" if bca else "market",
        "rate_at": bca["at"] if bca else None, "now": now_amt,
        # A higher rate buys less, so the low end of the amount comes from the high end of the rate.
        "next_low": amount_idr / hi_rate, "next_high": amount_idr / lo_rate,
        "plan": plan, "advice": {"id": texts[0], "en": texts[1]}, "next": c["next"], "unit": c["unit"],
        "summary": both(lambda lang: (
            f"Rp {fmt_num(amount_idr, 0, lang)} hari ini menjadi sekitar {fmt_num(now_amt, 2, lang)} {nid}."
            if lang == "id" else
            f"Rp {fmt_num(amount_idr, 0, lang)} today buys about {fmt_num(now_amt, 2, lang)} {nen}.")),
    }


def weekly_report(db: DB, days: int = 7) -> dict:
    """How many direction calls that came due in the last week were right, on day and week horizons."""
    since = int(time.time()) - days * 86400
    marks = ",".join("?" * len(HEADLINE_KEYS))
    rows = db.q(
        f"SELECT asset, horizon, p_up, went_up FROM forecasts WHERE scored_at >= ? AND went_up IS NOT NULL "
        f"AND horizon IN ('1d', '1w') AND asset IN ({marks})", (since, *HEADLINE_KEYS))
    right = sum(1 for r in rows if (r["p_up"] >= 0.5) == bool(r["went_up"]))
    return {"days": days, "total": len(rows), "right": right, "wrong": len(rows) - right}


def simple_states(brief: dict | None) -> dict[str, tuple]:
    s = (brief or {}).get("simple") or {}
    out = {}
    for name in ("indonesia", "usd", "cny"):
        if s.get(name):
            out[name] = (s[name]["now"]["state"], s[name]["next"]["state"], s[name]["next"]["strength"]["key"])
    if s.get("abroad"):
        out["abroad"] = (s["abroad"]["now"]["state"], s["abroad"]["next"]["state"], "")
    return out


TITLES = {"indonesia": ("Indonesia", "Indonesia"), "abroad": ("Luar negeri", "Abroad"),
          "usd": ("Rupiah vs dolar AS", "Rupiah vs US dollar"), "cny": ("Rupiah vs yuan", "Rupiah vs yuan")}
WORDS = {"good": ("Bagus", "Good"), "neutral": ("Netral", "Neutral"), "bad": ("Kurang bagus", "Not good")}


def flips(old: dict | None, new: dict, lang: str) -> list[str]:
    """One line per answer that changed since the previous brief, or whose confidence became strong."""
    a, b = simple_states(old), simple_states(new)
    i = 0 if lang == "id" else 1
    lines = []
    for name, (now, nxt, strength) in b.items():
        if name not in a:
            continue
        o_now, o_next, o_strength = a[name]
        title = TITLES[name][i]
        if nxt != o_next:
            lines.append(f"<b>{title}</b>, {('bulan depan', 'next month')[i]}: {WORDS[o_next][i]} → <b>{WORDS[nxt][i]}</b>")
        elif strength == "strong" and o_strength != "strong":
            lines.append(f"<b>{title}</b>, {('bulan depan', 'next month')[i]}: {WORDS[nxt][i]}, "
                         f"{('keyakinan sekarang kuat', 'confidence is now strong')[i]}")
        if now != o_now:
            lines.append(f"<b>{title}</b>, {('sekarang', 'now')[i]}: {WORDS[o_now][i]} → <b>{WORDS[now][i]}</b>")
    return lines


def ask_context(db: DB, brief: dict | None) -> list[str]:
    """Plain English lines describing what ARAH currently knows, for the ask agent to cite."""
    lines: list[str] = []
    b = brief or {}
    if b.get("headline"):
        lines.append(f"World today: {b['headline']['en']}")
    if b.get("outlook"):
        lines.append(f"ARAH's one-month view: {b['outlook']['en']}")
    s = b.get("simple") or {}
    for name, label in (("indonesia", "Indonesia stocks (IHSG)"), ("usd", "Rupiah vs US dollar"), ("cny", "Rupiah vs yuan")):
        c = s.get(name)
        if c:
            lines.append(f"{label}: now {c['now']['state']} ({c['now']['text']['en']}) next month {c['next']['state']} "
                         f"({c['next']['text']['en']})")
            lines += [f"{label} reason: {r['text']['en']}" for r in c["reasons"][:2]]
    for c in (s.get("abroad") or {}).get("countries", []):
        lines.append(f"{c['name_en']} ({c.get('country')}): now {c['now']['state']} ({c['now']['text']['en']}) "
                     f"next month {c['next']['state']} ({c['next']['text']['en']})")
    for code, d in (b.get("countries") or {}).items():
        if d.get("summary"):
            lines.append(f"{code} desk: {d['summary']['en']}")
    if b.get("foreign"):
        lines.append(f"Foreign flow in Indonesian stocks: {b['foreign']['text']['en']}")
    for e in b.get("events") or []:
        when = time.strftime("%Y-%m-%d", time.gmtime(e["at"] + 7 * 3600))
        lines.append(f"Upcoming event {when} ({e['country']}): {e.get('title') or e['what']['en']}")
    for key, cur in ASSET_CURRENCY.items():
        r = bca_rate(db, key)
        if r:
            lines.append(f"BCA bank rate for {cur}: buys at {r['buy']:,.2f}, sells at {r['sell']:,.2f} rupiah")
    return lines[:40]


EVENTS_PER_SIDE = 10


def events_for_brief(db: DB, desks: dict | None) -> list[dict]:
    """Up to 10 coming events for Indonesia and 10 for the rest of the world, soonest first: this week's
    calendar releases plus dated events the desks found in the news."""
    out = [dict(e, source="calendar") for e in upcoming(db)]
    for d in (desks or {}).values():
        out += [dict(e, source="news") for e in d.get("ahead", [])]
    out.sort(key=lambda e: e["at"])
    picked: list[dict] = []
    for side in ("id", "world"):
        picked += [dict(e, side=side) for e in out if (e["country"] == "ID") == (side == "id")][:EVENTS_PER_SIDE]
    return sorted(picked, key=lambda e: e["at"])

