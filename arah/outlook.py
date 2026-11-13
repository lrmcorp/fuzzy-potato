"""The plain answer: is it good or not, now and next month, and why.

"Good" is always from the owner's side: a rupiah investor who may expand
abroad. Rising stocks are good. A rising USD/IDR or CNY/IDR means a weaker
rupiah, which is not.
"""
from __future__ import annotations

from .agents import get_insight
from .data.bca import bca_rate
from .db import DB
from .service import build_view
from .signals import both, fmt_num, fmt_pct, snapshot
from .techniques import techniques
from .universe import BY_KEY, Asset

ABROAD = [("US", "SPX"), ("JP", "N225"), ("SG", "STI"), ("CN", "SSE")]
STATE_NAMES = {"good": ("Bagus", "Good"), "bad": ("Kurang bagus", "Not good")}
NEXT_NAMES = {"good": ("Bagus", "Good"), "bad": ("Kurang bagus", "Not good")}


def price_now(snap: dict) -> int:
    """+1 or -1, never 0: the direction of the last month, with the 50-day average as tie-break."""
    m = snap.get("chg1m") or 0.0
    if abs(m) >= 0.05:
        return 1 if m > 0 else -1
    return 1 if snap["price"] >= (snap.get("ma50") or snap["price"]) else -1


def price_next(p_up: float) -> int:
    """+1 or -1, never 0. The owner asked for a yes or no, so even a thin edge picks a side;
    `strength` says how thin it is."""
    return 1 if round(p_up, 2) >= 0.50 else -1


def strength(p_up: float) -> dict:
    edge = abs(round(p_up, 2) - 0.5)
    key = "strong" if edge >= 0.10 else "fair" if edge >= 0.05 else "thin"
    return {"key": key, **dict(zip(("id", "en"), {"strong": ("kuat", "strong"), "fair": ("cukup", "fair"),
                                                 "thin": ("tipis", "thin")}[key]))}


def state_of(direction: int, asset: Asset) -> str:
    return "good" if direction * (asset.up_is or 1) > 0 else "bad"


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
    now_dir, next_dir = price_now(snap), price_next(f["p_up"])
    now_state, next_state = state_of(now_dir, asset), state_of(next_dir, asset)
    fx = asset.klass == "fx"
    d = asset.decimals

    def now_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        m = fmt_pct(snap["chg1m"] or 0, lang)
        if fx:
            word = {1: ("Rupiah melemah", "The rupiah weakened"), -1: ("Rupiah menguat", "The rupiah strengthened")}[now_dir][i]
            return f"{word}: {fmt_num(shown, d, lang)} ({m} {'sebulan' if i == 0 else 'this month'})."
        word = {1: ("Naik", "Up"), -1: ("Turun", "Down")}[now_dir][i]
        return f"{word}: {m} {'dalam sebulan' if i == 0 else 'over the month'}."

    st = strength(f["p_up"])

    def next_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        p = round(f["p_up"] * 100)
        lo, hi = fmt_num(lo_px, d, lang), fmt_num(hi_px, d, lang)
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
        return f"{lead}. {rng}"

    # Lead with a reason that points somewhere; a bare "it moved x%" explains nothing.
    reasons = sorted(view["reasons"], key=lambda r: r["lean"] == 0)[:3]
    return {
        "key": key, "name": asset.name, "name_en": asset.nm("en"), "decimals": d, "klass": asset.klass,
        "price": shown, "chg1d": snap["chg1d"], "chg1m": snap["chg1m"], "bca": bca,
        # Daily closes for the card's chart, put on the same footing as the price shown above.
        "spark": [round(x * scale, max(d, 2)) for x in _spark(db, asset, snaps)],
        "now": {"state": now_state, "name": dict(zip(("id", "en"), STATE_NAMES[now_state])), "text": both(now_text)},
        "next": {"state": next_state, "name": dict(zip(("id", "en"), NEXT_NAMES[next_state])), "text": both(next_text),
                 "p_up": f["p_up"], "range": [lo_px, hi_px], "strength": st},
        "why": reasons[0]["text"] if reasons else None,
        "reasons": reasons, "watch": view.get("watch"),
        "from_team": bool(ins), "grade": (view.get("validation") or {}).get("grade"),
        "touch": f["touch"] if key == "USDIDR" and not bca else {},
        "horizon": horizon,
        "votes": tech["votes"] if tech else None,
        "techniques": [{"key": t["key"], "name": t["name"], "vote": t["vote"]} for t in tech["techniques"]] if tech else [],
    }


def _blend(cards: list[dict], which: str) -> str:
    """Majority of the countries; an even split is settled by the average chance or monthly move."""
    score = sum(1 if c[which]["state"] == "good" else -1 for c in cards)
    if score == 0:
        if which == "next":
            score = sum(c["next"]["p_up"] for c in cards) / len(cards) - 0.5
        else:
            score = sum(c["chg1m"] or 0 for c in cards)
    return "good" if score >= 0 else "bad"


def _abroad_text(lang: str, n: int, ups: int, downs: int) -> str:
    if lang == "id":
        return f"Dari {n} bursa yang dipantau, {ups} naik dan {downs} turun sebulan ini."
    return f"Of {n} markets watched, {ups} rose and {downs} fell this month."


def build_simple(db: DB, snaps: dict, horizon: str = "1m") -> dict:
    out: dict = {"horizon": horizon, "indonesia": card(db, "IHSG", snaps, horizon), "usd": card(db, "USDIDR", snaps, horizon),
                 "cny": card(db, "CNYIDR", snaps, horizon)}
    countries = []
    for country, key in ABROAD:
        c = card(db, key, snaps, horizon)
        if c:
            c["country"] = country
            countries.append(c)
    if countries:
        now_state, next_state = _blend(countries, "now"), _blend(countries, "next")
        ups = sum(1 for c in countries if c["now"]["state"] == "good")
        downs = sum(1 for c in countries if c["now"]["state"] == "bad")
        n = len(countries)
        out["abroad"] = {
            "now": {"state": now_state, "name": dict(zip(("id", "en"), STATE_NAMES[now_state])),
                    "text": both(lambda lang: _abroad_text(lang, n, ups, downs))},
            "next": {"state": next_state, "name": dict(zip(("id", "en"), NEXT_NAMES[next_state]))},
            "countries": countries,
        }
    return out
