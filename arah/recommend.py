"""Stock screen and recommendation cards.

A stock is only recommended when at least three checked strengths hold. If
nothing passes, the list is empty and the UI says so.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time

from .data.yahoo import fetch_fundamentals
from .db import DB
from .service import forecast_asset
from .signals import both, fmt_num, fmt_pct, fmt_price, snapshot
from .universe import BENCHMARK, BY_KEY, STOCKS, Asset

log = logging.getLogger("arah.recommend")

# Minimum average daily value traded, in the stock's own currency.
MIN_VALUE = {"ID": 20e9, "US": 50e6}
IDX_TICKS = [(200, 1), (500, 2), (2000, 5), (5000, 10), (math.inf, 25)]


def idx_tick(price: float) -> int:
    return next(t for limit, t in IDX_TICKS if price < limit)


def round_price(asset: Asset, price: float, down: bool = True) -> float:
    if asset.country != "ID":
        return round(price, 2)
    t = idx_tick(price)
    return float(math.floor(price / t) * t if down else math.ceil(price / t) * t)


def _latest(series: list[dict] | None) -> float | None:
    return series[-1]["value"] if series else None


def _growth(series: list[dict] | None) -> float | None:
    if not series or len(series) < 2 or not series[-2]["value"]:
        return None
    return (series[-1]["value"] / series[-2]["value"] - 1) * 100


def evaluate(db: DB, asset: Asset, fund: dict, bench: dict | None) -> dict | None:
    s = snapshot(db, asset)
    if not s or s["ma50"] is None or s["ma200"] is None or s["atr"] is None:
        return None
    try:
        _, f, _ = forecast_asset(db, asset, "1m")
    except ValueError:
        return None
    strengths: list[tuple[float, dict]] = []
    risks: list[tuple[float, dict]] = []

    def strong(w: float, i: str, e: str) -> None:
        strengths.append((w, {"id": i, "en": e}))

    def risk(w: float, i: str, e: str) -> None:
        risks.append((w, {"id": i, "en": e}))

    p, d = s["price"], asset.decimals
    if p > s["ma50"] > s["ma200"]:
        strong(1.0, "Tren naik utuh: harga di atas rata-rata 50 hari, dan rata-rata 50 hari di atas 200 hari.",
               "The uptrend is intact: price above its 50-day average, and the 50-day above the 200-day.")
    elif p < s["ma200"]:
        risk(1.0, "Harga di bawah rata-rata 200 hari: tren jangka panjang masih turun.",
             "Price is below its 200-day average: the long-term trend is still down.")
    if bench and s["chg3m"] is not None and bench.get("chg3m") is not None:
        rel = s["chg3m"] - bench["chg3m"]
        bname = BY_KEY[BENCHMARK[asset.country]].name
        if rel > 4:
            strong(0.9, f"Lebih kuat dari {bname} dalam 3 bulan: {fmt_pct(s['chg3m'])} dibanding {fmt_pct(bench['chg3m'])}.",
                   f"Stronger than the {bname} over 3 months: {fmt_pct(s['chg3m'], 'en')} versus {fmt_pct(bench['chg3m'], 'en')}.")
        elif rel < -8:
            risk(0.6, f"Tertinggal dari {bname} dalam 3 bulan ({fmt_pct(rel)} poin).",
                 f"Lagging the {bname} over 3 months ({fmt_pct(rel, 'en')} points).")
    pe_series, pb = fund.get("trailingPeRatio"), _latest(fund.get("trailingPbRatio"))
    pe = _latest(pe_series)
    if pe and pe_series and len(pe_series) >= 3 and pe > 0:
        avg = sum(x["value"] for x in pe_series) / len(pe_series)
        if pe < 0.85 * avg:
            strong(0.8, f"Valuasi lebih murah dari biasanya: P/E {fmt_num(pe, 1)} dibanding rata-rata {fmt_num(avg, 1)} beberapa tahun terakhir.",
                   f"Cheaper than usual: P/E {pe:.1f} against its {avg:.1f} average of recent years.")
        elif pe > 1.3 * avg:
            risk(0.6, f"Valuasi lebih mahal dari biasanya: P/E {fmt_num(pe, 1)} dibanding rata-rata {fmt_num(avg, 1)}.",
                 f"More expensive than usual: P/E {pe:.1f} against its {avg:.1f} average.")
    g_rev, g_ni = _growth(fund.get("annualTotalRevenue")), _growth(fund.get("annualNetIncome"))
    if g_ni is not None and g_rev is not None and g_ni > 8 and g_rev > 0:
        strong(0.8, f"Laba bersih tahunan terakhir tumbuh {fmt_pct(g_ni)} dan pendapatan {fmt_pct(g_rev)}.",
               f"Latest annual net profit grew {fmt_pct(g_ni, 'en')} and revenue {fmt_pct(g_rev, 'en')}.")
    elif g_ni is not None and g_ni < -10:
        risk(0.8, f"Laba bersih tahunan terakhir turun {fmt_pct(g_ni)}.", f"Latest annual net profit fell {fmt_pct(g_ni, 'en')}.")
    if s["rsi"] is not None:
        if 40 <= s["rsi"] <= 62 and p > s["ma50"]:
            strong(0.5, f"Belum terlalu panas: RSI {fmt_num(s['rsi'], 0)}, masih ada ruang sebelum jenuh beli.",
                   f"Not overheated: RSI {s['rsi']:.0f}, with room before it is overbought.")
        elif s["rsi"] > 72:
            risk(0.7, f"Sudah naik cepat (RSI {fmt_num(s['rsi'], 0)}), rawan koreksi jangka pendek.",
                 f"It has run up fast (RSI {s['rsi']:.0f}) and is prone to a short-term pullback.")
    if s["vol_ratio"] and s["vol_ratio"] < 0.9:
        strong(0.4, "Pergerakan harian lebih tenang dari biasanya, risiko guncangan lebih kecil.",
               "Daily swings are calmer than usual, so shocks are less likely.")
    elif s["vol_ratio"] and s["vol_ratio"] > 1.6:
        risk(0.6, f"Pergerakan harian {fmt_num(s['vol_ratio'], 1)}x lebih liar dari biasanya.",
             f"Daily swings are {s['vol_ratio']:.1f}x wilder than usual.")
    if f.p_up >= 0.53:
        strong(0.5, f"Model memberi peluang naik {f.p_up * 100:.0f}% untuk 1 bulan ke depan.",
               f"The model gives a {f.p_up * 100:.0f}% chance of a rise over the next month.")
    if -12 < s["from_hi"] < -3 and p > s["ma200"]:
        strong(0.4, f"Harga {fmt_pct(s['from_hi'])} dari puncak setahun, jadi ada jarak ke level tertinggi sebelumnya.",
               f"Price is {fmt_pct(s['from_hi'], 'en')} from its one-year high, leaving room to the prior peak.")
    if bench and bench.get("chg1m") is not None and bench["chg1m"] < -6:
        risk(0.9, f"Pasar secara umum sedang turun ({BY_KEY[BENCHMARK[asset.country]].name} {fmt_pct(bench['chg1m'])} sebulan).",
             f"The broad market is falling ({BY_KEY[BENCHMARK[asset.country]].name} {fmt_pct(bench['chg1m'], 'en')} over a month).")

    strengths.sort(key=lambda x: -x[0])
    risks.sort(key=lambda x: -x[0])
    score = sum(w for w, _ in strengths) - 0.8 * sum(w for w, _ in risks)
    liquid = s["avg_value"] >= MIN_VALUE.get(asset.country, 0)
    uptrend = p > s["ma200"]
    ok = len(strengths) >= 3 and liquid and uptrend and score >= 1.6

    entry_hi = round_price(asset, p, down=False)
    entry_lo = round_price(asset, p - 0.6 * s["atr"])
    stop = round_price(asset, min(p - 2.0 * s["atr"], s["ma50"] * 0.99))
    risk_per = max(entry_hi - stop, 1e-9)
    target1 = round_price(asset, entry_hi + 1.5 * risk_per, down=False)
    target2 = round_price(asset, entry_hi + 2.5 * risk_per, down=False)
    why = both(lambda lang: (
        f"Tren jangka panjang masih naik dan harga berada {fmt_pct(p / s['ma50'] * 100 - 100)} dari rata-rata 50 hari, "
        f"dengan batas rugi yang jelas di {fmt_price(asset, stop)}. Jika turun ke batas itu, alasan masuk gugur."
        if lang == "id" else
        f"The long-term trend is still up and price sits {fmt_pct(p / s['ma50'] * 100 - 100, 'en')} from its 50-day average, "
        f"with a clear stop at {fmt_price(asset, stop, 'en')}. If it falls there, the case for entering is void."))
    ext = (p / s["ma50"] - 1) * 100
    if ext > 10:
        risk(0.7, f"Harga sudah {fmt_pct(ext)} di atas rata-rata 50 hari, rawan koreksi sebelum lanjut naik.",
             f"Price is already {fmt_pct(ext, 'en')} above its 50-day average and prone to a pullback before rising further.")
        risks.sort(key=lambda x: -x[0])
    loss = (stop / entry_hi - 1) * 100
    # Always true and specific to this plan, so the card never needs a filler risk.
    risks.append((0.0, {"id": f"Jika batas rugi di {fmt_price(asset, stop)} tersentuh, kerugiannya sekitar {fmt_pct(loss)} dari harga masuk.",
                        "en": f"If the stop at {fmt_price(asset, stop, 'en')} is hit, the loss is about {fmt_pct(loss, 'en')} from the entry price."}))
    return {
        "key": asset.key, "name": asset.name, "country": asset.country, "decimals": d, "unit": asset.unit,
        "price": p, "chg1d": s["chg1d"], "chg1m": s["chg1m"], "score": round(score, 2), "ok": ok,
        "liquid": liquid, "p_up_1m": f.p_up, "range_1m": [f.q05, f.q95],
        "strengths": [t for _, t in strengths[:3]], "risks": [t for _, t in risks[:2]],
        "why": why, "plan": {"entry": [entry_lo, entry_hi], "stop": stop, "targets": [target1, target2],
                             "rr": round((target1 - entry_hi) / risk_per, 1)},
        "pe": pe, "pb": pb, "spark": s["spark"],
    }


async def build_recs(db: DB, top: int = 5) -> dict:
    snaps = {k: snapshot(db, BY_KEY[k]) for k in set(BENCHMARK.values())}
    sem = asyncio.Semaphore(4)

    async def fund(a: Asset) -> dict:
        async with sem:
            return await fetch_fundamentals(db, a.symbol)

    funds = await asyncio.gather(*(fund(a) for a in STOCKS))
    out: dict = {"at": int(time.time()), "ID": [], "US": [], "screened": {"ID": 0, "US": 0}, "missing": {"ID": 0, "US": 0}}
    for a, fd in zip(STOCKS, funds):
        try:
            card = evaluate(db, a, fd, snaps.get(BENCHMARK[a.country]))
        except Exception:  # one odd stock must not empty the whole screen
            log.exception("screen failed for %s", a.key)
            card = None
        if not card:
            out["missing"][a.country] += 1
            continue
        out["screened"][a.country] += 1
        if card["ok"]:
            out[a.country].append(card)
    for c in ("ID", "US"):
        out[c] = sorted(out[c], key=lambda x: -x["score"])[:top]
    if not sum(out["screened"].values()):
        # No price history to screen (a download failed): keep the last real screen instead of an empty one.
        prev = db.latest_report("recs")
        if prev and sum((prev.get("screened") or {}).values()):
            log.warning("stock screen had no data; keeping the previous picks")
            return prev
    db.save_report("recs", out)
    return out


def recs_ok(db: DB, max_age: int = 20 * 3600) -> bool:
    """A recent screen that actually looked at stocks."""
    r = db.latest_report("recs", max_age=max_age)
    return bool(r and sum((r.get("screened") or {}).values()))
