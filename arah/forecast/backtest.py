"""Walk-forward test of the forecast engine against naive baselines.

Every forecast only sees bars that existed at its origin. Origins are spaced
one horizon apart so the scored windows do not overlap.
"""
from __future__ import annotations

import math

import numpy as np

from .engine import MIN_BARS, direction_of, simulate


def walk_forward(
    closes: np.ndarray,
    steps: int,
    drift_strength: float = 0.0,
    max_origins: int = 250,
    n_paths: int = 1500,
    warmup: int = 400,
    mean_shrink: float = 0.0,
) -> dict:
    closes = np.asarray(closes, dtype=float)
    origins = list(range(max(warmup, MIN_BARS), len(closes) - steps, steps))[-max_origins:]
    if len(origins) < 30:
        return {"n": len(origins), "enough": False}
    p_up, up, in50, in90, called, called_hit = [], [], [], [], 0, 0
    base_rate_hist = []
    for k, i in enumerate(origins):
        hist = closes[: i + 1][-2500:]
        f = simulate(hist, steps, n_paths=n_paths, drift_strength=drift_strength, seed=k, mean_shrink=mean_shrink)
        s_t = closes[i + steps]
        went_up = 1.0 if s_t > closes[i] else (0.5 if s_t == closes[i] else 0.0)
        p_up.append(f.p_up)
        up.append(went_up)
        in50.append(f.q25 <= s_t <= f.q75)
        in90.append(f.q05 <= s_t <= f.q95)
        d = direction_of(f.p_up)
        if d != "flat":
            called += 1
            called_hit += int((d == "up") == (went_up > 0.5)) if went_up != 0.5 else 0
            called -= int(went_up == 0.5)
        # Share of up-moves seen so far: the "always say what usually happens" baseline.
        prior = np.diff(np.log(hist[::steps]))
        base_rate_hist.append(float((prior > 0).mean() + 0.5 * (prior == 0).mean()) if len(prior) else 0.5)
    p = np.array(p_up)
    y = np.array(up, dtype=float)
    base = np.array(base_rate_hist)
    n = len(y)
    brier = float(np.mean((p - y) ** 2))
    brier_coin = 0.25
    brier_base = float(np.mean((base - y) ** 2))
    moved = y != 0.5
    n_moved = int(moved.sum()) or 1
    hit = float(np.mean((p[moved] > 0.5) == (y[moved] > 0.5))) if moved.any() else 0.5
    # Standard error of a hit rate under a fair coin, for a rough significance read.
    se = math.sqrt(0.25 / n_moved)
    return {
        "n": n,
        "enough": True,
        "hit_rate": hit,
        "hit_rate_z": (hit - 0.5) / se,
        "up_share": float(y.mean()),
        "unchanged_share": float(1 - moved.mean()),
        "brier": brier,
        "brier_coin": brier_coin,
        "brier_base": brier_base,
        "skill_vs_coin": 1 - brier / brier_coin,
        "skill_vs_base": 1 - brier / brier_base if brier_base else 0.0,
        "cover50": float(np.mean(in50)),
        "cover90": float(np.mean(in90)),
        "calls": called,
        "call_hit_rate": (called_hit / called) if called else None,
    }


def grade(result: dict) -> str:
    """'validated' only when direction beats both baselines and the ranges are honest."""
    if not result.get("enough"):
        return "insufficient"
    ranges_ok = abs(result["cover90"] - 0.90) <= 0.07 and abs(result["cover50"] - 0.50) <= 0.10
    # z > 2.33 (about 1 in 100 by luck): many asset and horizon pairs are tested, so the bar is high.
    direction_ok = (result["skill_vs_coin"] > 0.01 and result["skill_vs_base"] > 0.0
                    and result["hit_rate_z"] > 2.33 and result["n"] >= 100)
    if ranges_ok and direction_ok:
        return "validated"
    if ranges_ok:
        return "range_only"
    return "experimental"
