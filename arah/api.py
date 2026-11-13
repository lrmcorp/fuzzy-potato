from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import mimetypes
import os
import secrets
import time
from contextlib import asynccontextmanager
from html import escape as html_escape
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .agents import analyze_asset, ask, get_insight
from .extras import ask_context, calc, weekly_report
from .config import BRIEF_SCHEDULE, DEFAULT_HORIZONS, Settings, get_settings, parse_horizon
from .data.news import COUNTRY_TOPICS, top_stories
from .data.yahoo import fetch_fundamentals, load_bars, refresh_many
from .live import Live
from .outlook import build_simple
from .techniques import techniques
from .db import DB
from .llm import budget_state, claude_calls_today
from .runtime import Runtime
from .service import all_horizons, build_view, forecast_asset, horizon_name, record_summary, track_record, validation
from .signals import snapshot
from . import notif, panel, push
from .data import agenda_id
from . import verdict_rules as rules
from .signals import id_numbers
from .simulate import simulate_capital
from .recommend import PROFILES, VERDICTS_V, order_picks, picks_summary
from .universe import HEADLINE_KEYS, BY_KEY, COUNTRIES, CRYPTO, COMMODITIES, DEFAULT_LEVELS, FX, INDICES, STOCKS, resolve

log = logging.getLogger("arah.api")
STATIC = Path(__file__).parent / "static"
mimetypes.add_type("application/manifest+json", ".webmanifest")
COOKIE = "arah_session"
# The owner stays signed in on their own devices; each visit pushes the expiry out again.
SESSION_DAYS = 180


def _sign(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_token(secret: str) -> str:
    exp = str(int(time.time()) + SESSION_DAYS * 86400)
    return f"{exp}.{_sign(secret, exp)}"


def valid_token(secret: str, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, _sign(secret, exp))


def _id_text(v):
    """Indonesian number format for every Indonesian text in a stored brief ({"id": ..., "en": ...} pairs), so a
    brief written before the format rule still reads 5.311,36 and 1,2%."""
    if isinstance(v, dict):
        out = {k: _id_text(x) for k, x in v.items()}
        if isinstance(v.get("id"), str) and "en" in v:
            out["id"] = id_numbers(v["id"])
        return out
    if isinstance(v, list):
        return [_id_text(x) for x in v]
    return v


class ProfileBody(BaseModel):
    profile: str


class LoginBody(BaseModel):
    password: str = Field(max_length=200)


class SettingsBody(BaseModel):
    lang: str | None = Field(default=None, pattern="^(id|en)$")
    levels: dict[str, list[float]] | None = None


class AskBody(BaseModel):
    question: str = Field(min_length=5, max_length=400)


class WatchBody(BaseModel):
    key: str = Field(max_length=20)
    on: bool = True


class LevelIn(BaseModel):
    level: float = Field(gt=0)
    label: str | None = Field(default=None, max_length=40)


class AlertBatch(BaseModel):
    asset: str = Field(max_length=20)
    levels: list[LevelIn] = Field(default_factory=list, max_length=6)
    verdict_change: bool = False


class SessionBody(BaseModel):
    value: str = Field(min_length=20, max_length=20000)


class TelegramBody(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=3000)


class AlertBody(BaseModel):
    asset: str = Field(max_length=20)
    op: str = Field(pattern="^[<>]$")
    level: float = Field(gt=0)


def create_app(settings: Settings | None = None, db: DB | None = None, background: bool = True) -> FastAPI:
    settings = settings or get_settings()
    db = db or DB(settings.db_path)
    secret = settings.secret or db.get("secret") or secrets.token_hex(32)
    if not settings.secret and not db.get("secret"):
        db.set("secret", secret)
    # Sessions are signed with the password mixed in, so changing the password signs every device out.
    secret = hmac.new(secret.encode(), settings.password.encode(), hashlib.sha256).hexdigest()
    rt = Runtime(db, settings)
    live = Live(db)
    tasks: list[asyncio.Task] = []
    login_fails: dict[str, list[float]] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if background:
            rt.start()
            tasks.append(asyncio.create_task(rt.bootstrap()))
            tasks.append(asyncio.create_task(rt.bot.poll_forever()))
        yield
        for t in tasks:
            t.cancel()
        if background:
            rt.scheduler.shutdown(wait=False)

    app = FastAPI(title="ARAH", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.rt, app.state.db = rt, db

    def auth(request: Request) -> None:
        if settings.password and not valid_token(secret, request.cookies.get(COOKIE)):
            raise HTTPException(401, "login required")

    def asset_or_404(key: str):
        a = resolve(key)
        if not a:
            raise HTTPException(404, "unknown asset")
        return a

    def horizon_or_400(text: str, asset) -> str:
        try:
            return parse_horizon(text, asset.days_per_week)[2]
        except ValueError as e:
            raise HTTPException(400, str(e))

    def set_session(request: Request, response: Response) -> None:
        response.set_cookie(COOKIE, make_token(secret), max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")

    @app.get("/api/session")
    def session(request: Request, response: Response):
        authed = not settings.password or valid_token(secret, request.cookies.get(COOKIE))
        if authed and settings.password:
            set_session(request, response)
        return {"auth_required": bool(settings.password), "authed": authed,
                "lang": db.get("lang", "id"), "version": __version__}

    @app.post("/api/login")
    def login(body: LoginBody, request: Request, response: Response):
        ip = request.client.host if request.client else "?"
        recent = [t for t in login_fails.get(ip, []) if time.time() - t < 600]
        if len(recent) >= 8:
            raise HTTPException(429, "too many attempts; wait ten minutes")
        if not settings.password or not hmac.compare_digest(body.password.encode(), settings.password.encode()):
            login_fails[ip] = recent + [time.time()]
            raise HTTPException(401, "wrong password")
        set_session(request, response)
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/brief", dependencies=[Depends(auth)])
    def brief():
        b = db.latest_report("brief")
        if b:
            # Indonesian routine dates (BPS inflation, MSCI and IDX index changes, BI meetings) join the calendar.
            b = {**b, "events": sorted((b.get("events") or []) + agenda_id.upcoming(), key=lambda e: e["at"])}
        err = db.get("llm_error") if settings.llm_enabled else None
        if b:
            b = _id_text(b)
        return {"brief": b, "building": rt._brief_lock.locked(), "llm_error": (err or {}).get("kind"),
                "llm_enabled": settings.llm_enabled,
                # The 1-month forecasts for the headline markets, judged after the month has passed.
                "record": record_summary(db, "1m", HEADLINE_KEYS)}

    @app.get("/api/panel", dependencies=[Depends(auth)])
    def panel_data():
        """Ringkasan extras: foreign flow, commodities and macro, each with its source and time."""
        return panel.summary(db)

    @app.post("/api/brief/run", dependencies=[Depends(auth)])
    async def brief_run():
        if rt._brief_lock.locked():
            return {"started": False, "building": True}
        tasks.append(asyncio.create_task(rt.run_brief("manual", push=False)))
        return {"started": True, "building": True}

    @app.get("/api/markets", dependencies=[Depends(auth)])
    def markets(group: str = "fx", horizon: str = "1w"):
        groups = {"fx": FX, "index": INDICES, "commodity": COMMODITIES + CRYPTO,
                  "stock_id": [a for a in STOCKS if a.country == "ID"], "stock_us": [a for a in STOCKS if a.country == "US"]}
        if group not in groups:
            raise HTTPException(400, "unknown group")
        rows, snaps = [], {}
        verdicts = verdict_items()
        for a in groups[group]:
            h = horizon_or_400(horizon, a)
            v = build_view(db, a, h, insight=get_insight(db, a.key), with_chart=False, snaps=snaps)
            if v.get("error"):
                continue
            s = snapshot(db, a) or {}
            rows.append({"key": a.key, "name": a.name, "name_en": a.nm("en"), "decimals": a.decimals, "unit": a.unit, "up_is": a.up_is,
                         "price": v["forecast"]["s0"], "chg1d": v["snapshot"]["chg1d"], "chg1w": v["snapshot"]["chg1w"],
                         "direction": v["direction"], "p_up": v["forecast"]["p_up"], "q05": v["forecast"]["q05"],
                         "q95": v["forecast"]["q95"], "vigilance": v["vigilance"], "spark": s.get("spark", [])[-40:],
                         "klass": a.klass, "score": (verdicts.get(a.key) or {}).get("score"), "src": s.get("src"), "chg1m": s.get("chg1m"),
                         "tag": (rules.tag(verdicts[a.key]["verdict"]) if a.key in verdicts and verdicts[a.key].get("verdict") in rules.ACTIONS else None)
                         if a.klass == "stock" else rules.tag(rules.direction_range(v["forecast"]["p_up"], v["forecast"]["q05"], v["forecast"]["q95"], v["forecast"]["s0"]))})
        return {"group": group, "horizon": horizon, "rows": rows}

    @app.get("/api/live/{key}", dependencies=[Depends(auth)])
    async def live_prices(key: str):
        a = asset_or_404(key)
        try:
            return await live.get(a)
        except Exception as e:
            log.warning("live data failed for %s: %s", a.key, e)
            raise HTTPException(503, "live prices unavailable right now")

    @app.get("/api/forecast/{key}", dependencies=[Depends(auth)])
    async def forecast(key: str, h: str = Query("1m", pattern="^[1-9][0-9]?[dwm]$")):
        a = asset_or_404(key)
        h = horizon_or_400(h, a)
        if a.klass == "stock":
            await fetch_fundamentals(db, a.symbol)
        try:
            out = await asyncio.to_thread(techniques, db, a, h)
        except ValueError as e:
            raise HTTPException(400, str(e))
        out["name"], out["name_en"], out["up_is"], out["klass"], out["country"] = a.name, a.nm("en"), a.up_is, a.klass, a.country
        out["horizon_name"] = horizon_name(h)
        return out

    @app.get("/api/simple", dependencies=[Depends(auth)])
    def simple(h: str = Query("1m", pattern="^(1d|1w|[123]m)$")):
        b = db.latest_report("brief") or {}
        if h == "1m" and b.get("simple"):
            return b["simple"]
        if (b.get("simple_by_h") or {}).get(h):
            return b["simple_by_h"][h]
        return build_simple(db, {}, h)

    @app.get("/api/asset/{key}", dependencies=[Depends(auth)])
    async def asset(key: str, horizon: str = "1w"):
        a = asset_or_404(key)
        h = horizon_or_400(horizon, a)
        if a.klass == "stock":
            # Stocks only get daily bars in the background; hourly ones are pulled when someone looks.
            await refresh_many(db, [a.symbol], intervals=("1h",))
        ins = get_insight(db, a.key)
        view = build_view(db, a, h, insight=ins)
        if view.get("error"):
            raise HTTPException(404, view["error"])
        view["horizons"] = all_horizons(db, a, ins)
        view["debate"] = (ins or {}).get("debate")
        view["sources"] = (ins or {}).get("sources", [])
        view["llm_enabled"] = settings.llm_enabled
        return view

    @app.post("/api/asset/{key}/analyze", dependencies=[Depends(auth)])
    async def analyze(key: str):
        a = asset_or_404(key)
        if not settings.llm_enabled:
            raise HTTPException(409, "no LLM provider configured")
        ins = await analyze_asset(db, settings, a)
        if ins is None:
            raise HTTPException(502, "analysis unavailable (budget reached or the model returned nothing usable)")
        return {"ok": True}

    @app.get("/api/calc", dependencies=[Depends(auth)])
    def calculator(amount: float = Query(gt=0, le=1e15), currency: str = Query(pattern="^(USD|CNY|SGD|JPY|EUR)$")):
        out = calc(db, amount, currency)
        if not out:
            raise HTTPException(503, "no rate available for that currency yet")
        return out

    @app.post("/api/ask", dependencies=[Depends(auth)])
    async def ask_question(body: AskBody):
        if not settings.llm_enabled:
            raise HTTPException(409, "no LLM provider configured")
        out = await ask(db, settings, body.question.strip(), ask_context(db, db.latest_report("brief")))
        if not out:
            raise HTTPException(502, "no usable answer")
        return out

    @app.get("/api/recs", dependencies=[Depends(auth)])
    def recs():
        r = db.latest_report("recs") or {"ID": [], "US": [], "screened": {"ID": 0, "US": 0}, "at": None}
        r["record"] = picks_summary(db)
        r["profile"] = db.get("risk_profile")
        vs = verdict_items()
        for m in ("ID", "US"):
            for c in r.get(m, []):
                v = vs.get(c["key"]) or {}
                c["tag"] = rules.tag(rules.pick_status(c, v["verdict"])) if v.get("verdict") in rules.ACTIONS else None
                c["score"] = v.get("score")
            # New picks in the order the owner's risk profile asks for; earlier picks still tracked stay last.
            r[m] = order_picks([c for c in r.get(m, []) if not c.get("held")], r["profile"]) + [c for c in r.get(m, []) if c.get("held")]
        return r

    @app.get("/api/simulate", dependencies=[Depends(auth)])
    def simulate(capital: float = Query(..., gt=0, le=1e13), market: str = Query("ID", pattern="^(ID|US)$")):
        """Simulasi modal: today's picks for this capital and the model's ranges in rupiah."""
        r = recs()
        return simulate_capital(db, r, capital, market, r.get("profile"))

    @app.get("/api/push/prefs", dependencies=[Depends(auth)])
    def push_prefs():
        return {"prefs": notif.prefs(db), "kinds": [{"key": k, "title": t, "text": x} for k, (t, x) in notif.KINDS.items()],
                "devices": len(push.subscriptions(db)), "last": db.get("push_last")}

    @app.post("/api/push/prefs", dependencies=[Depends(auth)])
    def push_prefs_set(body: dict):
        return {"prefs": notif.set_prefs(db, body or {})}

    @app.get("/api/profile", dependencies=[Depends(auth)])
    def profile_get():
        return {"profile": db.get("risk_profile"), "options": list(PROFILES)}

    @app.post("/api/profile", dependencies=[Depends(auth)])
    def profile_set(body: ProfileBody):
        p = body.profile
        if p not in PROFILES:
            raise HTTPException(400, "unknown profile")
        db.set("risk_profile", p)
        return {"profile": p}

    @app.get("/api/news", dependencies=[Depends(auth)])
    def news(country: str = "ID"):
        topics = COUNTRY_TOPICS.get(country.upper())
        if not topics:
            raise HTTPException(400, "unknown country")
        return {"country": country.upper(), "items": top_stories(db, topics, limit=30)}

    @app.get("/api/track", dependencies=[Depends(auth)])
    def track():
        tests = []
        for a in FX + INDICES + COMMODITIES + CRYPTO:
            row = {"key": a.key, "name": a.name, "name_en": a.nm("en"), "horizons": {}}
            for h in DEFAULT_HORIZONS:
                v = validation(db, a, h)
                if v and v.get("enough"):
                    row["horizons"][h] = {k: v[k] for k in ("grade", "n", "hit_rate", "cover90", "cover50", "skill_vs_base")}
                elif v:
                    row["horizons"][h] = {"grade": "insufficient", "n": v.get("n", 0)}
            tests.append(row)
        return {"live": track_record(db), "report": weekly_report(db), "tests": tests, "validating": rt.status["validating"],
                "validated_at": db.get("validated_at")}

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        ds = db.get("data_status") or {}
        rec = db.latest_report("recs") or {}
        return {"version": __version__, "revision": os.environ.get("ARAH_REVISION", ""),
                "recs": {"at": rec.get("at"), "screened": rec.get("screened"), "missing": rec.get("missing")},
                "data_at": ds.get("at"), "data_errors": ds.get("errors", {}),
                "news_at": db.get("news_at"), "llm_enabled": settings.llm_enabled, "llm_error": db.get("llm_error"),
                "models": settings.llm_names, "llm_last": db.get("llm_last"), "claude_calls_today": claude_calls_today(db),
                "budget": budget_state(db, settings), "telegram_enabled": settings.telegram_enabled,
                "stockbit": live.stockbit.status(),
                "schedule": [{"slot": s, "time": t} for s, t in BRIEF_SCHEDULE], "timezone": settings.timezone}

    @app.get("/api/stockbit/{key}", dependencies=[Depends(auth)])
    async def stockbit_terminal(key: str):
        """Bandar detector, foreign flow, insider filings and stream posts for one Indonesian stock."""
        from .data import sbterm

        a = asset_or_404(key)
        if a.country != "ID" or a.klass not in ("stock", "index"):
            raise HTTPException(404, "only for Indonesian stocks")
        if not live.stockbit.status().get("usable"):
            raise HTTPException(409, "Stockbit is not configured")
        return await sbterm.snapshot(db, live.stockbit, a.key)

    def quick_row(a, verdicts: dict) -> dict:
        """One line about an asset for search results, the watchlist and alerts: price, today's change,
        a 3-month line, and the action (stocks) or the forecast direction (everything else)."""
        s = snapshot(db, a) or {}
        row = {"key": a.key, "name": a.name, "name_en": a.nm("en"), "klass": a.klass, "country": a.country, "unit": a.unit,
               "decimals": a.decimals, "up_is": a.up_is, "price": s.get("live") or s.get("price"), "chg1d": s.get("chg1d"),
               "spark": (s.get("spark") or [])[-60:], "tag": None, "src": s.get("src"), "chg1m": s.get("chg1m")}
        if a.klass == "stock":
            v = verdicts.get(a.key)
            if v and v.get("verdict") in rules.ACTIONS:
                row["tag"] = rules.tag(v["verdict"])
        elif s:
            try:
                _, f1, _ = forecast_asset(db, a, "1m")
                row["tag"] = rules.tag(rules.direction_range(f1.p_up, f1.q05, f1.q95, f1.s0))
            except ValueError:
                pass
        return row

    def verdict_items() -> dict:
        v = db.get("verdicts") or {}
        return v.get("items") or {} if v.get("v") == VERDICTS_V else {}

    @app.get("/api/search", dependencies=[Depends(auth)])
    def search(q: str = Query("", max_length=40)):
        """Tickers first (exact code, then code or name starting with the words, then containing them)."""
        needle = q.strip().lower()
        if not needle:
            return {"q": q, "items": []}
        pool = [a for a in BY_KEY.values() if a.klass != "gauge"]
        def rank(a):
            k, n = a.key.lower(), a.name.lower()
            if k == needle.replace("/", ""):
                return 0
            if k.startswith(needle) or n.startswith(needle):
                return 1
            if needle in k or needle in n or any(w.startswith(needle) for w in n.split()):
                return 2
            return 9
        hits = sorted((a for a in pool if rank(a) < 9), key=lambda a: (rank(a), a.key))[:8]
        vs = verdict_items()
        return {"q": q, "items": [quick_row(a, vs) for a in hits]}

    @app.get("/api/watchlist", dependencies=[Depends(auth)])
    def watchlist():
        vs = verdict_items()
        counts = {r["asset"]: r["n"] for r in db.q("SELECT asset, COUNT(*) n FROM alerts WHERE triggered_at IS NULL AND kind='price' GROUP BY asset")}
        rows = []
        for k in db.get("watchlist", []):
            if k in BY_KEY:
                rows.append(quick_row(BY_KEY[k], vs) | {"alerts": counts.get(k, 0)})
        return {"items": rows}

    @app.post("/api/watchlist", dependencies=[Depends(auth)])
    def watch(body: WatchBody):
        a = asset_or_404(body.key)
        keys = [k for k in db.get("watchlist", []) if k != a.key]
        if body.on:
            keys.insert(0, a.key)
            # Watching a stock also means "tell me when ARAH's decision on it changes".
            if a.klass == "stock" and not db.one("SELECT 1 FROM alerts WHERE asset=? AND kind='verdict'", (a.key,)):
                db.x("INSERT INTO alerts (asset, op, level, created_at, kind, label) VALUES (?,?,?,?,?,?)",
                     (a.key, "=", 0, int(time.time()), "verdict", "Keputusan ARAH berubah"))
        db.set("watchlist", keys[:40])
        return {"items": keys[:40], "on": body.on}

    @app.get("/api/plan/{key}", dependencies=[Depends(auth)])
    async def trade_plan(key: str):
        """Levels for the alert sheet: the pick's trade plan when there is one, else the forecast's 9-in-10 range."""
        a = asset_or_404(key)
        s = snapshot(db, a) or {}
        price = s.get("live") or s.get("price")
        recs = db.latest_report("recs") or {}
        card = next((c for m in ("ID", "US") for c in recs.get(m, []) if c.get("key") == a.key), None)
        levels = []
        if card and card.get("plan"):
            p = card["plan"]
            levels = [{"level": p["stop"], "label": "Batas rugi", "kind": "stop"},
                      {"level": p["targets"][0], "label": "Target 1", "kind": "target"},
                      {"level": p["targets"][1], "label": "Target 2", "kind": "target"}]
        else:
            try:
                _, f1, _ = await asyncio.to_thread(forecast_asset, db, a, "1m")
                levels = [{"level": f1.q05, "label": "Batas bawah 9 dari 10", "kind": "band"},
                          {"level": f1.q95, "label": "Batas atas 9 dari 10", "kind": "band"}]
            except ValueError:
                levels = []
        return {"key": a.key, "name": a.name, "klass": a.klass, "price": price, "decimals": a.decimals, "unit": a.unit,
                "from_plan": bool(card and card.get("plan")), "plan": card.get("plan") if card else None, "levels": levels}

    @app.post("/api/alerts/batch", dependencies=[Depends(auth)])
    def add_alerts(body: AlertBatch):
        """Several alerts from one sheet, as one group so a single "Batalkan" removes them all.
        The direction of each price alert follows from the current price."""
        a = asset_or_404(body.asset)
        s = snapshot(db, a) or {}
        price = s.get("live") or s.get("price")
        if not price:
            raise HTTPException(409, "no current price for this asset")
        grp = secrets.token_hex(6)
        now = int(time.time())
        n = 0
        for lv in body.levels:
            if lv.level <= 0 or abs(lv.level - price) < 1e-9:
                continue
            db.x("INSERT INTO alerts (asset, op, level, created_at, kind, grp, label) VALUES (?,?,?,?,?,?,?)",
                 (a.key, ">" if lv.level > price else "<", lv.level, now, "price", grp, (lv.label or "")[:40]))
            n += 1
        if body.verdict_change and not db.one("SELECT 1 FROM alerts WHERE asset=? AND kind='verdict'", (a.key,)):
            db.x("INSERT INTO alerts (asset, op, level, created_at, kind, grp, label) VALUES (?,?,?,?,?,?,?)",
                 (a.key, "=", 0, now, "verdict", grp, "Keputusan ARAH berubah"))
            n += 1
        if not n:
            raise HTTPException(400, "nothing to set")
        return {"group": grp, "count": n}

    @app.delete("/api/alerts/group/{grp}", dependencies=[Depends(auth)])
    def undo_alerts(grp: str):
        db.x("DELETE FROM alerts WHERE grp=?", (grp[:20],))
        return alerts()

    @app.post("/api/stockbit/session", dependencies=[Depends(auth)])
    def stockbit_session(body: SessionBody):
        """Reconnect Stockbit from the web: the owner pastes a fresh credentialStorage value."""
        from .data.stockbit import parse_session

        sess = parse_session(body.value.strip())
        if not sess:
            raise HTTPException(400, "that is not a Stockbit session value")
        db.set("stockbit_session", sess)
        db.set("stockbit_error", None)
        return live.stockbit.status()

    @app.post("/api/ask/telegram", dependencies=[Depends(auth)])
    async def ask_to_telegram(body: TelegramBody):
        if not settings.telegram_enabled:
            raise HTTPException(409, "Telegram is not connected")
        ok = await rt.bot.send(f"<b>Tanya ARAH:</b> {html_escape(body.question)}\n\n{html_escape(body.answer)}")
        if not ok:
            raise HTTPException(502, "Telegram did not accept the message")
        return {"sent": True}

    @app.get("/api/verdict/{key}", dependencies=[Depends(auth)])
    async def stock_verdict(key: str):
        """The action for one stock (Masuk, Masuk bertahap, Tunggu, Hindari), fresh, with its three main reasons."""
        from .verdict import score

        a = asset_or_404(key)
        if a.klass != "stock":
            raise HTTPException(404, "verdicts are for stocks")
        fund = await fetch_fundamentals(db, a.symbol)
        sbt = None
        if a.country == "ID":
            sbt = {k: (db.get(f"sbt:{k}:{a.key}") or {}).get("v") for k in ("bandar", "foreign")}
        try:
            _, f1, _ = await asyncio.to_thread(forecast_asset, db, a, "1m")
        except ValueError:
            raise HTTPException(409, "not enough history yet")
        v = score(db, a, f1.p_up, fund, sbt)
        if not v:
            raise HTTPException(409, "not enough history yet")
        return v

    @app.get("/api/history/{key}", dependencies=[Depends(auth)])
    def price_history(key: str, range: str = Query("3m", pattern="^(1w|1m|3m|6m|1y|5y)$")):
        """Daily candles for the detail chart's longer ranges."""
        a = asset_or_404(key)
        days = {"1w": 7, "1m": 31, "3m": 92, "6m": 183, "1y": 366, "5y": 1830}[range]
        b = load_bars(db, a.symbol, "1d", 2000)
        since = time.time() - days * 86400
        bars = [{"t": int(t), "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v)}
                for t, o, h, l, c, v in zip(b["ts"], b["o"], b["h"], b["l"], b["c"], b["v"]) if t >= since]
        return {"key": a.key, "range": range, "decimals": a.decimals, "unit": a.unit, "bars": bars}

    @app.get("/api/feed", dependencies=[Depends(auth)])
    def news_feed(scope: str = Query("ID", pattern="^(ID|US|ASIA|GLOBAL)$"), topic: str | None = Query(None, max_length=20)):
        """Ranked stories for one region, optionally one topic, with the desk's summary on top."""
        groups = {"ID": COUNTRY_TOPICS["ID"] + ["id_flow"], "US": COUNTRY_TOPICS["US"],
                  "ASIA": COUNTRY_TOPICS["JP"] + COUNTRY_TOPICS["SG"] + COUNTRY_TOPICS["CN"], "GLOBAL": COUNTRY_TOPICS["GLOBAL"]}
        topics = groups[scope]
        if topic:
            if topic not in topics:
                raise HTTPException(400, "unknown topic for this region")
            topics = [topic]
        brief = db.latest_report("brief") or {}
        desks = {c: (brief.get("countries") or {}).get(c) for c in ({"ASIA": ["JP", "SG", "CN"]}.get(scope) or [scope])}
        return {"scope": scope, "topics": groups[scope], "items": top_stories(db, topics, limit=40, max_age_h=72),
                "desks": [{"country": c, "summary": d.get("summary"), "mood": d.get("mood"), "events": d.get("events", [])}
                          for c, d in desks.items() if d and d.get("summary")]}

    @app.get("/api/feed/{key}", dependencies=[Depends(auth)])
    async def ticker_feed(key: str):
        """News for one asset: its own headlines (refreshed at most every 30 minutes) and, for an Indonesian
        stock, the busiest Stockbit posts about it."""
        from .data import sbterm
        from .data.news import refresh_ticker_news

        a = asset_or_404(key)
        if time.time() - (db.get(f"tnews_at:{a.key}") or 0) > 1800:
            db.set(f"tnews_at:{a.key}", int(time.time()))
            try:
                await refresh_ticker_news(db, a.key, a.name, a.country)
            except Exception as e:  # the feed is a bonus; the page must still load
                log.info("ticker news %s failed: %s", a.key, e)
        posts = []
        if a.country == "ID" and a.klass in ("stock", "index") and live.stockbit.status().get("usable"):
            posts = await sbterm.stream(db, live.stockbit, a.key) or []
        return {"key": a.key, "items": top_stories(db, [f"t:{a.key}"], limit=20, max_age_h=24 * 7), "posts": posts}

    @app.get("/api/push/key", dependencies=[Depends(auth)])
    def push_key():
        from . import push
        return {"key": push.public_key(db), "devices": len(push.subscriptions(db)), "last": db.get("push_last")}

    @app.post("/api/push/subscribe", dependencies=[Depends(auth)])
    async def push_subscribe(request: Request):
        from . import push
        try:
            n = push.subscribe(db, await request.json())
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e))
        await push.notify(db, "ARAH", "Notifikasi aktif. Anda akan diberi tahu saat harga melewati batas.", "/#/peringatan", "welcome")
        return {"devices": n}

    @app.post("/api/push/unsubscribe", dependencies=[Depends(auth)])
    async def push_unsubscribe(request: Request):
        from . import push
        body = await request.json()
        push.unsubscribe(db, str((body or {}).get("endpoint", "")))
        return {"devices": len(push.subscriptions(db))}

    @app.post("/api/push/test", dependencies=[Depends(auth)])
    async def push_test():
        from . import push
        if time.time() - (db.get("push_test_at") or 0) < 30:
            raise HTTPException(429, "wait a moment")
        db.set("push_test_at", int(time.time()))
        return {"sent": await push.notify(db, "ARAH: tes", "Notifikasi berfungsi.", "/#/peringatan", "test")}

    @app.get("/api/probe/stockbit", dependencies=[Depends(auth)])
    async def stockbit_probe(path: str | None = Query(None, max_length=300)):
        """Shapes of Stockbit's answers (no values), for the signed-in owner, to choose parameters.
        At most one run per minute: each run makes about 16 paced requests to Stockbit."""
        from .probe import probe_lines

        if time.time() - (db.get("probe_at") or 0) < 60:
            raise HTTPException(429, "one probe per minute")
        db.set("probe_at", int(time.time()))
        if not live.stockbit.session:
            raise HTTPException(409, "Stockbit is not configured")
        return {"lines": await probe_lines(live.stockbit, [path] if path else None)}

    @app.get("/api/pulse", dependencies=[Depends(auth)])
    def pulse():
        """Polled by every page: how fresh the data is, and how many alerts are active (for the nav badge).

        live     Stockbit answers: Indonesian prices are realtime; shown as the time only.
        delayed  Stockbit is not connected: Indonesian prices come about 15 minutes late.
        paused   No data refresh for more than a day: signals are paused and verdicts greyed out.
        """
        ds = db.get("data_status") or {}
        at = ds.get("at")
        sb = live.stockbit.status()
        err = sb.get("error") or {}
        if not at or time.time() - at > 86400:
            state = "paused"
        elif sb.get("usable") and not err:
            state = "live"
        else:
            state = "delayed"
        n = db.one("SELECT COUNT(*) n FROM alerts WHERE triggered_at IS NULL")["n"]
        return {"state": state, "at": at, "since": err.get("at"), "stockbit": bool(sb.get("configured")), "delay_min": 15,
                "idx": panel.idx_session(),
                "alerts_active": n, "telegram": settings.telegram_enabled}

    @app.get("/api/settings", dependencies=[Depends(auth)])
    def get_prefs():
        return {"lang": db.get("lang", "id"), "levels": db.get("levels", DEFAULT_LEVELS),
                "countries": COUNTRIES, "assets": [{"key": a.key, "name": a.name} for a in FX + INDICES + COMMODITIES + CRYPTO + STOCKS]}

    @app.put("/api/settings", dependencies=[Depends(auth)])
    def put_prefs(body: SettingsBody):
        if body.lang:
            db.set("lang", body.lang)
        if body.levels is not None:
            clean = {}
            for k, vals in body.levels.items():
                if k in BY_KEY:
                    clean[k] = sorted({float(v) for v in vals if v > 0})[:6]
            db.set("levels", clean)
        return get_prefs()

    @app.get("/api/alerts", dependencies=[Depends(auth)])
    def alerts():
        rows = db.q("SELECT * FROM alerts ORDER BY triggered_at IS NOT NULL, id DESC LIMIT 60")
        return {"items": [dict(r) | {"name": BY_KEY[r["asset"]].name, "decimals": BY_KEY[r["asset"]].decimals, "unit": BY_KEY[r["asset"]].unit}
                          for r in rows if r["asset"] in BY_KEY]}

    @app.post("/api/alerts", dependencies=[Depends(auth)])
    def add_alert(body: AlertBody):
        a = asset_or_404(body.asset)
        db.x("INSERT INTO alerts (asset, op, level, created_at) VALUES (?,?,?,?)", (a.key, body.op, body.level, int(time.time())))
        return alerts()

    @app.delete("/api/alerts/{alert_id}", dependencies=[Depends(auth)])
    def del_alert(alert_id: int):
        db.x("DELETE FROM alerts WHERE id=?", (alert_id,))
        return alerts()

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "internal error"}, status_code=500)

    if (STATIC / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (STATIC / path).resolve()
            if path and f.is_file() and STATIC.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(STATIC / "index.html")

    return app
