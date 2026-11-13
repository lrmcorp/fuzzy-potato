"""Builds the per-asset view: forecast, verdict, reasons, and what was checked."""
from __future__ import annotations

import json
import time

import numpy as np

from .config import DEFAULT_HORIZONS, parse_horizon
from .data.yahoo import load_bars
from .db import DB
from .forecast.backtest import grade, walk_forward
from .forecast.engine import Forecast, direction_of, simulate, tilt_to_drift
from .signals import both, build_facts, evidence_tilt, fmt_pct, fmt_price, snapshot
from .universe import DEFAULT_LEVELS, Asset

MAX_TILT = 0.08
# Half of the long-run average return is kept as drift; the walk-forward test favoured it
# over none for stocks and gold without hurting the ranges.
MEAN_SHRINK = 0.5
HORIZON_NAMES = {
    "1h": ("1 jam", "1 hour"), "4h": ("4 jam", "4 hours"), "1d": ("1 hari", "1 day"),
    "1w": ("1 minggu", "1 week"), "2w": ("2 minggu", "2 weeks"), "3w": ("3 minggu", "3 weeks"),
    "1m": ("1 bulan", "1 month"),
}
UNIT_NAMES = {"h": ("jam", "hours"), "d": ("hari", "days"), "w": ("minggu", "weeks"), "m": ("bulan", "months")}


def horizon_name(label: str) -> dict:
    if label in HORIZON_NAMES:
        i, e = HORIZON_NAMES[label]
    else:
        ui, ue = UNIT_NAMES[label[-1]]
        i, e = f"{label[:-1]} {ui}", f"{label[:-1]} {ue}"
    return {"id": i, "en": e}


def bucket_of(interval: str, steps: int) -> str:
    if interval == "1h" or steps <= 1:
        return "short"
    return "medium" if steps <= 10 else "long"


def levels_for(db: DB, asset: Asset) -> list[float]:
    levels = db.get("levels", DEFAULT_LEVELS)
    return [float(x) for x in levels.get(asset.key, [])]


def validation(db: DB, asset: Asset, horizon: str, compute: bool = False) -> dict | None:
    """Cached walk-forward result for this asset and horizon."""
    key = f"bt:{asset.key}:{horizon}"
    cached = db.get(key)
    if cached and time.time() - cached.get("at", 0) < 8 * 86400:
        return cached
    if not compute:
        return cached
    interval, steps, _ = parse_horizon(horizon, asset.days_per_week)
    closes = load_bars(db, asset.symbol, interval, 6000)["c"]
    res = walk_forward(closes, steps, n_paths=600, max_origins=200, mean_shrink=MEAN_SHRINK)
    res["grade"] = grade(res)
    res["at"] = int(time.time())
    db.set(key, res)
    return res


def forecast_asset(db: DB, asset: Asset, horizon: str, tilt: float = 0.0, seed: int | None = None,
                   extra_levels: list[float] | None = None) -> tuple[Forecast, Forecast, dict]:
    """Returns (quant forecast, final forecast after tilt, bars meta)."""
    interval, steps, label = parse_horizon(horizon, asset.days_per_week)
    bars = load_bars(db, asset.symbol, interval, 3000)
    closes = bars["c"]
    levels = levels_for(db, asset) + list(extra_levels or [])
    base_ts = int(bars["ts"][-1]) if len(closes) else 0
    if seed is None:
        seed = (base_ts + steps * 7919) % (2**31)
    quant = simulate(closes, steps, levels=levels, seed=seed, mean_shrink=MEAN_SHRINK)
    tilt = float(np.clip(tilt, -MAX_TILT, MAX_TILT))
    final = quant
    if abs(tilt) >= 0.005:
        extra = tilt_to_drift(quant.p_up, quant.p_up + tilt, quant.vol_step, steps)
        final = simulate(closes, steps, levels=levels, seed=seed, extra_drift_total=extra, mean_shrink=MEAN_SHRINK)
    r = np.diff(np.log(closes[-500:]))
    meta = {"interval": interval, "steps": steps, "label": label, "base_ts": base_ts, "bars": len(closes),
            "unchanged_share": float((r == 0).mean()) if len(r) else 0.0}
    return quant, final, meta


def vigilance(asset: Asset, f: Forecast) -> dict | None:
    """Four-step watch level for currency pairs, driven by the nearest level above the price."""
    above = sorted(float(k) for k in f.touch if float(k) > f.s0)
    below = sorted((float(k) for k in f.touch if float(k) <= f.s0), reverse=True)
    if asset.klass != "fx" or not above:
        return None
    level = above[0]
    p = f.touch[f"{level:.10g}"]
    breached = bool(below)
    if p > 0.65:
        code = "bahaya"
    elif p >= 0.40:
        code = "siaga"
    elif p >= 0.20 or f.vol_ratio >= 1.5:
        code = "waspada"
    else:
        code = "aman"
    names = {"aman": ("Aman", "Calm"), "waspada": ("Waspada", "Watch"), "siaga": ("Siaga", "Alert"), "bahaya": ("Bahaya", "Danger")}
    return {"code": code, "name": {"id": names[code][0], "en": names[code][1]}, "level": level, "p": p,
            "above_last": below[0] if breached else None}


TREND_TEXT = {
    "strong_up": ("sedang naik tajam", "has been rising sharply"), "up": ("sedang naik", "has been rising"),
    "flat": ("bergerak mendatar", "has been moving sideways"), "down": ("sedang turun", "has been falling"),
    "strong_down": ("sedang turun tajam", "has been falling sharply"),
}


def conclusion_text(asset: Asset, f: Forecast, label: str, snap: dict | None = None) -> dict:
    """Two sentences: what the price has been doing, then what the model expects."""
    hn = horizon_name(label)
    d = f.direction
    p = f.p_up * 100
    trend, week = (snap or {}).get("trend"), (snap or {}).get("chg1w")

    def make(lang: str) -> str:
        i = 0 if lang == "id" else 1
        lo, hi = fmt_price(asset, f.q05, lang), fmt_price(asset, f.q95, lang)
        past = ""
        if trend and week is not None:
            past = (f"{asset.nm(lang)} {TREND_TEXT[trend][i]} ({fmt_pct(week, lang)} {'seminggu' if lang == 'id' else 'this week'}). ")
        if lang == "id":
            if d == "up":
                head = f"Untuk {hn['id']} ke depan cenderung naik (peluang naik {p:.0f}%)."
            elif d == "down":
                head = f"Untuk {hn['id']} ke depan cenderung turun (peluang turun {100 - p:.0f}%)."
            else:
                head = f"Untuk {hn['id']} ke depan arahnya belum jelas (peluang naik {p:.0f}%, hampir seimbang)."
            return f"{past}{head} Kisaran yang wajar: {lo} sampai {hi}."
        if d == "up":
            head = f"Over the next {hn['en']} it leans up ({p:.0f}% chance of a rise)."
        elif d == "down":
            head = f"Over the next {hn['en']} it leans down ({100 - p:.0f}% chance of a fall)."
        else:
            head = f"Over the next {hn['en']} the direction is unclear ({p:.0f}% chance of a rise, close to even)."
        return f"{past}{head} Reasonable range: {lo} to {hi}."

    return both(make)


def pick_reasons(facts: list[dict], f: Forecast, quant: Forecast, limit: int = 5) -> list[dict]:
    """Order facts so the ones that explain the verdict come first."""
    want = 1 if f.p_up >= 0.5 else -1
    ranked = sorted(facts, key=lambda x: (x["lean"] == want, x["lean"] != 0, x["w"]), reverse=True)
    if f.direction == "flat":
        ranked = sorted(facts, key=lambda x: x["w"], reverse=True)
    return [{"text": x["text"], "lean": x["lean"], "refs": [x["id"]]} for x in ranked[:limit]]


def build_view(db: DB, asset: Asset, horizon: str = "1w", insight: dict | None = None,
               with_chart: bool = True, snaps: dict | None = None) -> dict:
    """Everything the UI and the bot need for one asset at one horizon.

    `insight` is the stored LLM analysis for this asset, if any: per-bucket tilts,
    a conclusion and reasons with references.
    """
    snap = snapshot(db, asset)
    if not snap:
        return {"key": asset.key, "name": asset.name, "error": "no_data"}
    facts = build_facts(db, asset, snaps)
    interval, steps, label = parse_horizon(horizon, asset.days_per_week)
    bucket = bucket_of(interval, steps)
    rule_tilt = evidence_tilt(facts)
    llm_tilt = float((insight or {}).get("tilt", {}).get(bucket, 0.0))
    try:
        quant, final, meta = forecast_asset(db, asset, horizon, tilt=rule_tilt + llm_tilt)
    except ValueError:
        return {"key": asset.key, "name": asset.name, "error": "not_enough_history", "snapshot": snap}

    notes = []
    if meta["interval"] == "1h" and meta["unchanged_share"] > 0.3:
        notes.append(both(lambda lang: (
            "Data per jam untuk aset ini sering tidak bergerak (sumber gratis), jadi prakiraan jam-jaman kurang bisa diandalkan."
            if lang == "id" else
            "Hourly data for this asset often does not move (free source), so hour-level forecasts are less reliable.")))
    age = time.time() - meta["base_ts"]
    if age > (4 * 86400 if meta["interval"] == "1d" else 3 * 86400):
        notes.append(both(lambda lang: (
            f"Data terakhir berumur {age / 86400:.0f} hari." if lang == "id" else f"Latest data is {age / 86400:.0f} days old.")))

    val = validation(db, asset, label)
    view = {
        "key": asset.key, "name": asset.name, "name_en": asset.nm("en"), "klass": asset.klass, "country": asset.country,
        "decimals": asset.decimals, "unit": asset.unit, "up_is": asset.up_is,
        "horizon": label, "horizon_name": horizon_name(label),
        "snapshot": {k: v for k, v in snap.items() if k != "spark"},
        "forecast": final.to_dict() | {"p_up_quant": quant.p_up, "tilt_rule": rule_tilt, "tilt_llm": llm_tilt},
        "direction": final.direction,
        "summary": conclusion_text(asset, final, label, snap),
        "reasons": (insight or {}).get("reasons") or pick_reasons(facts, final, quant),
        "watch": (insight or {}).get("watch"),
        "facts": facts,
        "vigilance": vigilance(asset, final),
        "validation": {k: val.get(k) for k in ("grade", "n", "hit_rate", "cover90", "cover50", "skill_vs_base")} if val else None,
        "insight_at": (insight or {}).get("at"),
        "notes": notes,
        "meta": meta,
    }
    if not with_chart:
        view["forecast"].pop("band", None)
    else:
        hist = load_bars(db, asset.symbol, meta["interval"], 90 if meta["interval"] == "1d" else 72)
        view["history"] = [{"t": int(t), "c": float(c)} for t, c in zip(hist["ts"], hist["c"])]
    return view


def all_horizons(db: DB, asset: Asset, insight: dict | None = None, snaps: dict | None = None) -> list[dict]:
    """Compact row per preset horizon, for the 'next hour ... next month' strip."""
    facts = build_facts(db, asset, snaps)
    rule_tilt = evidence_tilt(facts)
    rows = []
    for h in DEFAULT_HORIZONS:
        interval, steps, label = parse_horizon(h, asset.days_per_week)
        tilt = rule_tilt + float((insight or {}).get("tilt", {}).get(bucket_of(interval, steps), 0.0))
        try:
            _, f, meta = forecast_asset(db, asset, h, tilt=tilt)
        except ValueError:
            continue
        rows.append({"horizon": label, "name": horizon_name(label), "p_up": f.p_up, "direction": f.direction,
                     "q05": f.q05, "q50": f.q50, "q95": f.q95, "touch": f.touch,
                     "thin": meta["interval"] == "1h" and meta["unchanged_share"] > 0.3})
    return rows


def record_forecasts(db: DB, asset: Asset, insight: dict | None = None, source: str = "auto") -> int:
    """Write the current forecast for each preset horizon to the ledger, once per bar."""
    facts = build_facts(db, asset)
    rule_tilt = evidence_tilt(facts)
    n = 0
    for h in DEFAULT_HORIZONS:
        interval, steps, label = parse_horizon(h, asset.days_per_week)
        tilt = rule_tilt + float((insight or {}).get("tilt", {}).get(bucket_of(interval, steps), 0.0))
        try:
            quant, f, meta = forecast_asset(db, asset, h, tilt=tilt)
        except ValueError:
            continue
        with db.tx() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO forecasts (asset, horizon, interval, steps, base_ts, made_at, s0, p_up_quant, "
                "p_up, direction, q05, q25, q50, q75, q95, touch, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (asset.key, label, interval, steps, meta["base_ts"], int(time.time()), f.s0, quant.p_up, f.p_up,
                 f.direction, f.q05, f.q25, f.q50, f.q75, f.q95, json.dumps(f.touch), source),
            )
            n += cur.rowcount
    return n


def score_forecasts(db: DB) -> int:
    """Fill in outcomes for forecasts whose horizon has passed."""
    from .universe import BY_KEY

    done = 0
    for row in db.q("SELECT id, asset, interval, steps, base_ts, s0 FROM forecasts WHERE scored_at IS NULL"):
        asset = BY_KEY.get(row["asset"])
        if not asset:
            continue
        later = db.q(
            "SELECT ts, c FROM bars WHERE symbol=? AND interval=? AND ts>? ORDER BY ts LIMIT ?",
            (asset.symbol, row["interval"], row["base_ts"], row["steps"] + 1),
        )
        # One extra bar must exist so the target bar is closed, not still forming.
        if len(later) <= row["steps"]:
            continue
        s_t = later[row["steps"] - 1]["c"]
        went = 1 if s_t > row["s0"] else (0 if s_t < row["s0"] else None)
        db.x("UPDATE forecasts SET scored_at=?, s_t=?, went_up=? WHERE id=?", (int(time.time()), s_t, went, row["id"]))
        done += 1
    return done


def forecast_hit(row) -> bool:
    """One recorded forecast was right when the price ended inside its 9-in-10 range and, when it named a
    direction (chance of a rise at least 60% or at most 40%), moved that way."""
    if row["s_t"] is None or row["q05"] is None or row["q95"] is None:
        return False
    inside = row["q05"] <= row["s_t"] <= row["q95"]
    p = round(row["p_up"], 2)
    if p >= 0.60:
        return inside and row["s_t"] > row["s0"]
    if p <= 0.40:
        return inside and row["s_t"] < row["s0"]
    return inside


def record_summary(db: DB, horizon: str = "1m", keys: list[str] | None = None, last: int = 30, min_n: int = 10) -> dict:
    """"Prediksi 1 bln tepat X% (N prediksi terakhir)" from the ledger; "enough" is false below min_n."""
    marks = ",".join("?" * len(keys)) if keys else ""
    rows = db.q("SELECT s0, s_t, p_up, q05, q95 FROM forecasts WHERE horizon=? AND scored_at IS NOT NULL"
                + (f" AND asset IN ({marks})" if keys else "") + " ORDER BY base_ts DESC LIMIT ?",
                (horizon, *(keys or []), last))
    pending = db.one("SELECT COUNT(*) n FROM forecasts WHERE horizon=? AND scored_at IS NULL"
                     + (f" AND asset IN ({marks})" if keys else ""), (horizon, *(keys or [])))["n"]
    hits = sum(1 for r in rows if forecast_hit(r))
    return {"horizon": horizon, "n": len(rows), "hits": hits, "pct": round(100 * hits / len(rows)) if rows else None,
            "pending": pending, "enough": len(rows) >= min_n}


def track_record(db: DB) -> dict:
    """Live scorecard from the ledger, grouped by horizon."""
    rows = db.q("SELECT horizon, p_up, p_up_quant, direction, q05, q95, q25, q75, s_t, went_up FROM forecasts "
                "WHERE scored_at IS NOT NULL")
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["horizon"], []).append(r)
    out = []
    for h in DEFAULT_HORIZONS:
        g = groups.get(h, [])
        moved = [r for r in g if r["went_up"] is not None]
        calls = [r for r in moved if r["direction"] != "flat"]
        hits = sum(1 for r in calls if (r["direction"] == "up") == bool(r["went_up"]))
        out.append({
            "horizon": h, "name": horizon_name(h), "n": len(g),
            "calls": len(calls), "call_hits": hits,
            "brier": float(np.mean([(r["p_up"] - r["went_up"]) ** 2 for r in moved])) if moved else None,
            "brier_quant": float(np.mean([(r["p_up_quant"] - r["went_up"]) ** 2 for r in moved])) if moved else None,
            "cover90": float(np.mean([r["q05"] <= r["s_t"] <= r["q95"] for r in g])) if g else None,
            "cover50": float(np.mean([r["q25"] <= r["s_t"] <= r["q75"] for r in g])) if g else None,
        })
    pending = db.one("SELECT COUNT(*) n FROM forecasts WHERE scored_at IS NULL")["n"]
    return {"by_horizon": out, "pending": pending, "scored": len(rows)}

