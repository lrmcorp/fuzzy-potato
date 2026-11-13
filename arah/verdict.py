"""One word a newcomer can act on for each stock: Layak (worth buying), Tunggu (wait) or Hindari (avoid),
with a 0 to 100 score and the three reasons that moved it most.

The score is a plain rule over data ARAH already has, so every point can be explained:

  part          max  what earns it
  trend          30  price above its 50-day and 200-day averages, and the 50-day above the 200-day
  chance         20  the forecast's chance of a rise over the next month
  flow           25  broker accumulation (Stockbit bandar detector) and a month's net foreign buying
  value          15  P/E below its own average of recent years, and profit growing
  calm           10  not overheated (RSI) and not swinging much more than usual

A part with no data is left out and the score is taken over the parts that remain, so a US stock
(no bandar data) is not marked down for it. The rule has not been tested on past data yet; the
screen says so.
"""
from __future__ import annotations

import time

from .db import DB
from .signals import fmt_pct, snapshot
from .universe import Asset

LABELS = {"layak": ("Layak", "Worth buying"), "tunggu": ("Tunggu", "Wait"), "hindari": ("Hindari", "Avoid")}
LAYAK_AT, HINDARI_BELOW = 65, 45


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score(db: DB, asset: Asset, p_up: float | None, fund: dict | None = None, sbt: dict | None = None) -> dict | None:
    s = snapshot(db, asset)
    if not s or s.get("ma50") is None or s.get("ma200") is None:
        return None
    parts: list[tuple[str, float, float, dict]] = []  # (key, points, max, reason)
    p, m50, m200 = s["price"], s["ma50"], s["ma200"]

    # Trend
    if p > m50 > m200:
        t, why = 30, ("Tren naik utuh: harga di atas rata-rata 50 dan 200 hari.", "Uptrend intact: price above its 50 and 200-day averages.")
    elif p > m200:
        t, why = 18, ("Masih di atas rata-rata 200 hari, tapi jangka pendek melemah.", "Still above its 200-day average, but weaker short term.")
    elif p > m50:
        t, why = 12, ("Mulai naik dari bawah, tapi tren panjang masih turun.", "Turning up from below, but the long trend is still down.")
    else:
        t, why = 4, ("Tren turun: harga di bawah rata-rata 50 dan 200 hari.", "Downtrend: price below its 50 and 200-day averages.")
    parts.append(("trend", t, 30, {"id": why[0], "en": why[1]}))

    # Chance of a rise over the next month
    if p_up is not None:
        c = 20 * _clip((p_up - 0.40) / 0.25)
        parts.append(("chance", c, 20, {"id": f"Peluang naik sebulan ke depan {p_up * 100:.0f}%.",
                                        "en": f"Chance of a rise over the next month: {p_up * 100:.0f}%."}))

    # Broker and foreign flow (Indonesian stocks with Stockbit)
    b, fr = (sbt or {}).get("bandar") or {}, (sbt or {}).get("foreign") or {}
    flow_pts, flow_max, flow_why = 0.0, 0.0, []
    if b.get("label"):
        flow_max += 15
        flow_pts += 7.5 + 3.75 * _clip(b.get("side", 0), -2, 2)
        flow_why.append(("bandar " + b["label"], "brokers " + b["label"]))
    nf = fr.get("net_foreign")
    if nf is not None and s.get("avg_value"):
        flow_max += 10
        flow_pts += 5 + 5 * _clip(nf / (2 * s["avg_value"]), -1, 1)
        flow_why.append((("asing beli bersih" if nf > 0 else "asing jual bersih") + " sebulan",
                         ("foreigners net bought" if nf > 0 else "foreigners net sold") + " over a month"))
    if flow_max:
        parts.append(("flow", flow_pts, flow_max, {"id": "Aliran dana: " + ", ".join(w[0] for w in flow_why) + ".",
                                                   "en": "Money flow: " + ", ".join(w[1] for w in flow_why) + "."}))

    # Value
    fund = fund or {}
    pe_s = fund.get("trailingPeRatio") or []
    if len(pe_s) >= 3 and pe_s[-1]["value"] and pe_s[-1]["value"] > 0:
        pe, avg = pe_s[-1]["value"], sum(x["value"] for x in pe_s) / len(pe_s)
        v = 15 * _clip((1.3 - pe / avg) / 0.5)
        r = pe / avg
        word = (("Murah dibanding biasanya", "Cheap for this stock") if r < 0.85 else
                ("Mahal dibanding biasanya", "Expensive for this stock") if r > 1.3 else ("Harga wajar", "Fairly priced"))
        parts.append(("value", v, 15, {"id": f"{word[0]}: P/E {pe:.1f}, rata-ratanya {avg:.1f}.",
                                       "en": f"{word[1]}: P/E {pe:.1f}, its average {avg:.1f}."}))

    # Calm: not overheated, not wild
    rsi, vr = s.get("rsi"), s.get("vol_ratio")
    if rsi is not None:
        calm = 10.0
        if rsi > 70:
            calm -= 6
        if vr and vr > 1.5:
            calm -= 4
        if rsi < 25:
            calm -= 2
        note = ("Sudah naik terlalu cepat (RSI {:.0f}), rawan koreksi.".format(rsi) if rsi > 70 else
                "Pergerakan sedang jauh lebih liar dari biasanya." if vr and vr > 1.5 else
                "Sudah turun dalam (RSI {:.0f}): bisa memantul, tapi belum tanda berbalik.".format(rsi) if rsi < 30 else
                "Belum terlalu panas (RSI {:.0f}).".format(rsi))
        note_en = (f"Rose too fast (RSI {rsi:.0f}), prone to a pullback." if rsi > 70 else
                   "Swinging much more than usual." if vr and vr > 1.5 else
                   f"Fell hard (RSI {rsi:.0f}): may bounce, but no sign of a turn yet." if rsi < 30 else
                   f"Not overheated (RSI {rsi:.0f}).")
        parts.append(("calm", _clip(calm, 0, 10), 10, {"id": note, "en": note_en}))

    got, most = sum(x[1] for x in parts), sum(x[2] for x in parts)
    sc = round(100 * got / most) if most else 50
    key = "layak" if sc >= LAYAK_AT else "hindari" if sc < HINDARI_BELOW else "tunggu"
    # The reasons that pushed hardest toward the answer: the strongest parts for Layak, the weakest for
    # Hindari, and for Tunggu both sides, because "wait" means the good and the bad roughly cancel.
    best = sorted(parts, key=lambda x: x[1] / x[2], reverse=True)
    if key == "layak":
        picked = best[:3]
    elif key == "hindari":
        picked = best[::-1][:3]
    else:
        picked = [best[-1], best[0]] + [x for x in best[1:-1]][:1]
    reasons = [{"part": k, "share": round(pt / mx, 2), "good": pt / mx >= 0.5, "text": r} for k, pt, mx, r in picked]
    return {"key": asset.key, "verdict": key, "label": dict(zip(("id", "en"), LABELS[key])), "score": sc,
            "parts": {k: {"points": round(pt, 1), "max": mx} for k, pt, mx, _ in parts}, "reasons": reasons,
            "chg1m": s.get("chg1m"), "tested": False, "at": int(time.time())}


def describe(v: dict, lang: str = "id") -> str:
    """One sentence for Telegram or a notification."""
    word = v["label"][lang]
    return (f"{word} (skor {v['score']}/100): " if lang == "id" else f"{word} (score {v['score']}/100): ") + \
        v["reasons"][0]["text"][lang] if v.get("reasons") else word


__all__ = ["score", "describe", "LABELS", "fmt_pct"]
