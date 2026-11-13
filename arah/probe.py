"""Shape of Stockbit's answers for the terminal's data, to choose the right parameters.
Only field names, types, row counts, date spans and Stockbit's error messages: no tokens or values."""
from __future__ import annotations

import time

from .data.stockbit import Stockbit, StockbitError


def _shape(v, depth=0):
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_shape(x, depth + 1) if depth < 2 else type(x).__name__}" for k, x in list(v.items())[:16]) + "}"
    if isinstance(v, list):
        return f"list[{len(v)}]" + (f" of {_shape(v[0], depth + 1)}" if v and depth < 2 else "")
    return type(v).__name__


def _when(x):
    try:
        x = float(x)
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(x / 1000 if x > 1e11 else x))
    except (TypeError, ValueError):
        return str(x)[:25]


def _spans(data):
    if not isinstance(data, dict):
        return ""
    out = []
    for k, v in data.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            f = next((f for f in ("date", "time", "datetime", "created_at", "timestamp") if f in v[0]), None)
            out.append(f"{k}: {len(v)} rows" + (f", {_when(v[0].get(f))} .. {_when(v[-1].get(f))}" if f else ""))
    return "; ".join(out)


def tries() -> list[str]:
    today = time.strftime("%Y-%m-%d")
    year_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 370 * 86400))
    return [
        "/charts/BBCA/daily?timeframe=today&chart_type=PRICE_CHART_TYPE_CANDLE",
        "/charts/BBCA/daily?timeframe=1d&chart_type=PRICE_CHART_TYPE_CANDLE",
        "/charts/BBCA/daily?timeframe=1y&chart_type=PRICE_CHART_TYPE_CANDLE",
        "/charts/BBCA/daily?timeframe=5y&chart_type=PRICE_CHART_TYPE_CANDLE",
        f"/company-price-feed/historical/summary/BBCA?period=HS_PERIOD_DAILY&start_date={year_ago}&end_date={today}&limit=50&page=1",
        "/company-price-feed/historical/summary/BBCA?limit=50&page=1",
        "/order-trade/running-trade/chart/BBCA?period=RT_PERIOD_LAST_1_DAY&investor_type=INVESTOR_TYPE_ALL&market_board=BOARD_TYPE_REGULAR",
        "/marketdetectors/BBCA",
        "/marketdetectors/BBCA?transaction_type=TRANSACTION_TYPE_NET&market_board=BOARD_TYPE_REGULAR&investor_type=INVESTOR_TYPE_ALL&limit=25",
        "/marketdetectors/BBCA?transaction_type=TRANSACTION_TYPE_NET&market_board=MARKET_BOARD_REGULER&investor_type=INVESTOR_TYPE_ALL&limit=25",
        f"/order-trade/broker/distribution?date={today}&symbol=BBCA&investor_type=INVESTOR_TYPE_ALL&market_board=BOARD_TYPE_REGULAR",
        "/findata-view/foreign-domestic/v1/chart-data/BBCA",
        "/findata-view/foreign-domestic/v1/chart-data/BBCA?market_type=MARKET_TYPE_REGULAR&period=PERIOD_RANGE_1M",
        "/insider/company/majorholder?symbols=BBCA&page=1&limit=10",
        "/stream/v3/symbol/BBCA?limit=10",
        "/stream/v3/symbol/BBCA?category=STREAM_CATEGORY_ALL&limit=10",
    ]


async def probe_lines(sb: Stockbit, paths: list[str] | None = None) -> list[str]:
    lines = []
    for path in paths or tries():
        label = path.split("?")[0].replace("BBCA", "{code}") + ("?" + path.split("?")[1][:90] if "?" in path else "")
        try:
            status, body = await sb.probe(path)
        except StockbitError as e:
            lines.append(f"ERR  {label} :: {str(e)[:120]}")
            continue
        msg, data = "", body
        if isinstance(body, dict):
            msg = str(body.get("message") or body.get("error") or "")[:160]
            data = body.get("data", body)
        sp = _spans(data)
        lines.append(f"{status}  {label}" + (f" :: message: {msg}" if msg else "") + f" :: shape: {_shape(data)[:500]}"
                     + (f" :: rows: {sp}" if sp else ""))
    return lines
