"""Indonesian market agenda: dates that follow a published, fixed rule, each with why it matters.

Only rules that the institutions publish themselves are used:
- BPS releases monthly inflation on the first working day of the month.
- MSCI's quarterly index reviews take effect after the close of the last business day of February, May, August
  and November.
- IDX reviews its main indices (LQ45, IDX30, IDX80) with changes effective from the first trading day of
  February, May, August and November.
- BI's Board of Governors meeting (RDG) dates are set yearly by BI and do not follow a rule; they are read from
  ARAH_BI_RDG (comma-separated YYYY-MM-DD) and left out when it is empty.

Exchange holidays are not known here, so a date can move a day when it falls on one; each item says "jadwal rutin".
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
QUARTER_MONTHS = (2, 5, 8, 11)

WHY = {
    "bps": ("Inflasi menentukan ruang BI menurunkan atau menaikkan bunga. Inflasi tinggi biasanya menekan saham dan obligasi.",
            "Inflation sets how much room BI has to cut or raise rates. High inflation usually weighs on stocks and bonds."),
    "msci": ("Dana indeks global menyesuaikan porsi saham Indonesia. Saham yang masuk atau keluar indeks MSCI sering bergerak besar.",
             "Global index funds rebalance their Indonesian holdings. Stocks added to or removed from MSCI indices often move sharply."),
    "idx": ("Komposisi LQ45, IDX30 dan IDX80 berubah. Reksa dana indeks membeli saham yang masuk dan menjual yang keluar.",
            "LQ45, IDX30 and IDX80 change members. Index funds buy the stocks added and sell those removed."),
    "rdg": ("Keputusan BI Rate. Bunga turun biasanya mendukung saham dan obligasi; bunga naik menekannya.",
            "The BI Rate decision. A cut usually supports stocks and bonds; a hike weighs on them."),
}


def _workday_on_or_after(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _workday_on_or_before(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _last_day(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def _ts(d: date, hour: int = 9) -> int:
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=WIB).timestamp())


def _item(kind: str, d: date, title: str, hour: int = 9, timed: bool = False) -> dict:
    wid, wen = WHY[kind]
    return {"at": _ts(d, hour), "country": "ID", "title": title, "why": {"id": wid, "en": wen}, "source": "calendar",
            "impact": "High", "timed": timed, "kind": kind, "note": "jadwal rutin"}


def upcoming(now: float | None = None, days: int = 35) -> list[dict]:
    today = datetime.fromtimestamp(now if now is not None else time.time(), WIB).date()
    end = today + timedelta(days=days)
    out: list[dict] = []
    y, m = today.year, today.month
    for i in range(3):  # this month and the next two cover any window up to ~60 days
        yy, mm = y + (m - 1 + i) // 12, (m - 1 + i) % 12 + 1
        out.append(_item("bps", _workday_on_or_after(date(yy, mm, 1)), "Inflasi Indonesia (BPS)"))
        if mm in QUARTER_MONTHS:
            out.append(_item("msci", _workday_on_or_before(_last_day(yy, mm)), "Rebalancing indeks MSCI berlaku"))
            out.append(_item("idx", _workday_on_or_after(date(yy, mm, 1)), "Perubahan anggota LQ45, IDX30, IDX80"))
    for raw in os.environ.get("ARAH_BI_RDG", "").split(","):
        try:
            d = date.fromisoformat(raw.strip())
        except ValueError:
            continue
        # BI announces the decision at about 14.30 WIB on the second day of the meeting.
        out.append(_item("rdg", d, "Keputusan BI Rate (RDG BI)", hour=14, timed=False))
    out = [e for e in out if today <= datetime.fromtimestamp(e["at"], WIB).date() <= end]
    return sorted(out, key=lambda e: e["at"])
