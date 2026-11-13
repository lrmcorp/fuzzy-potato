"""Several independent ways of reading where a price may go over the next one to three months,
each tested on the asset's own history, then combined into one conclusion.

Every technique returns a vote (+1 up, -1 down, 0 no view), how strong it is, the move it
implies, and one plain reason. Techniques that can be replayed on past prices carry their
historical hit rate for this horizon, and only those that beat a coin flip get weight.
"""
from __future__ import annotations

import math
import time

import numpy as np

from .agents import get_insight
from .config import parse_horizon
from .data.yahoo import load_bars
from .db import DB
from .forecast.engine import simulate, tilt_to_drift
from .service import MEAN_SHRINK, validation
from .signals import build_facts, fmt_num, fmt_pct
from .universe import Asset

MAX_COMBINED_TILT = 0.08
BT_TTL = 86400
ANALOG_WINDOW = 20
ANALOG_K = 20

NAMES = {
    "sim": ("Simulasi statistik", "Statistical simulation"),
    "trend": ("Tren", "Trend"),
    "revert": ("Kembali ke rata-rata", "Mean reversion"),
    "season": ("Pola musiman", "Seasonality"),
    "analog": ("Pola historis serupa", "Similar past patterns"),
    "fund": ("Fundamental dan makro", "Fundamentals and macro"),
    "news": ("Berita dan analis AI", "News and AI analysts"),
}


def _ma(c: np.ndarray, n: int) -> np.ndarray:
    """Trailing mean; NaN until n values exist."""
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        cs = np.cumsum(np.insert(c, 0, 0.0))
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def _trend_votes(c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ma50, ma200 = _ma(c, 50), _ma(c, 200)
    up = (c > ma200) & (ma50 > ma200)
    down = (c < ma200) & (ma50 < ma200)
    vote = np.where(up, 1, np.where(down, -1, 0))
    with np.errstate(invalid="ignore", divide="ignore"):
        strength = np.clip(np.abs(c / ma200 - 1) / 0.10, 0, 1)
    vote[np.isnan(ma200)] = 0
    return vote, np.nan_to_num(strength)


def _revert_votes(c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lc = np.log(c)
    ma50 = _ma(c, 50)
    r = np.diff(lc, prepend=lc[0])
    sd = np.sqrt(_ma(r * r, 120))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.log(c / ma50) / (sd * math.sqrt(50))
    z = np.nan_to_num(z)
    vote = np.where(z > 1.5, -1, np.where(z < -1.5, 1, 0))
    return vote, np.clip((np.abs(z) - 1.5) / 1.5 + 0.3, 0, 1) * (vote != 0)


def _season_at(ts: np.ndarray, c: np.ndarray, i: int, span_days: int) -> tuple[int, float, float, int, list]:
    """Returns over the same calendar window in earlier years, using only data before bar i."""
    origin = int(ts[i])
    rets, paths = [], []
    year = 365.25 * 86400
    for k in range(1, 11):
        start = origin - k * year
        if start < ts[0]:
            break
        a = int(np.searchsorted(ts, start))
        b = int(np.searchsorted(ts, start + span_days * 86400))
        if b >= i or b <= a or a >= len(c):
            continue
        rets.append(c[b] / c[a] - 1)
        paths.append(c[a:b + 1] / c[a])
    n = len(rets)
    if n < 5:
        return 0, 0.0, 0.0, n, []
    share = float(np.mean(np.array(rets) > 0))
    med = float(np.median(rets))
    vote = 1 if share >= 0.65 else -1 if share <= 0.35 else 0
    return vote, abs(share - 0.5) * 2, med, n, paths


def _analog_index(c: np.ndarray) -> np.ndarray:
    """Every 20-day log-price path, shifted to start at zero and scaled by its own volatility."""
    lc = np.log(c)
    w = np.lib.stride_tricks.sliding_window_view(lc, ANALOG_WINDOW)
    w = w - w[:, :1]
    sd = np.diff(w, axis=1).std(axis=1, keepdims=True) + 1e-9
    return w / sd


def _analog_at(c: np.ndarray, idx: np.ndarray, i: int, steps: int) -> tuple[int, float, float, list]:
    """The 20 past windows most like the one ending at bar i, and what followed each of them."""
    end = i - ANALOG_WINDOW + 1
    usable = end - steps  # a library window must have its whole future before the origin
    if usable < 200 or end < 0:
        return 0, 0.0, 0.0, []
    target = idx[end]
    lib = idx[:usable]
    d = np.sqrt(((lib - target) ** 2).sum(axis=1))
    near = np.argsort(d)[:ANALOG_K]
    starts = near + ANALOG_WINDOW - 1
    fwd = c[starts + steps] / c[starts] - 1
    share = float(np.mean(fwd > 0))
    vote = 1 if share >= 0.65 else -1 if share <= 0.35 else 0
    paths = [c[s:s + steps + 1] / c[s] for s in starts]
    return vote, abs(share - 0.5) * 2, float(np.median(fwd)), paths


def _backtest(c: np.ndarray, ts: np.ndarray, steps: int, span_days: int) -> dict:
    """Hit rate of each replayable technique's calls on this asset, origins one week apart."""
    tv, _ = _trend_votes(c)
    rv, _ = _revert_votes(c)
    idx = _analog_index(c) if len(c) > 400 else None
    origins = range(max(260, len(c) - 8 * 252), len(c) - steps, 5)
    rec: dict[str, list[tuple[int, bool]]] = {"trend": [], "revert": [], "season": [], "analog": []}
    for i in origins:
        if c[i + steps] == c[i]:
            continue
        up = bool(c[i + steps] > c[i])
        votes = {"trend": tv[i], "revert": rv[i], "season": _season_at(ts, c, i, span_days)[0]}
        if idx is not None:
            votes["analog"] = _analog_at(c, idx, i, steps)[0]
        for k, v in votes.items():
            if v:
                rec[k].append((int(v), up))
    out = {}
    for k, rows in rec.items():
        n = len(rows)
        if not n:
            out[k] = {"n": 0, "n_eff": 0, "hit": None, "chance": None}
            continue
        hit = sum(1 for v, up in rows if (v > 0) == up) / n
        # What a call would score by luck alone, given how often this asset rose and how often the
        # technique said up. Without this, "always up" looks skilled on an index that mostly rose.
        pu = sum(1 for _, up in rows if up) / n
        vu = sum(1 for v, _ in rows if v > 0) / n
        chance = pu * vu + (1 - pu) * (1 - vu)
        # Origins are a week apart but each call spans `steps` bars, so neighbours overlap.
        out[k] = {"n": n, "n_eff": int(n * 5 / max(steps, 5)), "hit": hit, "chance": chance}
    return out


def _weight(hist: dict | None, default: float) -> float:
    """Weight from a technique's edge over luck on this asset: none at chance, full at +15 points."""
    if not hist:
        return default
    if hist.get("n_eff", 0) < 12 or hist.get("hit") is None or hist.get("chance") is None:
        return 0.0
    return float(np.clip((hist["hit"] - hist["chance"]) / 0.15, 0, 1))


def _text(id_: str, en: str) -> dict:
    return {"id": id_, "en": en}


def techniques(db: DB, asset: Asset, horizon: str = "1m") -> dict:
    """All techniques for one asset and a daily horizon (1m, 2m, 3m, or any number of days)."""
    interval, steps, label = parse_horizon(horizon, asset.days_per_week)
    if interval != "1d":
        raise ValueError("techniques work on daily horizons")
    bars = load_bars(db, asset.symbol, "1d", 3000)
    c, ts = bars["c"], bars["ts"]
    if len(c) < 300:
        raise ValueError("not enough history")
    span_days = steps if asset.days_per_week == 7 else int(round(steps * 7 / 5))
    s0, d = float(c[-1]), asset.decimals

    bt_key = f"tech_bt2:{asset.key}:{steps}"
    bt = db.get(bt_key)
    if not bt or time.time() - bt.get("at", 0) > BT_TTL or bt.get("last") != int(ts[-1]):
        bt = _backtest(c, ts, steps, span_days) | {"at": int(time.time()), "last": int(ts[-1])}
        db.set(bt_key, bt)

    out: list[dict] = []

    def add(key: str, vote: int, strength: float, exp_ret: float | None, reason: dict, hist: dict | None,
            path: list[float] | None = None, default_w: float = 0.0) -> None:
        out.append({
            "key": key, "name": dict(zip(("id", "en"), NAMES[key])), "vote": int(vote),
            "strength": round(float(strength), 2), "exp_ret": None if exp_ret is None else round(exp_ret * 100, 2),
            "target": None if exp_ret is None else s0 * (1 + exp_ret), "reason": reason,
            "hist": hist, "weight": round(_weight(hist, default_w), 2), "path": path,
        })

    # 1. Statistical simulation: the model's own odds, already tested by the walk-forward check.
    sim = simulate(c, steps, n_paths=3000, seed=int(ts[-1]) % (2**31), mean_shrink=MEAN_SHRINK)
    val = validation(db, asset, label)
    sim_hist = ({"n": val.get("n", 0), "n_eff": val.get("n", 0), "hit": val.get("hit_rate"), "chance": 0.5}
                if val and val.get("enough") else None)
    p = sim.p_up
    vote = 1 if p >= 0.52 else -1 if p <= 0.48 else 0
    add("sim", vote, min(abs(p - 0.5) * 10, 1), sim.q50 / s0 - 1,
        _text(f"Dari ribuan jalur harga yang disimulasikan, {p * 100:.0f}% berakhir lebih tinggi.",
              f"Of thousands of simulated price paths, {p * 100:.0f}% end higher."), sim_hist)

    # 2. Trend: where price sits against its 50 and 200-day averages; the slope of the last
    #    60 days, halved, gives the line drawn on the chart.
    tv, ts_ = _trend_votes(c)
    slope = float(np.polyfit(np.arange(60), np.log(c[-60:]), 1)[0])
    trend_ret = math.exp(slope * steps * 0.5) - 1
    trend_path = [s0 * math.exp(slope * 0.5 * k) for k in range(steps + 1)]
    ma200 = float(np.mean(c[-200:]))
    if tv[-1] > 0:
        r = _text(f"Harga {fmt_pct((s0 / ma200 - 1) * 100)} di atas rata-rata 200 hari dan rata-rata 50 hari ikut di atasnya: tren naik.",
                  f"Price is {fmt_pct((s0 / ma200 - 1) * 100, 'en')} above its 200-day average with the 50-day above it too: an uptrend.")
    elif tv[-1] < 0:
        r = _text(f"Harga {fmt_pct((s0 / ma200 - 1) * 100)} dari rata-rata 200 hari dan rata-rata 50 hari ikut di bawahnya: tren turun.",
                  f"Price is {fmt_pct((s0 / ma200 - 1) * 100, 'en')} from its 200-day average with the 50-day below it too: a downtrend.")
    else:
        r = _text("Rata-rata 50 dan 200 hari tidak searah: belum ada tren yang tegas.",
                  "The 50 and 200-day averages disagree: no firm trend.")
    add("trend", int(tv[-1]), float(ts_[-1]), trend_ret if tv[-1] else None, r, bt.get("trend"), trend_path)

    # 3. Mean reversion: a price stretched far from its 50-day average tends to drift back.
    rv, rs = _revert_votes(c)
    ma50 = float(np.mean(c[-50:]))
    gap = (s0 / ma50 - 1) * 100
    if rv[-1]:
        r = _text(f"Harga {fmt_pct(gap)} dari rata-rata 50 hari, jauh di luar kebiasaan: cenderung kembali ke {fmt_num(ma50, d)}.",
                  f"Price is {fmt_pct(gap, 'en')} from its 50-day average, far outside its usual range: it tends to drift back toward {fmt_num(ma50, d, 'en')}.")
        exp = ma50 / s0 - 1
    else:
        r = _text(f"Harga {fmt_pct(gap)} dari rata-rata 50 hari, masih dalam batas wajar: tidak ada tarikan balik.",
                  f"Price is {fmt_pct(gap, 'en')} from its 50-day average, within its usual range: no pull back.")
        exp = None
    add("revert", int(rv[-1]), float(rs[-1]), exp, r, bt.get("revert"))

    # 4. Seasonality: how the same calendar window went in each of the last ten years.
    sv, sstr, smed, sn, spaths = _season_at(np.append(ts, ts[-1] + 1), np.append(c, c[-1]), len(c), span_days)
    season_path = None
    if spaths:
        m = min(len(x) for x in spaths)
        avg = np.mean([x[:m] for x in spaths], axis=0)
        season_path = [s0 * float(v) for v in np.interp(np.linspace(0, m - 1, steps + 1), np.arange(m), avg)]
        ups = sum(1 for x in spaths if x[-1] > 1)
        r = _text(f"Di periode yang sama, {ups} dari {sn} tahun terakhir naik (median {fmt_pct(smed * 100)}).",
                  f"In the same weeks, {ups} of the last {sn} years rose (median {fmt_pct(smed * 100, 'en')}).")
    else:
        r = _text("Riwayat kurang dari lima tahun, pola musiman tidak dihitung.", "Less than five years of history; no seasonal read.")
    add("season", sv, sstr, smed if spaths else None, r, bt.get("season"), season_path if sv else season_path)

    # 5. Similar past patterns: the 20 earlier moments whose last month looked most like this one.
    if len(c) > 400:
        av, astr, amed, apaths = _analog_at(c, _analog_index(c), len(c) - 1, steps)
        analog_path = [s0 * float(v) for v in np.median(apaths, axis=0)] if apaths else None
        ups = sum(1 for x in apaths if x[-1] > 1)
        r = _text(f"Dari {len(apaths)} momen masa lalu dengan pola serupa, {ups} berakhir naik dalam rentang waktu yang sama.",
                  f"Of {len(apaths)} past moments with a similar pattern, {ups} ended higher over the same span.")
        add("analog", av, astr, amed if apaths else None, r, bt.get("analog"), analog_path)

    # 6. Fundamentals and macro: valuation and profit growth for stocks, cross-market drivers otherwise.
    fv, fstr, fr = 0, 0.0, _text("Tidak ada data fundamental untuk aset ini.", "No fundamental data for this asset.")
    if asset.klass == "stock":
        fund = db.get(f"fund:{asset.symbol}") or {}
        pe_s = fund.get("trailingPeRatio") or []
        ni = fund.get("annualNetIncome") or []
        score, notes_id, notes_en = 0, [], []
        if len(pe_s) >= 3 and pe_s[-1]["value"] > 0:
            avg = sum(x["value"] for x in pe_s) / len(pe_s)
            ratio = pe_s[-1]["value"] / avg
            if ratio < 0.85:
                score += 1
                notes_id.append(f"P/E {fmt_num(pe_s[-1]['value'], 1)} lebih murah dari rata-ratanya {fmt_num(avg, 1)}")
                notes_en.append(f"P/E {pe_s[-1]['value']:.1f} is cheaper than its {avg:.1f} average")
            elif ratio > 1.3:
                score -= 1
                notes_id.append(f"P/E {fmt_num(pe_s[-1]['value'], 1)} lebih mahal dari rata-ratanya {fmt_num(avg, 1)}")
                notes_en.append(f"P/E {pe_s[-1]['value']:.1f} is dearer than its {avg:.1f} average")
        if len(ni) >= 2 and ni[-2]["value"]:
            g = (ni[-1]["value"] / ni[-2]["value"] - 1) * 100
            if g > 8:
                score += 1
                notes_id.append(f"laba tahunan tumbuh {fmt_pct(g)}")
                notes_en.append(f"annual profit grew {fmt_pct(g, 'en')}")
            elif g < -10:
                score -= 1
                notes_id.append(f"laba tahunan turun {fmt_pct(g)}")
                notes_en.append(f"annual profit fell {fmt_pct(g, 'en')}")
        if notes_id:
            fv = 1 if score > 0 else -1 if score < 0 else 0
            fstr = min(abs(score) / 2, 1)
            fr = _text(notes_id[0][0].upper() + "; ".join(notes_id)[1:] + ".", notes_en[0][0].upper() + "; ".join(notes_en)[1:] + ".")
    else:
        drivers = [f for f in build_facts(db, asset) if f["kind"] == "driver"]
        score = sum(f["lean"] * f["w"] for f in drivers)
        if drivers:
            fv = 1 if score > 0.25 else -1 if score < -0.25 else 0
            fstr = min(abs(score), 1)
            top = max(drivers, key=lambda f: f["w"])
            fr = top["text"]
    add("fund", fv, fstr, None, fr, None, default_w=0.25)

    # 7. News and the AI analysts: the team's one-month lean, else the country desk's mood.
    ins = get_insight(db, asset.key)
    nv, nstr, nr = 0, 0.0, _text("Belum ada analisa berita untuk aset ini.", "No news analysis for this asset yet.")
    if ins:
        tilt = float(ins.get("tilt", {}).get("long", 0.0))
        nv = 1 if tilt >= 0.01 else -1 if tilt <= -0.01 else 0
        nstr = min(abs(tilt) / 0.06, 1)
        lead = next((x for x in ins.get("reasons", []) if x.get("lean") == nv and nv), None) or (ins.get("reasons") or [None])[0]
        if lead:
            nr = lead["text"]
    else:
        brief = db.latest_report("brief") or {}
        desk = (brief.get("countries") or {}).get(asset.country) or {}
        mood = desk.get("mood")
        if mood:
            nv = 1 if mood > 0 else -1
            nstr = min(abs(mood) / 2, 1)
            nr = desk.get("summary") or nr
    add("news", nv, nstr, None, nr, None, default_w=0.25)

    # Conclusion: the simulation's odds, nudged by the other techniques in proportion to their weight.
    push = sum(t["vote"] * t["strength"] * t["weight"] for t in out if t["key"] != "sim")
    tilt = float(np.clip(MAX_COMBINED_TILT * math.tanh(push / 1.5), -MAX_COMBINED_TILT, MAX_COMBINED_TILT))
    final = sim
    if abs(tilt) >= 0.003:
        extra = tilt_to_drift(sim.p_up, sim.p_up + tilt, sim.vol_step, steps)
        final = simulate(c, steps, n_paths=3000, seed=int(ts[-1]) % (2**31), mean_shrink=MEAN_SHRINK, extra_drift_total=extra)
    up = sum(1 for t in out if t["vote"] > 0)
    down = sum(1 for t in out if t["vote"] < 0)
    tested = [t for t in out if t["hist"] and t["hist"].get("n_eff", 0) >= 12]
    return {
        "key": asset.key, "horizon": label, "steps": steps, "s0": s0, "decimals": d,
        "techniques": out,
        "votes": {"up": up, "down": down, "none": len(out) - up - down},
        "tilt": round(tilt, 4),
        "conclusion": {"p_up": final.p_up, "q05": final.q05, "q25": final.q25, "q50": final.q50,
                       "q75": final.q75, "q95": final.q95, "band": final.band},
        "tested": len(tested),
        "history": [{"t": int(t), "c": float(x)} for t, x in zip(ts[-130:], c[-130:])],
    }
