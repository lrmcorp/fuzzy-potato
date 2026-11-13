"""Stock screen and recommendation cards.

A stock is only recommended when at least three checked strengths hold. If
nothing passes, the list is empty and the UI says so.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time

from .data import sbterm
from .verdict import score as verdict_score
from .data.stockbit import Stockbit
from .data.yahoo import fetch_fundamentals
from .db import DB
from .service import forecast_asset
from .signals import both, fmt_num, fmt_pct, fmt_price, snapshot
from .universe import BENCHMARK, BY_KEY, SECTOR, STOCKS, Asset

log = logging.getLogger("arah.recommend")
# Bumped when the verdict's words or shape change, so stored verdicts are recomputed on the next start.
VERDICTS_V = 3

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


def evaluate(db: DB, asset: Asset, fund: dict, bench: dict | None, sbt: dict | None = None) -> dict | None:
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
    # What brokers and foreign investors are doing, from the owner's Stockbit terminal.
    b, fr = (sbt or {}).get("bandar") or {}, (sbt or {}).get("foreign") or {}
    if b.get("side", 0) > 0:
        strong(0.7 + 0.15 * (b["side"] - 1), f"Bandar detector Stockbit: {b['label']} (broker besar sedang mengakumulasi).",
               f"Stockbit bandar detector: {b['label']} (large brokers are accumulating).")
    elif b.get("side", 0) < 0:
        risk(0.7 + 0.15 * (-b["side"] - 1), f"Bandar detector Stockbit: {b['label']} (broker besar sedang mendistribusi).",
             f"Stockbit bandar detector: {b['label']} (large brokers are distributing).")
    nf = fr.get("net_foreign")
    if nf is not None and s.get("avg_value"):
        # A month's net foreign flow counts when it exceeds 40% of one normal day's trading value.
        if nf > 0.4 * s["avg_value"]:
            strong(0.6, f"Asing beli bersih Rp {nf:,.0f} sebulan terakhir.", f"Foreign investors net bought Rp {nf:,.0f} over the last month.")
        elif nf < -0.4 * s["avg_value"]:
            risk(0.6, f"Asing jual bersih Rp {abs(nf):,.0f} sebulan terakhir.", f"Foreign investors net sold Rp {abs(nf):,.0f} over the last month.")
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
        "currency": "IDR" if asset.country == "ID" else "USD", "sector": SECTOR.get(asset.key),
        # Average value traded per day over the last 20 sessions, and what the smallest buy costs (1 lot = 100 shares
        # on IDX, 1 share in the US).
        "liquidity": s["avg_value"] or None, "lot_size": 100 if asset.country == "ID" else 1,
        "min_capital": p * (100 if asset.country == "ID" else 1), "horizon_days": PICK_DAYS,
    }


async def build_recs(db: DB, top: int = 5) -> dict:
    snaps = {k: snapshot(db, BY_KEY[k]) for k in set(BENCHMARK.values())}
    sem = asyncio.Semaphore(4)

    async def fund(a: Asset) -> dict:
        async with sem:
            return await fetch_fundamentals(db, a.symbol)

    funds = await asyncio.gather(*(fund(a) for a in STOCKS))
    # Broker and foreign flow for Indonesian stocks, when the owner's Stockbit session is set up.
    sbts: dict[str, dict] = {}
    sb = Stockbit(db)
    fetched = 0
    for a in STOCKS:
        if a.country != "ID":
            continue
        cached = {k: (db.get(f"sbt:{k}:{a.key}") or {}) for k in ("bandar", "foreign")}
        fresh = all(time.time() - c.get("_at", 0) < 12 * 3600 for c in cached.values())
        # A burst of terminal requests at startup is what made Stockbit refuse the session once: refresh at
        # most six stocks per run and use what is cached for the rest.
        if not fresh and fetched < 6 and sb.status().get("usable"):
            sbts[a.key] = {"bandar": await sbterm.bandar(db, sb, a.key), "foreign": await sbterm.foreign(db, sb, a.key)}
            fetched += 1
        else:
            sbts[a.key] = {k: c.get("v") for k, c in cached.items()}
    cards: dict[str, dict] = {}
    out: dict = {"at": int(time.time()), "ID": [], "US": [], "screened": {"ID": 0, "US": 0}, "missing": {"ID": 0, "US": 0}}
    for a, fd in zip(STOCKS, funds):
        try:
            card = evaluate(db, a, fd, snaps.get(BENCHMARK[a.country]), sbts.get(a.key))
        except Exception:  # one odd stock must not empty the whole screen
            log.exception("screen failed for %s", a.key)
            card = None
        if not card:
            out["missing"][a.country] += 1
            continue
        out["screened"][a.country] += 1
        cards[a.key] = card
        if card["ok"]:
            out[a.country].append(card)
    # A verdict for every stock, kept with the screen so lists can show it without recomputing.
    verdicts = {}
    for a, fd in zip(STOCKS, funds):
        try:
            _, f1, _ = forecast_asset(db, a, "1m")
            v = verdict_score(db, a, f1.p_up, fd, sbts.get(a.key))
        except (ValueError, KeyError, TypeError):
            v = None
        if v:
            verdicts[a.key] = v
    db.set("verdicts", {"at": int(time.time()), "v": VERDICTS_V, "items": verdicts})
    for c in ("ID", "US"):
        out[c] = sorted(out[c], key=lambda x: -x["score"])[:top]
    # Earlier picks still being tracked that dropped off today's list stay visible, so the owner hears when to
    # hold off or take some off the table instead of the stock silently disappearing.
    shown = {c["key"] for m in ("ID", "US") for c in out[m]}
    for row in db.q("SELECT asset FROM picks_ledger WHERE status='open'"):
        k = row["asset"]
        if k in shown or k not in cards:
            continue
        out[cards[k]["country"]].append({**cards[k], "held": True})
        shown.add(k)
    if not sum(out["screened"].values()):
        # No price history to screen (a download failed): keep the last real screen instead of an empty one.
        prev = db.latest_report("recs")
        if prev and sum((prev.get("screened") or {}).values()):
            log.warning("stock screen had no data; keeping the previous picks")
            return prev
    db.save_report("recs", out)
    log_picks(db, out)
    return out


PICK_DAYS = 31  # a pick's plan is judged over about one month, the forecast horizon behind its targets


def log_picks(db: DB, out: dict) -> int:
    """Record each new pick with its plan; a stock already open in the ledger is not recorded twice."""
    n = 0
    for m in ("ID", "US"):
        for c in out.get(m, []):
            p = c.get("plan")
            if not p or c.get("held") or db.one("SELECT 1 FROM picks_ledger WHERE asset=? AND status='open'", (c["key"],)):
                continue
            db.x("INSERT INTO picks_ledger (asset, made_at, price, stop, t1, t2, horizon_days) VALUES (?,?,?,?,?,?,?)",
                 (c["key"], int(time.time()), c["price"], p["stop"], p["targets"][0], p["targets"][1], PICK_DAYS))
            n += 1
    return n


def score_picks(db: DB) -> int:
    """Close open picks from daily bars after the pick: the stop or target 1, whichever the price reached first
    (a day that touched both counts as the stop, the cautious reading), else the close when the horizon ends."""
    done = 0
    for row in db.q("SELECT * FROM picks_ledger WHERE status='open'"):
        a = BY_KEY.get(row["asset"])
        if not a:
            continue
        bars = db.q("SELECT ts, h, l, c FROM bars WHERE symbol=? AND interval='1d' AND ts>? ORDER BY ts",
                    (a.symbol, row["made_at"] - 86400))
        bars = [b for b in bars if b["ts"] >= row["made_at"] - row["made_at"] % 86400 + 86400]
        status, at, px = None, None, None
        for b in bars:
            if b["l"] <= row["stop"]:
                status, at, px = "stop", b["ts"], row["stop"]
                break
            if b["h"] >= row["t1"]:
                status, at, px = "target", b["ts"], row["t1"]
                break
        if not status and time.time() - row["made_at"] > row["horizon_days"] * 86400 and bars:
            status, at, px = "expired", bars[-1]["ts"], bars[-1]["c"]
        if status:
            db.x("UPDATE picks_ledger SET status=?, closed_at=?, close_price=? WHERE id=?", (status, at, px, row["id"]))
            done += 1
    return done


def picks_summary(db: DB, last: int = 30) -> dict:
    closed = db.q("SELECT asset, made_at, price, status, close_price, closed_at FROM picks_ledger WHERE status!='open' "
                  "ORDER BY closed_at DESC LIMIT ?", (last,))
    open_n = db.one("SELECT COUNT(*) n FROM picks_ledger WHERE status='open'")["n"]
    count = {s: sum(1 for r in closed if r["status"] == s) for s in ("target", "stop", "expired")}
    return {"closed": len(closed), "open": open_n, **count,
            "items": [{"asset": r["asset"], "status": r["status"], "made_at": r["made_at"], "closed_at": r["closed_at"],
                       "ret": (r["close_price"] / r["price"] - 1) * 100 if r["close_price"] else None} for r in closed[:10]]}


PROFILES = ("hati-hati", "sedang", "berani")


def order_picks(cards: list[dict], profile: str | None) -> list[dict]:
    """The owner's answer to "how much swing can you take" orders the list; it never adds or removes a stock.
    hati-hati: smallest loss to the stop first, then the most traded. berani: the largest room to target 1 first.
    sedang or unanswered: ARAH's own score (the screen's order)."""
    def loss(c):
        p = c.get("plan") or {}
        return (c["price"] - p["stop"]) / c["price"] if p.get("stop") and c.get("price") else 1.0

    def room(c):
        p = c.get("plan") or {}
        return (p["targets"][0] / c["price"] - 1) if p.get("targets") and c.get("price") else 0.0

    if profile == "hati-hati":
        return sorted(cards, key=lambda c: (round(loss(c), 3), -(c.get("liquidity") or 0)))
    if profile == "berani":
        return sorted(cards, key=lambda c: -room(c))
    return cards


def recs_ok(db: DB, max_age: int = 20 * 3600) -> bool:
    """A recent screen that actually looked at stocks."""
    r = db.latest_report("recs", max_age=max_age)
    return bool(r and sum((r.get("screened") or {}).values()))
