from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .agents import analyze_asset, get_insight
from .config import BRIEF_SCHEDULE, DEFAULT_HORIZONS, Settings, get_settings, parse_horizon
from .data.news import headlines
from .data.yahoo import refresh_many
from .db import DB
from .llm import budget_state, claude_calls_today
from .runtime import Runtime
from .service import all_horizons, build_view, track_record, validation
from .signals import snapshot
from .universe import BY_KEY, COUNTRIES, CRYPTO, COMMODITIES, DEFAULT_LEVELS, FX, INDICES, STOCKS, resolve

log = logging.getLogger("arah.api")
STATIC = Path(__file__).parent / "static"
COOKIE = "arah_session"
SESSION_DAYS = 30


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


class LoginBody(BaseModel):
    password: str = Field(max_length=200)


class SettingsBody(BaseModel):
    lang: str | None = Field(default=None, pattern="^(id|en)$")
    levels: dict[str, list[float]] | None = None


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
    rt = Runtime(db, settings)
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

    @app.get("/api/session")
    def session(request: Request):
        return {"auth_required": bool(settings.password),
                "authed": not settings.password or valid_token(secret, request.cookies.get(COOKIE)),
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
        response.set_cookie(COOKIE, make_token(secret), max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/brief", dependencies=[Depends(auth)])
    def brief():
        b = db.latest_report("brief")
        err = db.get("llm_error") if settings.llm_enabled else None
        return {"brief": b, "building": rt._brief_lock.locked(), "llm_error": (err or {}).get("kind")}

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
        for a in groups[group]:
            h = horizon_or_400(horizon, a)
            v = build_view(db, a, h, insight=get_insight(db, a.key), with_chart=False, snaps=snaps)
            if v.get("error"):
                continue
            s = snapshot(db, a) or {}
            rows.append({"key": a.key, "name": a.name, "name_en": a.nm("en"), "decimals": a.decimals, "up_is": a.up_is,
                         "price": v["forecast"]["s0"], "chg1d": v["snapshot"]["chg1d"], "chg1w": v["snapshot"]["chg1w"],
                         "direction": v["direction"], "p_up": v["forecast"]["p_up"], "q05": v["forecast"]["q05"],
                         "q95": v["forecast"]["q95"], "vigilance": v["vigilance"], "spark": s.get("spark", [])[-40:]})
        return {"group": group, "horizon": horizon, "rows": rows}

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

    @app.get("/api/recs", dependencies=[Depends(auth)])
    def recs():
        return db.latest_report("recs") or {"ID": [], "US": [], "screened": {"ID": 0, "US": 0}, "at": None}

    @app.get("/api/news", dependencies=[Depends(auth)])
    def news(country: str = "ID"):
        topics = {"ID": ["id_market", "id_politics"], "US": ["us_market", "us_politics"], "JP": ["jp"], "SG": ["sg"],
                  "GLOBAL": ["global"]}.get(country.upper())
        if not topics:
            raise HTTPException(400, "unknown country")
        return {"country": country.upper(), "items": headlines(db, topics, limit=30)}

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
        return {"live": track_record(db), "tests": tests, "validating": rt.status["validating"],
                "validated_at": db.get("validated_at")}

    @app.get("/api/status", dependencies=[Depends(auth)])
    def status():
        ds = db.get("data_status") or {}
        return {"version": __version__, "data_at": ds.get("at"), "data_errors": ds.get("errors", {}),
                "news_at": db.get("news_at"), "llm_enabled": settings.llm_enabled, "llm_error": db.get("llm_error"),
                "models": settings.llm_names, "llm_last": db.get("llm_last"), "claude_calls_today": claude_calls_today(db),
                "budget": budget_state(db, settings), "telegram_enabled": settings.telegram_enabled,
                "schedule": [{"slot": s, "time": t} for s, t in BRIEF_SCHEDULE], "timezone": settings.timezone}

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
        return {"items": [dict(r) | {"name": BY_KEY[r["asset"]].name, "decimals": BY_KEY[r["asset"]].decimals}
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
