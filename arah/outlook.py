"""The plain answer: good, neutral or not good, now and next month, and why.

"Good" is always from the owner's side: a rupiah investor who may expand
abroad. Rising stocks are good. A rising USD/IDR or CNY/IDR means a weaker
rupiah, which is not.
"""
from __future__ import annotations

from .agents import get_insight
from .data.bca import bca_rate
from .db import DB
from .service import build_view
import math

from . import verdict_rules as rules

from .signals import both, fmt_pct, fmt_price, snapshot
from .techniques import techniques
from .universe import BY_KEY, Asset

ABROAD = [("US", "SPX"), ("JP", "N225"), ("SG", "STI"), ("CN", "SSE")]
# Where the market sits for the owner, on the gauge that runs from Menekan to Mendukung.
STATE_NAMES = {"good": ("Mendukung", "Supportive"), "neutral": ("Seimbang", "Balanced"), "bad": ("Menekan", "Pressing")}
NEXT_NAMES = STATE_NAMES
# The owner's rule: a call needs at least a 60% chance on the owner's side to be "Mendukung", and at most
# 40% to be "Menekan". Anything between is a coin toss with a slight lean, shown as "Seimbang".
GOOD_AT, BAD_AT = 0.60, 0.40
# Bumped when the summary's shape or rules change, so a stored one is rebuilt on the next start.
SIMPLE_V = 3


def price_now(snap: dict, asset: Asset) -> int:
    """+1 up, -1 down, 0 when the last month's move is within half of a normal month's swing."""
    m = snap.get("chg1m") or 0.0
    s = snap.get("spark") or []
    days = 30 if asset.days_per_week == 7 else 21
    if len(s) > 21:
        r = [math.log(b / a) for a, b in zip(s, s[1:]) if a > 0 and b > 0]
        mu = sum(r) / len(r)
        sd = math.sqrt(sum((x - mu) ** 2 for x in r) / max(len(r) - 1, 1))
        quiet = 0.5 * sd * math.sqrt(days) * 100
    else:
        quiet = 1.0 if asset.klass == "fx" else 2.0
    if abs(m) < quiet:
        return 0
    return 1 if m > 0 else -1


def gauge_now(snap: dict, asset: Asset) -> float:
    """Where the last month puts the market for the owner: a 10% move in their favour reaches the end."""
    m = (snap.get("chg1m") or 0.0) * (asset.up_is or 1)
    return round(min(0.97, max(0.03, 0.5 + m / 20)), 3)


def favorable(p_up: float, asset: Asset) -> float:
    """Chance that the move is good for the owner: a rise for stocks, a fall for USD/IDR."""
    return p_up if (asset.up_is or 1) > 0 else 1.0 - p_up


def next_state(p_up: float, asset: Asset) -> str:
    pf = round(favorable(p_up, asset), 2)
    return "good" if pf >= GOOD_AT else "bad" if pf <= BAD_AT else "neutral"


def strength(p_up: float) -> dict:
    edge = abs(round(p_up, 2) - 0.5)
    key = "strong" if edge >= 0.10 else "fair" if edge >= 0.05 else "thin"
    return {"key": key, **dict(zip(("id", "en"), {"strong": ("kuat", "strong"), "fair": ("cukup", "fair"),
                                                 "thin": ("tipis", "thin")}[key]))}


def state_of(direction: int, asset: Asset) -> str:
    v = direction * (asset.up_is or 1)
    return "good" if v > 0 else "bad" if v < 0 else "neutral"


def _spark(db: DB, asset: Asset, snaps: dict) -> list[float]:
    snap = snaps.get(asset.key) or snapshot(db, asset) or {}
    return snap.get("spark", [])


HORIZON_WORDS = {"1m": ("sebulan", "next month"), "2m": ("2 bulan", "2 months"), "3m": ("3 bulan", "3 months")}


def card(db: DB, key: str, snaps: dict, horizon: str = "1m") -> dict | None:
    asset = BY_KEY[key]
    ins = get_insight(db, key)
    view = build_view(db, asset, horizon, insight=ins, with_chart=False, snaps=snaps)
    if view.get("error"):
        return None
    snap, f = view["snapshot"], dict(view["forecast"])
    # The conclusion of all techniques replaces the single model's odds and range.
    tech = None
    try:
        tech = techniques(db, asset, horizon)
        f.update({k: tech["conclusion"][k] for k in ("p_up", "q05", "q95")})
    except ValueError:
        pass
    # For currencies the number on screen is the bank's rate, the one the owner actually pays. The
    # forecast keeps its shape and is re-based onto it: Yahoo's rupiah quote jumps about 1% between hours.
    bca = bca_rate(db, key)
    shown = bca["mid"] if bca else snap["price"]
    scale = shown / f["s0"] if f["s0"] else 1.0
    lo_px, hi_px = f["q05"] * scale, f["q95"] * scale
    now_dir = price_now(snap, asset)
    now_state, nxt = state_of(now_dir, asset), next_state(f["p_up"], asset)
    next_dir = 1 if f["p_up"] >= 0.5 else -1
    fx = asset.klass == "fx"
    d = asset.decimals

    def now_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        m = fmt_pct(snap["chg1m"] or 0, lang)
        if fx:
            word = {1: ("Rupiah melemah", "The rupiah weakened"), -1: ("Rupiah menguat", "The rupiah strengthened"),
                    0: ("Rupiah stabil", "The rupiah held steady")}[now_dir][i]
            return f"{word}: {fmt_price(asset, shown, lang)} ({m} {'sebulan' if i == 0 else 'this month'})."
        word = {1: ("Naik", "Up"), -1: ("Turun", "Down"), 0: ("Datar", "Flat")}[now_dir][i]
        return f"{word}: {m} {'dalam sebulan' if i == 0 else 'over the month'}."

    st = strength(f["p_up"])

    def next_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        p = round(f["p_up"] * 100)
        lo, hi = fmt_price(asset, lo_px, lang), fmt_price(asset, hi_px, lang)
        # Always state the chance of the side that was picked, so the number matches the label.
        if fx:
            side = (("rupiah melemah", "the rupiah weakens") if next_dir > 0 else ("rupiah menguat", "the rupiah strengthens"))[i]
        else:
            side = (("naik", "a rise") if next_dir > 0 else ("turun", "a fall"))[i]
        chance = p if next_dir > 0 else 100 - p
        hw = HORIZON_WORDS.get(horizon, HORIZON_WORDS["1m"])
        lead = (f"Peluang {side} {hw[0]} ke depan {chance}% (keyakinan {st['id']})",
                f"Chance of {side} over the {hw[1]}: {chance}% ({st['en']} confidence)")[i]
        rng = (f"Kisaran wajar {lo} sampai {hi}.", f"Reasonable range {lo} to {hi}.")[i]
        if nxt == "neutral":
            rule = (" Di bawah 60%, jadi belum cukup untuk menyebut arah.",
                    " Below 60%, so it is not enough to call either way.")[i]
            return f"{lead}.{rule} {rng}"
        return f"{lead}. {rng}"

    # Lead with a reason that points somewhere; a bare "it moved x%" explains nothing.
    reasons = sorted(view["reasons"], key=lambda r: r["lean"] == 0)[:3]
    return {
        "key": key, "name": asset.name, "name_en": asset.nm("en"), "decimals": d, "klass": asset.klass, "unit": asset.unit, "up_is": asset.up_is,
        "price": shown, "chg1d": snap["chg1d"], "chg1m": snap["chg1m"], "bca": bca,
        # Daily closes for the card's chart, put on the same footing as the price shown above.
        "spark": [round(x * scale, max(d, 2)) for x in _spark(db, asset, snaps)],
        "now": {"state": now_state, "name": dict(zip(("id", "en"), STATE_NAMES[now_state])), "text": both(now_text)},
        "next": {"state": nxt, "name": dict(zip(("id", "en"), NEXT_NAMES[nxt])), "text": both(next_text),
                 "p_up": f["p_up"], "p_good": favorable(f["p_up"], asset), "range": [lo_px, hi_px], "strength": st,
                 "dir": rules.direction(f["p_up"])},
        # Positions on the gauge from Menekan (0) to Mendukung (1), from the owner's side.
        "gauge": {"now": gauge_now(snap, asset), "next": round(favorable(f["p_up"], asset), 3)},
        "why": reasons[0]["text"] if reasons else None,
        "reasons": reasons, "watch": view.get("watch"),
        "from_team": bool(ins), "grade": (view.get("validation") or {}).get("grade"),
        "touch": f["touch"] if key == "USDIDR" and not bca else {},
        "horizon": horizon,
        "votes": tech["votes"] if tech else None,
        "techniques": [{"key": t["key"], "name": t["name"], "vote": t["vote"]} for t in tech["techniques"]] if tech else [],
    }


def _blend(cards: list[dict], which: str) -> str:
    """Next: the average chance across the countries, under the same 60/40 rule as one market.
    Now: good or not good only when a clear majority of the markets agree, otherwise neutral."""
    if which == "next":
        pf = round(sum(c["next"]["p_good"] for c in cards) / len(cards), 2)
        return "good" if pf >= GOOD_AT else "bad" if pf <= BAD_AT else "neutral"
    score = sum({"good": 1, "bad": -1}.get(c["now"]["state"], 0) for c in cards)
    return "good" if score >= 2 else "bad" if score <= -2 else "neutral"


def _abroad_text(lang: str, n: int, ups: int, downs: int) -> str:
    if lang == "id":
        return f"Dari {n} bursa yang dipantau, {ups} naik dan {downs} turun sebulan ini."
    return f"Of {n} markets watched, {ups} rose and {downs} fell this month."


def headline(card_id: dict | None, horizon: str = "1m") -> str | None:
    """One sentence with an actor, from the IHSG card: "Pasar tertekan. ARAH memperkirakan datar dalam 1 bulan." """
    if not card_id:
        return None
    g = card_id["gauge"]["now"]
    now = "Pasar tertekan." if g < 0.4 else "Pasar menguat." if g > 0.6 else "Pasar tenang."
    months = {"1m": "1 bulan", "2m": "2 bulan", "3m": "3 bulan"}.get(horizon, "1 bulan")
    return f"{now} ARAH memperkirakan {card_id['next']['dir']} dalam {months}."


def build_simple(db: DB, snaps: dict, horizon: str = "1m") -> dict:
    out: dict = {"v": SIMPLE_V, "horizon": horizon, "indonesia": card(db, "IHSG", snaps, horizon), "usd": card(db, "USDIDR", snaps, horizon),
                 "cny": card(db, "CNYIDR", snaps, horizon)}
    out["headline"] = headline(out["indonesia"], horizon)
    countries = []
    for country, key in ABROAD:
        c = card(db, key, snaps, horizon)
        if c:
            c["country"] = country
            countries.append(c)
    if countries:
        now_state, next_state = _blend(countries, "now"), _blend(countries, "next")
        ups = sum(1 for c in countries if (c["chg1m"] or 0) > 0)
        downs = len(countries) - ups
        n = len(countries)
        p_good = sum(c["next"]["p_good"] for c in countries) / n
        g_now = sum(c["gauge"]["now"] for c in countries) / n
        out["abroad"] = {
            "now": {"state": now_state, "name": dict(zip(("id", "en"), STATE_NAMES[now_state])),
                    "text": both(lambda lang: _abroad_text(lang, n, ups, downs))},
            "next": {"state": next_state, "name": dict(zip(("id", "en"), NEXT_NAMES[next_state])), "p_good": p_good},
            "gauge": {"now": round(g_now, 3), "next": round(p_good, 3)},
            "countries": countries,
        }
    return out
