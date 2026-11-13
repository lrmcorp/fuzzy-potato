"""Kurs: one dollar and one yuan in rupiah, why the rate moved, and whether the move is normal.

"Wajar" here is measured, not judged: a month's change is compared with how much this rate usually moves in a
month (the standard deviation of 21-day changes over about two years). The causes are the ones the data can show:
the dollar against everyone (DXY), the rupiah against other Asian currencies, US yields, foreign investors in
Indonesian stocks and the stock market itself. Nothing here is a forecast except the model's range, labelled as such.
"""
from __future__ import annotations

import numpy as np

from .data.news import COUNTRY_TOPICS, top_stories
from .data.yahoo import load_bars
from .db import DB
from .panel import foreign_flow
from .service import forecast_asset
from .signals import fmt_num, quote_info, snapshot
from .universe import BY_KEY

PEERS = [("USDJPY", "Yen Jepang"), ("USDSGD", "Dolar Singapura"), ("USDCNY", "Yuan China")]
FX_WORDS = ("rupiah", "dolar", "dollar", "yuan", "renminbi", "kurs", "valas", "bi rate", "suku bunga")


# The lead cause in words, for a rising and for a falling USD/IDR.
LEAD_TEXT = {
    "dxy": ("dolar sedang menguat ke hampir semua mata uang", "dolar sedang melemah ke hampir semua mata uang"),
    "asia": ("rupiah melemah lebih dari mata uang Asia lain, jadi sebabnya terutama dari dalam negeri",
             "rupiah menguat lebih dari mata uang Asia lain, jadi sebabnya terutama dari dalam negeri"),
    "yield": ("bunga obligasi AS naik", "bunga obligasi AS turun"),
    "asing": ("investor asing menjual saham Indonesia", "investor asing membeli saham Indonesia"),
    "ihsg": ("saham Indonesia turun tajam", "saham Indonesia naik tajam"),
}


def typical_month(db: DB, key: str, days: int = 21, history: int = 520) -> float | None:
    """How much the rate usually moves in a month, in percent: the spread of its 21-day changes."""
    c = load_bars(db, BY_KEY[key].symbol, "1d", history)["c"]
    if len(c) < days * 6:
        return None
    r = np.log(c[days:] / c[:-days]) * 100
    sd = float(np.std(r))
    return sd if sd > 0 else None


def normal_label(chg: float | None, sd: float | None) -> dict | None:
    """biasa within one usual month's move, besar up to two, tidak_biasa beyond."""
    if chg is None or not sd:
        return None
    z = chg / sd
    key = "biasa" if abs(z) <= 1 else "besar" if abs(z) <= 2 else "tidak_biasa"
    text = {"biasa": "Masih wajar", "besar": "Lebih besar dari biasanya", "tidak_biasa": "Tidak biasa"}[key]
    return {"key": key, "label": text, "z": round(z, 2), "sd": round(sd, 2)}


def _chg(db: DB, key: str, field: str = "chg1m") -> float | None:
    s = snapshot(db, BY_KEY[key])
    return s.get(field) if s else None


def drivers(db: DB, usd_chg: float | None) -> list[dict]:
    """What pushed USD/IDR over the last month. push +1 means it pushed the dollar up (rupiah weaker)."""
    out = []
    dxy = _chg(db, "DXY")
    if dxy is not None:
        out.append({"key": "dxy", "label": "Dolar terhadap mata uang dunia (DXY)", "value": dxy, "unit": "%",
                    "push": 1 if dxy > 0.3 else -1 if dxy < -0.3 else 0,
                    "why": "Dolar yang menguat ke semua mata uang ikut menaikkan USD/IDR."})
    peers = [v for k, _ in PEERS if (v := _chg(db, k)) is not None]
    if usd_chg is not None and peers:
        gap = usd_chg - sum(peers) / len(peers)
        out.append({"key": "asia", "label": "Rupiah dibanding mata uang Asia lain", "value": gap, "unit": "pp",
                    "push": 1 if gap > 0.5 else -1 if gap < -0.5 else 0,
                    "why": "Bila rupiah melemah lebih dari yen, dolar Singapura dan yuan, sebabnya ada di dalam negeri."})
    y = _chg(db, "US10Y")
    if y is not None:
        out.append({"key": "yield", "label": "Yield obligasi AS 10 tahun", "value": y, "unit": "%",
                    "push": 1 if y > 2 else -1 if y < -2 else 0,
                    "why": "Bunga AS yang naik menarik dana keluar dari negara berkembang seperti Indonesia."})
    f = foreign_flow(db, top=100)
    net = sum(r["net"] for r in f["buy"]) + sum(r["net"] for r in f["sell"]) if f["covered"] else None
    if net:
        out.append({"key": "asing", "label": f"Asing di saham Indonesia ({f['covered']} saham, 1 bln)", "value": net, "unit": "idr",
                    "push": 1 if net < 0 else -1,
                    "why": "Asing yang menjual saham menukar rupiah ke dolar, menekan rupiah."})
    ihsg = _chg(db, "IHSG")
    if ihsg is not None:
        out.append({"key": "ihsg", "label": "IHSG", "value": ihsg, "unit": "%",
                    "push": 1 if ihsg < -3 else -1 if ihsg > 3 else 0,
                    "why": "Saham yang turun tajam biasanya sejalan dengan dana yang keluar dan rupiah yang melemah."})
    return out


def _forecast(db: DB, key: str) -> dict:
    out = {}
    for h in ("1w", "1m"):
        try:
            _, f, _ = forecast_asset(db, BY_KEY[key], h)
        except ValueError:
            continue
        out[h] = {"q05": f.q05, "q50": f.q50, "q95": f.q95, "p_up": f.p_up}
    return out


def _news(db: DB, limit: int = 3) -> list[dict]:
    items = top_stories(db, COUNTRY_TOPICS["ID"], limit=60)
    hits = [s for s in items if any(w in s["title"].lower() for w in FX_WORDS)]
    return [{"title": s["title"], "url": s["url"], "sources": s.get("sources") or [s["source"]], "impact": s.get("impact"),
             "published_at": s["published_at"]} for s in hits[:limit]]


def rate_view(db: DB, key: str) -> dict | None:
    a = BY_KEY[key]
    s = snapshot(db, a)
    if not s:
        return None
    sd = typical_month(db, key)
    c = load_bars(db, a.symbol, "1d", 300)["c"]
    chg1y = float(c[-1] / c[0] * 100 - 100) if len(c) >= 250 else None
    pos = (s["price"] - s["lo52"]) / (s["hi52"] - s["lo52"]) if s["hi52"] > s["lo52"] else None
    return {
        "key": key, "name": a.name, "price": s["price"], "src": s.get("src"), "decimals": a.decimals,
        "chg": {"1d": s["chg1d"], "1w": s["chg1w"], "1m": s["chg1m"], "3m": s["chg3m"], "1y": chg1y},
        "year": {"lo": s["lo52"], "hi": s["hi52"], "pos": pos, "near_high": s["from_hi"] > -2, "near_low": s["from_lo"] < 2},
        "normal": normal_label(s["chg1m"], sd), "spark": s["spark"], "forecast": _forecast(db, key),
    }


def summary_sentence(v: dict, drv: list[dict], unit: str) -> str:
    """One plain sentence: what moved, whether that is normal, and the biggest cause."""
    m = v["chg"]["1m"]
    if m is None:
        return f"Belum ada cukup data untuk {unit}."
    move = "naik" if m > 0 else "turun"
    n = v.get("normal")
    head = f"{unit} {move} {fmt_num(abs(m), 1)}% sebulan"
    head += f", {n['label'].lower()} (biasanya bergerak sekitar {fmt_num(n['sd'], 1)}% sebulan)." if n else "."
    if v["year"]["near_high"]:
        head += " Kurs ini sekarang dekat titik tertinggi setahun."
    elif v["year"]["near_low"]:
        head += " Kurs ini sekarang dekat titik terendah setahun."
    # The two currency causes are in the same unit, so the bigger one leads; the others follow.
    lead = sorted((d for d in drv if d["push"] == (1 if m > 0 else -1)),
                  key=lambda d: (d["key"] not in ("dxy", "asia"), -abs(d["value"])))
    if lead:
        head += f" Pendorong utama: {LEAD_TEXT[lead[0]['key']][0 if m > 0 else 1]}."
    return head


def focus(db: DB) -> dict:
    usd = rate_view(db, "USDIDR")
    cny = rate_view(db, "CNYIDR")
    drv = drivers(db, usd["chg"]["1m"] if usd else None)
    peers = []
    for k, name in [("USDIDR", "Rupiah")] + PEERS:
        v = _chg(db, k)
        if v is not None:
            peers.append({"key": k, "name": name, "chg1m": v})
    # CNY/IDR = USD/IDR ÷ USD/CNY, so its change is (about) the rupiah leg minus the yuan leg.
    cny_parts = None
    if usd and cny:
        u, y = usd["chg"]["1m"], _chg(db, "USDCNY")
        if u is not None and y is not None:
            cny_parts = {"usd_idr": u, "usd_cny": y,
                         "text": f"Rupiah {'melemah' if u > 0 else 'menguat'} {fmt_num(abs(u), 1)}% terhadap dolar, yuan "
                                 f"{'melemah' if y > 0 else 'menguat'} {fmt_num(abs(y), 1)}% terhadap dolar."}
    return {
        "usd": usd and {**usd, "sentence": summary_sentence(usd, drv, "Dolar terhadap rupiah")},
        "cny": cny and {**cny, "sentence": summary_sentence(cny, [], "Yuan terhadap rupiah"), "parts": cny_parts},
        "drivers": drv, "peers": peers, "news": _news(db),
        "usd_quote": quote_info(db, BY_KEY["USDIDR"]),
    }

