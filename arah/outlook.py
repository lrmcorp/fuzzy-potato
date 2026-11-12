"""The plain answer: is it good or not, now and next month, and why.

"Good" is always from the owner's side: a rupiah investor who may expand
abroad. Rising stocks are good. A rising USD/IDR or CNY/IDR means a weaker
rupiah, which is not.
"""
from __future__ import annotations

from .agents import get_insight
from .db import DB
from .service import build_view
from .signals import both, fmt_num, fmt_pct
from .universe import BY_KEY, Asset

ABROAD = [("US", "SPX"), ("JP", "N225"), ("SG", "STI"), ("CN", "SSE")]
STATE_NAMES = {"good": ("Bagus", "Good"), "neutral": ("Netral", "Neutral"), "bad": ("Kurang bagus", "Not good")}
NEXT_NAMES = {"good": ("Berpotensi bagus", "Likely good"), "neutral": ("Belum jelas", "Unclear"),
              "bad": ("Berisiko", "At risk")}


def price_now(snap: dict) -> int:
    """+1 rising, -1 falling, 0 flat: this month's move and where price sits against its 50-day average."""
    score = 0
    if snap.get("ma50"):
        score += 1 if snap["price"] > snap["ma50"] else -1
    m = snap.get("chg1m")
    if m is not None and snap.get("atr"):
        # A month's move only counts when it is larger than about four typical days.
        typical = snap["atr"] / snap["price"] * 100 * 4
        score += 1 if m > typical else -1 if m < -typical else 0
    return 1 if score >= 2 else -1 if score <= -2 else 0


def price_next(p_up: float) -> int:
    p = round(p_up, 2)  # classify on the number the screen shows
    return 1 if p >= 0.55 else -1 if p <= 0.45 else 0


def state_of(direction: int, asset: Asset) -> str:
    v = direction * asset.up_is
    return "good" if v > 0 else "bad" if v < 0 else "neutral"


def card(db: DB, key: str, snaps: dict) -> dict | None:
    asset = BY_KEY[key]
    ins = get_insight(db, key)
    view = build_view(db, asset, "1m", insight=ins, with_chart=False, snaps=snaps)
    if view.get("error"):
        return None
    snap, f = view["snapshot"], view["forecast"]
    now_dir, next_dir = price_now(snap), price_next(f["p_up"])
    now_state, next_state = state_of(now_dir, asset), state_of(next_dir, asset)
    fx = asset.klass == "fx"
    d = asset.decimals

    def now_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        m = fmt_pct(snap["chg1m"] or 0, lang)
        if fx:
            word = {1: ("Rupiah sedang melemah", "The rupiah is weakening"), -1: ("Rupiah sedang menguat", "The rupiah is strengthening"),
                    0: ("Rupiah relatif stabil", "The rupiah is fairly stable")}[now_dir][i]
            return f"{word}: {fmt_num(snap['price'], d, lang)} ({m} {'sebulan' if i == 0 else 'this month'})."
        word = {1: ("Sedang naik", "Rising"), -1: ("Sedang turun", "Falling"), 0: ("Bergerak mendatar", "Moving sideways")}[now_dir][i]
        return f"{word}: {m} {'dalam sebulan' if i == 0 else 'over the month'}."

    def next_text(lang: str) -> str:
        i = 0 if lang == "id" else 1
        p = f["p_up"] * 100
        lo, hi = fmt_num(f["q05"], d, lang), fmt_num(f["q95"], d, lang)
        if fx:
            # For a currency pair the chance that matters to the owner is the rupiah getting weaker.
            lead = (f"Peluang rupiah melemah sebulan ke depan {p:.0f}%", f"Chance the rupiah weakens over the next month: {p:.0f}%")[i]
        else:
            lead = (f"Peluang naik sebulan ke depan {p:.0f}%", f"Chance of a rise over the next month: {p:.0f}%")[i]
        even = ("hampir seimbang", "close to even")[i] if next_dir == 0 else ""
        rng = (f"Kisaran wajar {lo} sampai {hi}.", f"Reasonable range {lo} to {hi}.")[i]
        return f"{lead}{', ' + even if even else ''}. {rng}"

    # Lead with a reason that points somewhere; a bare "it moved x%" explains nothing.
    reasons = sorted(view["reasons"], key=lambda r: r["lean"] == 0)[:3]
    return {
        "key": key, "name": asset.name, "name_en": asset.nm("en"), "decimals": d, "klass": asset.klass,
        "price": snap["price"], "chg1m": snap["chg1m"],
        "now": {"state": now_state, "name": dict(zip(("id", "en"), STATE_NAMES[now_state])), "text": both(now_text)},
        "next": {"state": next_state, "name": dict(zip(("id", "en"), NEXT_NAMES[next_state])), "text": both(next_text),
                 "p_up": f["p_up"], "range": [f["q05"], f["q95"]]},
        "why": reasons[0]["text"] if reasons else None,
        "reasons": reasons, "watch": view.get("watch"),
        "from_team": bool(ins), "grade": (view.get("validation") or {}).get("grade"),
        "touch": f["touch"] if key == "USDIDR" else {},
    }


def _blend(cards: list[dict], which: str) -> str:
    score = sum({"good": 1, "neutral": 0, "bad": -1}[c[which]["state"]] for c in cards)
    half = len(cards) / 2
    return "good" if score >= half else "bad" if score <= -half else "neutral"


def _abroad_text(lang: str, n: int, ups: int, downs: int) -> str:
    if ups == 0 and downs == 0:
        return (f"Keempat bursa yang dipantau bergerak mendatar sebulan ini." if lang == "id" and n == 4
                else f"Semua {n} bursa yang dipantau bergerak mendatar sebulan ini." if lang == "id"
                else f"All {n} markets watched moved sideways this month.")
    flat = n - ups - downs
    if lang == "id":
        return f"Dari {n} bursa yang dipantau: {ups} sedang naik, {downs} sedang turun, {flat} mendatar."
    return f"Of {n} markets watched: {ups} rising, {downs} falling, {flat} sideways."


def build_simple(db: DB, snaps: dict) -> dict:
    out: dict = {"indonesia": card(db, "IHSG", snaps), "usd": card(db, "USDIDR", snaps), "cny": card(db, "CNYIDR", snaps)}
    countries = []
    for country, key in ABROAD:
        c = card(db, key, snaps)
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
