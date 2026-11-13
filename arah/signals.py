"""Turn price history into plain-language facts.

A fact is one observation with a number behind it. `lean` says which way it
pushes the asset's own price (+1 up, -1 down, 0 context only).
"""
from __future__ import annotations

import numpy as np

from .db import DB
from .data.yahoo import load_bars
from .universe import BENCHMARK, BY_KEY, Asset


MINUS = "\u2212"


def fmt_num(x: float, decimals: int = 2, lang: str = "id") -> str:
    """Indonesian style in both languages, as the owner chose: 5.311,36 and \u22121.234."""
    s = f"{abs(x):,.{decimals}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return (MINUS + s) if x < 0 and s.strip("0,.") else s


def fmt_price(asset, x: float, lang: str = "id") -> str:
    """A price with its unit, e.g. "Rp 18,228" or "$ 7,591.63"; index points have none."""
    unit = asset.unit
    return f"{unit} {fmt_num(x, asset.decimals, lang)}" if unit else fmt_num(x, asset.decimals, lang)


def fmt_pct(x: float, lang: str = "id", signed: bool = True) -> str:
    x = 0.0 if abs(x) < 0.05 else x  # no "-0.0%"
    s = f"{abs(x):.1f}".replace(".", ",")
    sign = (MINUS if x < 0 else "+" if signed and x > 0 else "") if x else ""
    return sign + s + "%"


def both(fn) -> dict:
    return {"id": fn("id"), "en": fn("en")}


def pct_change(c: np.ndarray, bars: int) -> float | None:
    if len(c) <= bars or c[-1 - bars] <= 0:
        return None
    return float(c[-1] / c[-1 - bars] - 1) * 100


def rsi(c: np.ndarray, n: int = 14) -> float | None:
    if len(c) < n + 2:
        return None
    d = np.diff(c[-(n * 6):])
    up, dn = np.maximum(d, 0), np.maximum(-d, 0)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n
        ad = (ad * (n - 1) + dn[i]) / n
    return 100.0 if ad == 0 else float(100 - 100 / (1 + au / ad))


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> float | None:
    if len(c) < n + 1:
        return None
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    return float(tr[-n:].mean())


def snapshot(db: DB, asset: Asset) -> dict | None:
    """Numbers used by facts, screens and the UI tiles. None when there is no usable history."""
    b = load_bars(db, asset.symbol, "1d", 600)
    c = b["c"]
    if len(c) < 30:
        return None
    w = 7 if asset.days_per_week == 7 else 5
    r = np.diff(np.log(c))
    vol20 = float(r[-20:].std()) if len(r) >= 20 else None
    vol250 = float(r[-250:].std()) if len(r) >= 120 else None
    hi52, lo52 = float(c[-252:].max()), float(c[-252:].min())
    out = {
        "key": asset.key,
        "price": float(c[-1]),
        "ts": int(b["ts"][-1]),
        "chg1d": pct_change(c, 1),
        "chg1w": pct_change(c, w),
        "chg1m": pct_change(c, 30 if w == 7 else 21),
        "chg3m": pct_change(c, 90 if w == 7 else 63),
        "chg6m": pct_change(c, 180 if w == 7 else 126),
        "ma20": float(c[-20:].mean()) if len(c) >= 20 else None,
        "ma50": float(c[-50:].mean()) if len(c) >= 50 else None,
        "ma200": float(c[-200:].mean()) if len(c) >= 200 else None,
        "rsi": rsi(c),
        "atr": atr(b["h"], b["l"], c),
        "vol_ratio": (vol20 / vol250) if vol20 and vol250 else None,
        "hi52": hi52,
        "lo52": lo52,
        "from_hi": float(c[-1] / hi52 - 1) * 100,
        "from_lo": float(c[-1] / lo52 - 1) * 100,
        "avg_value": float((b["c"][-20:] * b["v"][-20:]).mean()) if len(c) >= 20 else 0.0,
        "spark": [float(x) for x in c[-60:]],
    }
    # What the price has been doing, as opposed to what it may do next.
    weekly_sd = (vol250 or vol20 or 0.01) * np.sqrt(w) * 100
    z = (out["chg1w"] or 0.0) / (weekly_sd or 1.0)
    out["trend"] = "strong_up" if z > 1.5 else "up" if z > 0.5 else "strong_down" if z < -1.5 else "down" if z < -0.5 else "flat"
    q = db.one("SELECT price, market_ts FROM quotes WHERE symbol=?", (asset.symbol,))
    if q and q["price"]:
        out["live"] = float(q["price"])
        out["live_ts"] = q["market_ts"]
    return out


# Cross-asset drivers: (driver key, change field, sign, weight, texts).
# `sign` is the direction this asset tends to move when the driver rises.
# texts = (id when driver rises, id when it falls, en when it rises, en when it falls).
_USD = [
    ("DXY", "chg1w", 1, 0.9, ("dolar AS menguat terhadap mata uang utama, biasanya rupiah ikut tertekan",
                              "dolar AS melemah terhadap mata uang utama, biasanya memberi napas bagi rupiah",
                              "the US dollar is gaining against major currencies, which usually weighs on the rupiah",
                              "the US dollar is losing ground against major currencies, which usually eases pressure on the rupiah")),
    ("US10Y", "chg1w", 1, 0.6, ("imbal hasil obligasi AS naik, dana cenderung keluar dari negara berkembang",
                                "imbal hasil obligasi AS turun, dana cenderung kembali ke negara berkembang",
                                "US bond yields are rising, which tends to pull money out of emerging markets",
                                "US bond yields are falling, which tends to send money back to emerging markets")),
    ("VIX", "chg1w", 1, 0.5, ("pasar global makin cemas, investor biasanya lari ke dolar",
                              "kecemasan pasar global mereda, minat pada aset negara berkembang membaik",
                              "global markets are more nervous, and investors usually run to the dollar",
                              "global market anxiety is easing, which helps appetite for emerging-market assets")),
    ("IHSG", "chg1w", -1, 0.7, ("IHSG naik, tanda dana asing masih betah di Indonesia",
                                "IHSG turun, tanda dana asing sedang keluar dari Indonesia",
                                "the IHSG is up, a sign foreign money is staying in Indonesia",
                                "the IHSG is down, a sign foreign money is leaving Indonesia")),
    ("BRENT", "chg1w", 1, 0.3, ("minyak naik menambah kebutuhan dolar untuk impor",
                                "minyak turun mengurangi kebutuhan dolar untuk impor",
                                "higher oil adds to the dollars Indonesia needs for imports",
                                "cheaper oil trims the dollars Indonesia needs for imports")),
]
_IDX = [
    ("SPX", "chg1d", 1, 0.6, ("Wall Street menguat semalam, biasanya jadi angin segar untuk pembukaan Asia",
                              "Wall Street melemah semalam, biasanya membebani pembukaan Asia",
                              "Wall Street rose overnight, usually a tailwind for the Asian open",
                              "Wall Street fell overnight, usually a drag on the Asian open")),
    ("USDIDR", "chg1w", -1, 0.9, ("rupiah melemah, biasanya diikuti jual bersih investor asing",
                                  "rupiah menguat, biasanya mengundang beli bersih investor asing",
                                  "the rupiah is weakening, which usually comes with foreign selling",
                                  "the rupiah is strengthening, which usually invites foreign buying")),
    ("VIX", "chg1w", -1, 0.5, ("kecemasan pasar global naik dan menekan saham negara berkembang",
                               "kecemasan pasar global mereda dan menopang saham negara berkembang",
                               "global market anxiety is up and weighs on emerging-market stocks",
                               "global market anxiety is easing and supports emerging-market stocks")),
    ("CPO", "chg1w", 1, 0.3, ("harga sawit naik, positif untuk emiten perkebunan", "harga sawit turun, negatif untuk emiten perkebunan",
                              "palm oil is up, good for plantation companies", "palm oil is down, bad for plantation companies")),
    ("COPPER", "chg1w", 1, 0.2, ("tembaga naik, tanda permintaan industri global sehat", "tembaga turun, tanda permintaan industri global melemah",
                                 "copper is up, a sign of healthy global industrial demand", "copper is down, a sign of weaker global industrial demand")),
]
_US = [
    ("VIX", "chg1w", -1, 0.7, ("kecemasan investor AS meningkat", "kecemasan investor AS mereda",
                               "US investor anxiety is rising", "US investor anxiety is easing")),
    ("US10Y", "chg1w", -1, 0.6, ("imbal hasil obligasi naik dan menekan valuasi saham", "imbal hasil obligasi turun dan menopang valuasi saham",
                                 "bond yields are rising and pressure stock valuations", "bond yields are falling and support stock valuations")),
]
_GOLD = [
    ("DXY", "chg1w", -1, 0.7, ("dolar menguat, biasanya menekan emas", "dolar melemah, biasanya mengangkat emas",
                               "the dollar is stronger, which usually pressures gold", "the dollar is weaker, which usually lifts gold")),
    ("US10Y", "chg1w", -1, 0.6, ("imbal hasil obligasi naik membuat emas kurang menarik", "imbal hasil obligasi turun membuat emas lebih menarik",
                                 "higher bond yields make gold less attractive", "lower bond yields make gold more attractive")),
    ("VIX", "chg1w", 1, 0.4, ("pasar makin cemas, emas dicari sebagai pelindung", "pasar makin tenang, kebutuhan pelindung seperti emas berkurang",
                              "markets are more anxious, so gold is sought as a hedge", "markets are calmer, so there is less need for a hedge like gold")),
]
_CRYPTO = [
    ("NASDAQ", "chg1w", 1, 0.6, ("saham teknologi naik, kripto sering ikut terangkat", "saham teknologi turun, kripto sering ikut tertekan",
                                 "tech stocks are up, and crypto often follows", "tech stocks are down, and crypto often follows")),
    ("DXY", "chg1w", -1, 0.4, ("dolar menguat, biasanya menekan kripto", "dolar melemah, biasanya menopang kripto",
                               "the dollar is stronger, which usually pressures crypto", "the dollar is weaker, which usually supports crypto")),
]
_CROSS = [("USDIDR", "chg1w", 1, 0.9, ("rupiah melemah terhadap dolar, kurs ini ikut terdorong naik",
                                       "rupiah menguat terhadap dolar, kurs ini ikut tertarik turun",
                                       "the rupiah is weaker against the dollar, which pushes this rate up",
                                       "the rupiah is stronger against the dollar, which pulls this rate down"))]
_BENCH = ("pasar secara umum naik dan ikut mengangkat saham ini", "pasar secara umum turun dan ikut menyeret saham ini",
          "the broad market is rising and lifts this stock", "the broad market is falling and drags this stock")
_ASIA = [_IDX[0], _IDX[2]]
DRIVERS: dict[str, list] = {"N225": _ASIA, "STI": _ASIA, "SSE": _ASIA, "CNYIDR": _CROSS, "USDIDR": _USD, "IHSG": _IDX, "LQ45": _IDX, "SPX": _US, "NASDAQ": _US, "GOLD": _GOLD,
                            "BTC": _CRYPTO, "ETH": _CRYPTO, "JPYIDR": _CROSS, "SGDIDR": _CROSS, "EURIDR": _CROSS}

# How large a weekly (or daily) move in the driver has to be before it counts.
DRIVER_SCALE = {"DXY": 0.6, "US10Y": 2.5, "VIX": 12.0, "IHSG": 1.5, "SPX": 0.8, "USDIDR": 0.7, "BRENT": 4.0,
                "CPO": 3.0, "COPPER": 3.0, "NASDAQ": 2.0}


def build_facts(db: DB, asset: Asset, snaps: dict[str, dict] | None = None) -> list[dict]:
    snaps = snaps if snaps is not None else {}

    def snap(key: str) -> dict | None:
        if key not in snaps:
            snaps[key] = snapshot(db, BY_KEY[key])
        return snaps[key]

    s = snap(asset.key)
    if not s:
        return []
    facts: list[dict] = []
    name, name_e = asset.name, asset.nm("en")

    def add(kind: str, lean: int, w: float, id_text: str, en_text: str) -> None:
        facts.append({"id": f"F{len(facts) + 1}", "kind": kind, "lean": lean, "w": round(w, 2),
                      "text": {"id": id_text, "en": en_text}})

    w1, m1 = s["chg1w"], s["chg1m"]
    if w1 is not None and m1 is not None:
        add("move", 0, 0.5,
            f"{name} bergerak {fmt_pct(w1)} dalam seminggu dan {fmt_pct(m1)} dalam sebulan.",
            f"{name_e} moved {fmt_pct(w1, 'en')} over the week and {fmt_pct(m1, 'en')} over the month.")

    pw, pw_e = ("Kurs", "The rate") if asset.klass == "fx" else ("Harga", "Price")
    p, ma20, ma50, ma200 = s["price"], s["ma20"], s["ma50"], s["ma200"]
    if ma20 and ma50:
        if p > ma20 > ma50:
            add("trend", 1, 0.5, f"{pw} berada di atas rata-rata 20 dan 50 hari: tren jangka pendek naik.",
                f"{pw_e} sits above its 20 and 50-day averages: the short-term trend is up.")
        elif p < ma20 < ma50:
            add("trend", -1, 0.5, f"{pw} berada di bawah rata-rata 20 dan 50 hari: tren jangka pendek turun.",
                f"{pw_e} sits below its 20 and 50-day averages: the short-term trend is down.")
        else:
            add("trend", 0, 0.3, f"{pw} berada di antara rata-rata 20 dan 50 hari: tren belum tegas.",
                f"{pw_e} sits between its 20 and 50-day averages: no firm trend.")
    if ma200:
        gap = (p / ma200 - 1) * 100
        if abs(gap) > 3:
            add("trend", 1 if gap > 0 else -1, 0.3,
                f"{pw} {fmt_pct(gap)} dari rata-rata 200 hari (tren jangka panjang {'naik' if gap > 0 else 'turun'}).",
                f"{pw_e} is {fmt_pct(gap, 'en')} from its 200-day average (long-term trend {'up' if gap > 0 else 'down'}).")

    r = s["rsi"]
    if r is not None and (r >= 72 or r <= 28):
        hot = r >= 72
        add("stretch", -1 if hot else 1, 0.4,
            f"RSI {fmt_num(r, 0)}: sudah naik terlalu cepat, rawan jeda atau koreksi." if hot
            else f"RSI {fmt_num(r, 0)}: sudah turun terlalu dalam, sering diikuti pantulan.",
            f"RSI {r:.0f}: it has risen fast and is prone to a pause or pullback." if hot
            else f"RSI {r:.0f}: it has fallen hard, which is often followed by a bounce.")

    vr = s["vol_ratio"]
    if vr and vr >= 1.4:
        add("vol", 0, 0.6,
            f"Pergerakan harian sedang {fmt_num(vr, 1)}x lebih liar dari biasanya, jadi rentang prakiraan melebar.",
            f"Daily swings are {vr:.1f}x wilder than usual, so the forecast range is wider.")
    elif vr and vr <= 0.7:
        add("vol", 0, 0.3, "Pergerakan harian sedang lebih tenang dari biasanya.", "Daily swings are calmer than usual.")

    if s["from_hi"] > -1.5:
        add("level", 0, 0.5, f"{pw} berada di dekat titik tertinggi setahun ({fmt_price(asset, s['hi52'])}).",
            f"{pw_e} is near its one-year high ({fmt_price(asset, s['hi52'], 'en')}).")
    elif s["from_lo"] < 1.5:
        add("level", 0, 0.5, f"{pw} berada di dekat titik terendah setahun ({fmt_price(asset, s['lo52'])}).",
            f"{pw_e} is near its one-year low ({fmt_price(asset, s['lo52'], 'en')}).")

    drivers = list(DRIVERS.get(asset.key, []))
    if asset.klass == "stock":
        bench = BENCHMARK.get(asset.country)
        if bench:
            drivers.append((bench, "chg1w", 1, 0.6, _BENCH))
    for dkey, field, sign, weight, texts in drivers:
        d = snap(dkey)
        if not d or d.get(field) is None:
            continue
        move = d[field]
        scale = DRIVER_SCALE.get(dkey, 2.0) * (0.5 if field == "chg1d" else 1.0)
        if abs(move) < scale * 0.5:
            continue
        strength = min(abs(move) / scale, 2.0) / 2.0
        rising = move > 0
        lean = sign * (1 if rising else -1)
        span_id, span_en = ("sehari", "in a day") if field == "chg1d" else ("seminggu", "in a week")
        dname, dname_e = BY_KEY[dkey].name, BY_KEY[dkey].nm("en")
        add("driver", lean, weight * strength,
            f"{dname} {fmt_pct(move)} {span_id}: {texts[0 if rising else 1]}.",
            f"{dname_e} {fmt_pct(move, 'en')} {span_en}: {texts[2 if rising else 3]}.")
    return facts


def evidence_tilt(facts: list[dict], cap: float = 0.03) -> float:
    """A small probability nudge from the facts. The backtest shows price-only signals carry
    little directional edge, so this stays within a few points."""
    score = sum(f["lean"] * f["w"] for f in facts)
    return float(cap * np.tanh(score / 1.5))
