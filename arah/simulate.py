"""Simulasi modal: split the owner's capital across today's Pilihan ARAH and show what the model's ranges mean
in rupiah over 1 week, 1, 2 and 3 months.

Every number comes from the same forecast the rest of the app shows (the 5th, 50th and 95th percentile of the
simulated paths), scaled to today's price. Nothing here is a promise; the page says so.
"""
from __future__ import annotations

from .db import DB
from .recommend import order_picks
from .service import forecast_asset
from .signals import quote_info
from .universe import BY_KEY

HORIZONS = [("1w", "1 mgg"), ("1m", "1 bln"), ("2m", "2 bln"), ("3m", "3 bln")]
MAX_STOCKS = 5


def allocate(cards: list[dict], capital: float, unit_cost) -> list[tuple[dict, int]]:
    """Equal weight across the best-ranked picks the capital can buy, in whole lots (IDX) or shares (US).

    Start with up to MAX_STOCKS picks; while the equal share is below one lot of some pick, drop the most expensive
    one. Leftover cash then buys single lots in rank order, as long as no stock grows past 1.5x its fair share."""
    pool = [c for c in cards if unit_cost(c) > 0][:MAX_STOCKS]
    while pool:
        share = capital / len(pool)
        too_dear = [c for c in pool if unit_cost(c) > share]
        if not too_dear:
            break
        pool.remove(max(too_dear, key=unit_cost))
    if not pool:
        return []
    share = capital / len(pool)
    units = {c["key"]: int(share // unit_cost(c)) for c in pool}
    cash = capital - sum(units[c["key"]] * unit_cost(c) for c in pool)
    added = True
    while added:
        added = False
        for c in pool:
            u = unit_cost(c)
            if u <= cash and (units[c["key"]] + 1) * u <= 1.5 * share:
                units[c["key"]] += 1
                cash -= u
                added = True
    return [(c, units[c["key"]]) for c in pool if units[c["key"]] > 0]


def simulate_capital(db: DB, recs: dict, capital: float, market: str = "ID", profile: str | None = None) -> dict:
    market = "US" if market == "US" else "ID"
    usd = None
    if market == "US":
        q = quote_info(db, BY_KEY["USDIDR"])
        usd = q["price"] if q else None
        if not usd:
            return {"error": "no_fx", "capital": capital, "market": market}
    fx = usd or 1.0
    lot = 100 if market == "ID" else 1
    cards = order_picks([c for c in recs.get(market, []) if not c.get("held") and c.get("plan")], profile)
    unit_cost = lambda c: c["price"] * lot * fx  # rupiah for one lot (IDX) or one share (US)
    picks = allocate(cards, capital, unit_cost)
    if not picks:
        cheapest = min(cards, key=unit_cost) if cards else None
        return {"capital": capital, "market": market, "items": [], "cash": capital, "horizons": [h for h, _ in HORIZONS],
                "need": {"key": cheapest["key"], "rp": unit_cost(cheapest)} if cheapest else None, "fx": usd, "profile": profile}

    items, totals = [], {h: {"q05": 0.0, "q50": 0.0, "q95": 0.0} for h, _ in HORIZONS}
    for c, units in picks:
        a = BY_KEY[c["key"]]
        cost = units * unit_cost(c)
        out = {}
        for h, _ in HORIZONS:
            try:
                _, f, _ = forecast_asset(db, a, h)
            except ValueError:
                out = None
                break
            # The model's quantiles are relative to its last close; apply the same ratios to today's price.
            r = {k: getattr(f, k) / f.s0 for k in ("q05", "q50", "q95")} if f.s0 else None
            if not r:
                out = None
                break
            out[h] = {k: cost * r[k] for k in r} | {"p_up": f.p_up}
        if out is None:
            continue
        for h in out:
            for k in ("q05", "q50", "q95"):
                totals[h][k] += out[h][k]
        stop = c["plan"]["stop"]
        items.append({
            "key": c["key"], "name": c["name"], "sector": c.get("sector"), "tag": c.get("tag"),
            "price": c["price"], "currency": "IDR" if market == "ID" else "USD", "units": units,
            "unit": "lot" if market == "ID" else "lembar", "cost": cost,
            "stop": stop, "loss_at_stop": units * lot * (c["price"] - stop) * fx,
            "target1": c["plan"]["targets"][0], "outcomes": out,
        })
    invested = sum(i["cost"] for i in items)
    cash = capital - invested
    for h in totals:  # cash stays cash
        for k in totals[h]:
            totals[h][k] += cash
    return {"capital": capital, "market": market, "fx": usd, "profile": profile, "items": items, "cash": cash,
            "invested": invested, "horizons": [h for h, _ in HORIZONS], "labels": dict(HORIZONS),
            "total": totals if items else None,
            "loss_at_stops": sum(i["loss_at_stop"] for i in items)}

