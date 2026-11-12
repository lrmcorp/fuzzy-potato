"""Probabilistic price forecasts by filtered historical simulation.

Volatility clusters, so recent turbulence says a lot about the width of the
next move. Direction is far harder: the drift term is deliberately small and
shrunk towards zero, and the backtest in `backtest.py` is what decides how much
of it we are allowed to use.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# GARCH(1,1)-style recursion with fixed, conventional weights. Fixed weights
# are more stable than fitting them on a few hundred noisy bars.
ALPHA, BETA = 0.07, 0.91
MIN_BARS = 120


@dataclass
class Forecast:
    s0: float
    steps: int
    p_up: float
    q05: float
    q25: float
    q50: float
    q75: float
    q95: float
    touch: dict[str, float] = field(default_factory=dict)
    band: list[dict] = field(default_factory=list)  # per-step quantiles for the fan chart
    vol_step: float = 0.0  # current one-step volatility (log-return std)
    vol_ratio: float = 1.0  # current vol relative to its long-run level
    drift_step: float = 0.0

    @property
    def direction(self) -> str:
        return direction_of(self.p_up)

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in ("s0", "steps", "p_up", "q05", "q25", "q50", "q75", "q95",
                                           "touch", "band", "vol_step", "vol_ratio", "drift_step")}
        d["direction"] = self.direction
        return d


def direction_of(p_up: float) -> str:
    if p_up >= 0.55:
        return "up"
    if p_up <= 0.45:
        return "down"
    return "flat"


def log_returns(closes: np.ndarray) -> np.ndarray:
    c = np.asarray(closes, dtype=float)
    return np.diff(np.log(c))


def conditional_vol(r: np.ndarray) -> tuple[np.ndarray, float]:
    """Return the variance path (aligned so var[i] is the forecast for r[i]) and the long-run variance."""
    long_var = float(np.var(r)) or 1e-12
    omega = (1 - ALPHA - BETA) * long_var
    var = np.empty(len(r) + 1)
    var[0] = long_var
    for i, x in enumerate(r):
        var[i + 1] = omega + ALPHA * x * x + BETA * var[i]
    return var, long_var


def trend_drift(r: np.ndarray, var_now: float, strength: float) -> float:
    """A small per-step drift from medium-term momentum, capped at a fraction of one-step vol.

    `strength` is the cap as a share of the one-step standard deviation. Zero
    switches the drift off, which makes every forecast a coin flip around the
    current price.
    """
    if strength <= 0 or len(r) < 60:
        return 0.0
    sd = math.sqrt(var_now)
    score = 0.0
    for look, w in ((20, 0.5), (60, 0.3), (120, 0.2)):
        if len(r) >= look:
            window = r[-look:]
            t = window.mean() / (window.std() / math.sqrt(look) + 1e-12)  # t-stat of the mean
            score += w * math.tanh(t / 2.0)
    return float(score * strength * sd)


def simulate(
    closes: np.ndarray,
    steps: int,
    levels: list[float] | None = None,
    n_paths: int = 4000,
    drift_strength: float = 0.0,
    extra_drift_total: float = 0.0,
    mean_shrink: float = 0.0,
    seed: int | None = None,
) -> Forecast:
    closes = np.asarray(closes, dtype=float)
    if len(closes) < MIN_BARS:
        raise ValueError(f"need at least {MIN_BARS} bars, got {len(closes)}")
    r = log_returns(closes)
    r = r[np.isfinite(r)]
    var_path, long_var = conditional_vol(r)
    z = r / np.sqrt(var_path[:-1])
    z = z[np.isfinite(z)][-1500:]
    # Bars where the quote did not update stay exact zeros; only real moves are de-meaned.
    live = z != 0
    if live.any():
        z[live] -= z[live].mean()
    var_now = float(var_path[-1])
    omega = (1 - ALPHA - BETA) * long_var
    # Long-run average return, shrunk: stocks drift up over years, and ignoring that
    # makes month-ahead odds too pessimistic.
    mu = trend_drift(r, var_now, drift_strength) + extra_drift_total / steps + mean_shrink * float(r.mean())

    rng = np.random.default_rng(seed)
    s0 = float(closes[-1])
    var = np.full(n_paths, var_now)
    logp = np.zeros(n_paths)
    moved = np.zeros(n_paths, dtype=bool)
    levels = [float(x) for x in (levels or []) if x > 0]
    log_levels = [math.log(x / s0) for x in levels]
    hit = [np.zeros(n_paths, dtype=bool) for _ in levels]
    band: list[dict] = []
    for step in range(1, steps + 1):
        shock = rng.choice(z, size=n_paths) * np.sqrt(var)
        prev = logp
        # A stale quote does not drift either.
        logp = logp + np.where(shock != 0, mu, 0.0) + shock
        moved |= shock != 0
        for i, lv in enumerate(log_levels):
            up = lv > 0
            crossed = (logp >= lv) if up else (logp <= lv)
            # Brownian-bridge correction: a path can cross the level inside a
            # bar and come back before the close.
            both_short = (prev < lv) & (logp < lv) if up else (prev > lv) & (logp > lv)
            p_inside = np.zeros(n_paths)
            p_inside[both_short] = np.exp(
                -2.0 * (lv - prev[both_short]) * (lv - logp[both_short]) / np.maximum(var[both_short], 1e-18)
            )
            hit[i] |= crossed | (rng.random(n_paths) < p_inside)
        var = omega + ALPHA * (shock**2) + BETA * var
        qs = np.quantile(logp, [0.05, 0.25, 0.5, 0.75, 0.95])
        band.append({"step": step, **{k: s0 * math.exp(v) for k, v in zip(("q05", "q25", "q50", "q75", "q95"), qs)}})

    qs = [b for b in band[-1].values()][1:]
    if len(band) > 30:
        idx = np.unique(np.linspace(0, len(band) - 1, 30).round().astype(int))
        band = [band[i] for i in idx]
    return Forecast(
        s0=s0,
        steps=steps,
        # A path whose every shock was zero is a quote that never updated (common in thin
        # hourly FX data). It counts half each way, whatever the drift.
        p_up=float(((logp > 0) & moved).mean() + 0.5 * (~moved).mean()),
        q05=qs[0], q25=qs[1], q50=qs[2], q75=qs[3], q95=qs[4],
        touch={_level_key(lv): float(h.mean()) for lv, h in zip(levels, hit)},
        band=band,
        vol_step=math.sqrt(var_now),
        vol_ratio=math.sqrt(var_now / long_var),
        drift_step=mu,
    )


def _level_key(level: float) -> str:
    return f"{level:.10g}"


def tilt_to_drift(p_from: float, p_to: float, vol_step: float, steps: int) -> float:
    """Total extra log-drift that moves P(up) from p_from to p_to under a normal approximation."""
    from statistics import NormalDist

    nd = NormalDist()
    clamp = lambda p: min(max(p, 0.02), 0.98)
    dz = nd.inv_cdf(clamp(p_to)) - nd.inv_cdf(clamp(p_from))
    return dz * vol_step * math.sqrt(steps)
