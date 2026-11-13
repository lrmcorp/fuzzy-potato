"""Background jobs: data refresh, forecasts to the ledger, briefs, alerts."""
from __future__ import annotations

import asyncio
import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .agents import get_insight
from .brief import build_brief
from .config import BRIEF_SCHEDULE, DEFAULT_HORIZONS, WEEKLY_OUTLOOK, Settings
from .data.bca import refresh_bca
from .data.calendar import refresh_calendar
from .data.news import refresh_news
from .extras import flips
from .data.yahoo import build_synthetic, refresh_many
from .db import DB
from .outlook import SIMPLE_V, build_simple
from .recommend import build_recs, recs_ok
from .service import record_forecasts, score_forecasts, validation
from .signals import fmt_price
from .telegram import Bot, format_brief, format_report
from .universe import SYNTHETIC, BY_KEY, DEFAULT_LEVELS, GAUGES, MACRO, STOCKS

log = logging.getLogger("arah.runtime")


class Runtime:
    def __init__(self, db: DB, settings: Settings):
        self.db, self.settings = db, settings
        self.bot = Bot(db, settings, on_brief=lambda: self.run_brief("manual", push=False))
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self._lock = asyncio.Lock()
        self._brief_lock = asyncio.Lock()
        self.status: dict = {"data_errors": {}, "last_refresh": 0, "validating": False}

    async def refresh_data(self, stocks: bool = True, force: bool = False) -> None:
        async with self._lock:
            symbols = [a.symbol for a in MACRO + GAUGES]
            errors = await refresh_many(self.db, symbols, force=force)
            if stocks:
                errors |= await refresh_many(self.db, [a.symbol for a in STOCKS], intervals=("1d",), force=force)
            await refresh_bca(self.db)
            for key, (num, den) in SYNTHETIC.items():
                build_synthetic(self.db, BY_KEY[key].symbol, BY_KEY[num].symbol, BY_KEY[den].symbol)
            self.status["data_errors"] = errors
            self.status["last_refresh"] = int(time.time())
            self.db.set("data_status", {"at": self.status["last_refresh"], "errors": errors})

    async def tick(self) -> None:
        """Every 15 minutes: fresh prices, new ledger rows, scores for finished horizons, alerts."""
        await self.refresh_data(stocks=False)
        for a in MACRO:
            try:
                record_forecasts(self.db, a, get_insight(self.db, a.key))
            except Exception:
                log.exception("ledger write failed for %s", a.key)
        score_forecasts(self.db)
        await self.check_alerts()
        await self.ensure_recs()

    async def ensure_recs(self) -> None:
        """Stock picks missing or built without data (a failed download): try again, at most once an hour."""
        if recs_ok(self.db) or time.time() - self.db.get("recs_try_at", 0) < 3600:
            return
        self.db.set("recs_try_at", int(time.time()))
        try:
            await self.refresh_data(stocks=True)
            r = await build_recs(self.db)
            log.info("stock screen rebuilt: %s screened, %s without data", r.get("screened"), r.get("missing"))
        except Exception:
            log.exception("stock screen failed")

    async def daily(self) -> None:
        await self.refresh_data(stocks=True)
        await build_recs(self.db)
        for a in STOCKS:
            try:
                record_forecasts(self.db, a)
            except Exception:
                log.exception("ledger write failed for %s", a.key)

    async def run_brief(self, slot: str, push: bool = True) -> dict:
        async with self._brief_lock:
            old = self.db.latest_report("brief")
            await self.refresh_data(stocks=False)
            try:
                await refresh_news(self.db)
                await refresh_calendar(self.db)
            except Exception:
                log.exception("news or calendar refresh failed")
            if not recs_ok(self.db):
                await self.refresh_data(stocks=True)
                await build_recs(self.db)
            brief = await build_brief(self.db, self.settings, slot=slot)
        lang = self.db.get("lang", "id")
        if push:
            text = format_brief(brief, lang)
            if slot == "weekly":
                text += "\n\n" + format_report(brief.get("report") or {}, lang)
            await self.bot.send(text)
        # An answer that changed is worth a message of its own, whichever brief found it.
        changed = flips(old, brief, lang) if slot != "startup" else []
        if changed:
            head = "<b>Jawaban ARAH berubah</b>" if lang == "id" else "<b>ARAH's answers changed</b>"
            await self.bot.send(head + "\n" + "\n".join(changed))
        return brief

    async def check_alerts(self) -> None:
        self.ensure_level_alerts()
        lang = self.db.get("lang", "id")
        for row in self.db.q("SELECT * FROM alerts WHERE triggered_at IS NULL"):
            asset = BY_KEY.get(row["asset"])
            q = self.db.one("SELECT price FROM quotes WHERE symbol=?", (asset.symbol,)) if asset else None
            if not q or not q["price"]:
                continue
            price = q["price"]
            if (row["op"] == ">" and price > row["level"]) or (row["op"] == "<" and price < row["level"]):
                self.db.x("UPDATE alerts SET triggered_at=?, last_price=? WHERE id=?", (int(time.time()), price, row["id"]))
                d = asset.decimals
                msg = (f"<b>Peringatan:</b> {asset.name} sekarang {fmt_price(asset, price, lang)}, sudah melewati {fmt_price(asset, row['level'], lang)}."
                       if lang == "id" else
                       f"<b>Alert:</b> {asset.name} is now {fmt_price(asset, price, lang)}, past {fmt_price(asset, row['level'], lang)}.")
                await self.bot.send(msg)

    def ensure_level_alerts(self) -> None:
        """Keep one alert per configured level that the price has not reached yet."""
        for key, levels in self.db.get("levels", DEFAULT_LEVELS).items():
            asset = BY_KEY.get(key)
            q = self.db.one("SELECT price FROM quotes WHERE symbol=?", (asset.symbol,)) if asset else None
            if not q or not q["price"]:
                continue
            for lv in levels:
                op = ">" if lv > q["price"] else "<"
                seen = self.db.one("SELECT 1 FROM alerts WHERE asset=? AND level=?", (key, lv))
                if not seen:
                    self.db.x("INSERT INTO alerts (asset, op, level, created_at) VALUES (?,?,?,?)", (key, op, lv, int(time.time())))

    async def validate_all(self) -> None:
        """Walk-forward test for every macro asset and horizon. CPU-heavy, so it runs in a thread."""
        if self.status["validating"]:
            return
        self.status["validating"] = True
        try:
            for a in MACRO:
                for h in DEFAULT_HORIZONS + ["2m", "3m"]:
                    try:
                        await asyncio.to_thread(validation, self.db, a, h, True)
                    except Exception:
                        log.exception("validation failed for %s %s", a.key, h)
        finally:
            self.status["validating"] = False
            self.db.set("validated_at", int(time.time()))

    def _refresh_simple(self) -> None:
        """After an update that changed the summary rules, redo just the summary in the stored brief,
        without the AI team, so the home page follows the new rules straight away."""
        b = self.db.latest_report("brief")
        if not b or (b.get("simple") or {}).get("v") == SIMPLE_V:
            return
        b["simple"] = build_simple(self.db, {})
        b["simple_by_h"] = {h: build_simple(self.db, {}, h) for h in ("2m", "3m")}
        self.db.save_report("brief", b)
        log.info("summary rebuilt under the current rules")

    async def bootstrap(self) -> None:
        """First start: pull history, build the first brief, then test the model in the background."""
        try:
            fresh = time.time() - (self.db.get("data_status") or {}).get("at", 0) < 900
            if not fresh:
                await self.refresh_data(stocks=True)
            if not self.db.latest_report("brief", max_age=6 * 3600):
                await self.run_brief("startup", push=False)
            else:
                await asyncio.to_thread(self._refresh_simple)
            await self.tick()
            # Also when the 2 and 3-month tests have never run (added after the first install).
            if time.time() - self.db.get("validated_at", 0) > 7 * 86400 or self.db.get("bt:IHSG:3m") is None:
                await self.validate_all()
        except Exception:
            log.exception("bootstrap failed")

    def start(self) -> None:
        tz = self.settings.timezone
        self.scheduler.add_job(self.tick, IntervalTrigger(minutes=15), id="tick", max_instances=1, coalesce=True)
        for slot, hhmm in BRIEF_SCHEDULE:
            h, m = hhmm.split(":")
            self.scheduler.add_job(self.run_brief, CronTrigger(hour=int(h), minute=int(m), timezone=tz), args=[slot],
                                   id=f"brief:{slot}", max_instances=1, coalesce=True, misfire_grace_time=1800)
        day, hhmm = WEEKLY_OUTLOOK
        h, m = hhmm.split(":")
        self.scheduler.add_job(self.run_brief, CronTrigger(day_of_week=day, hour=int(h), minute=int(m), timezone=tz),
                               args=["weekly"], id="brief:weekly", misfire_grace_time=3600)
        self.scheduler.add_job(self.daily, CronTrigger(hour=6, minute=40, timezone=tz), id="daily", misfire_grace_time=3600)
        self.scheduler.add_job(self.daily, CronTrigger(hour=17, minute=10, timezone=tz), id="daily_pm", misfire_grace_time=3600)
        self.scheduler.add_job(self.validate_all, CronTrigger(day_of_week="sat", hour=3, timezone=tz), id="validate")
        self.scheduler.start()

