import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from arah import agents
from arah.api import create_app
from arah.config import Settings
from arah.db import DB
from arah.service import build_view, record_forecasts, score_forecasts, track_record
from arah.universe import ALL, BY_KEY


def seed(db: DB, days: int = 700) -> None:
    rng = np.random.default_rng(42)
    now = int(time.time())
    today = now - now % 86400
    with db.tx() as c:
        for a in ALL:
            closes = 1000 * np.exp(np.cumsum(rng.normal(0, 0.01, days)))
            for i, px in enumerate(closes):
                ts = today - (days - 1 - i) * 86400
                c.execute("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?)", (a.symbol, "1d", ts, px, px * 1.01, px * 0.99, px, 1e6))
            c.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?)", (a.symbol, float(closes[-1]), float(closes[-2]), now, "X", now))
        c.execute("INSERT INTO news VALUES ('n1','id_market','ID','Bank Indonesia tahan suku bunga','Kontan','https://x.test/1',?,?)", (now, now))
    db.set("data_status", {"at": now, "errors": {}})


@pytest.fixture
def db(tmp_path):
    d = DB(tmp_path / "t.db")
    seed(d)
    return d


def test_view_has_verdict_reasons_and_levels(db):
    db.set("levels", {"USDIDR": [1010.0, 5000.0]})
    v = build_view(db, BY_KEY["USDIDR"], "2w")
    assert v["direction"] in ("up", "down", "flat")
    assert v["summary"]["id"] and v["summary"]["en"]
    assert "—" not in v["summary"]["id"] + v["summary"]["en"]
    assert len(v["reasons"]) >= 2 and v["history"] and v["forecast"]["band"]
    assert set(v["forecast"]["touch"]) == {"1010", "5000"}
    assert v["vigilance"]["code"] in ("aman", "waspada", "siaga", "bahaya")


def test_ledger_records_once_per_bar_and_scores(db):
    a = BY_KEY["IHSG"]
    first = record_forecasts(db, a)
    assert first >= 5 and record_forecasts(db, a) == 0
    assert score_forecasts(db) == 0
    # Two more daily bars: the one-day forecast is now due.
    last = db.one("SELECT MAX(ts) m, c FROM bars WHERE symbol=? AND interval='1d'", (a.symbol,))
    for k in (1, 2):
        db.x("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?)", (a.symbol, "1d", last["m"] + k * 86400, 1, 1, 1, last["c"] * 1.02, 1))
    assert score_forecasts(db) == 1
    rec = track_record(db)
    assert rec["scored"] == 1 and rec["by_horizon"][2]["n"] == 1


async def test_team_output_is_validated(db, monkeypatch):
    settings = Settings(openrouter_key="test-key")

    async def fake(db_, s_, role, system, user, **kw):
        if role.startswith("desk"):
            return {"summary": {"id": "BI menahan suku bunga — rupiah stabil.", "en": "BI held rates."}, "mood": 1,
                    "events": [{"refs": ["N1"], "what": {"id": "a", "en": "a"}, "effect": {"id": "b", "en": "b"}},
                               {"refs": ["N99"], "what": {"id": "x", "en": "x"}, "effect": {"id": "y", "en": "y"}}]}
        if role.startswith("debate"):
            return {"cases": {"USDIDR": {"id": "kasus", "en": "case"}}}
        return {"headline": {"id": "Dunia tenang.", "en": "The world is calm."},
                "world": {"stance": "mixed", "summary": {"id": "s", "en": "s"}, "points": [{"text": {"id": "p", "en": "p"}, "refs": ["W1"]}]},
                "assets": {"USDIDR": {"tilt": {"short": 0.5, "medium": -0.02, "long": "x"},
                                      "reasons": [{"text": {"id": "r1", "en": "r1"}, "lean": 1, "refs": ["F1"]},
                                                  {"text": {"id": "r2", "en": "r2"}, "lean": -1, "refs": ["DESK.ID"]},
                                                  {"text": {"id": "made up", "en": "made up"}, "lean": 1, "refs": ["F999"]}],
                                      "watch": {"id": "w", "en": "w"}},
                           "IHSG": {"tilt": {}, "reasons": [{"text": {"id": "only", "en": "only"}, "refs": ["Z1"]}]}}}

    monkeypatch.setattr(agents, "chat_json", fake)
    out = await agents.run_team(db, settings)
    desk = out["desks"]["ID"]
    assert "—" not in desk["summary"]["id"]
    assert len(desk["events"]) == 1  # the event citing a headline that does not exist is dropped
    ins = agents.get_insight(db, "USDIDR")
    assert ins["tilt"] == {"short": agents.LLM_TILT_CAP, "medium": -0.02, "long": 0.0}
    assert [r["text"]["id"] for r in ins["reasons"]] == ["r1", "r2"]
    assert agents.get_insight(db, "IHSG") is None  # no valid references, so nothing is stored


def test_api_requires_login_when_password_set(db):
    app = create_app(Settings(password="s3cret", secret="k" * 32), db, background=False)
    c = TestClient(app)
    assert c.get("/api/brief").status_code == 401
    assert c.post("/api/login", json={"password": "nope"}).status_code == 401
    assert c.post("/api/login", json={"password": "s3cret"}).status_code == 200
    assert c.get("/api/brief").status_code == 200
    r = c.get("/api/asset/USDIDR?horizon=3d")
    assert r.status_code == 200 and r.json()["horizon"] == "3d"
    assert c.get("/api/asset/USDIDR?horizon=zzz").status_code == 400
    assert c.get("/api/asset/NOPE").status_code == 404
    assert c.post("/api/alerts", json={"asset": "USDIDR", "op": ">", "level": -5}).status_code == 422
    assert len(c.post("/api/alerts", json={"asset": "usd", "op": ">", "level": 19000}).json()["items"]) == 1
    assert c.get("/api/../arah/config.py").status_code in (200, 404)
    c.post("/api/logout")
    assert c.get("/api/brief").status_code == 401


def test_login_is_rate_limited(db):
    c = TestClient(create_app(Settings(password="pw", secret="k" * 32), db, background=False))
    codes = [c.post("/api/login", json={"password": "bad"}).status_code for _ in range(10)]
    assert codes[:8] == [401] * 8 and codes[-1] == 429


async def test_claude_provider_runs_cli_without_api_key(db, tmp_path, monkeypatch):
    from arah import llm

    fake = tmp_path / "claude"
    # Stand-in for the Claude CLI: reports whether an API key leaked into its environment.
    fake.write_text(
        "#!/bin/sh\ncat > /dev/null\n"
        "if [ \"$1\" = \"-p\" ] && [ -z \"$ANTHROPIC_API_KEY\" ]; then\n"
        "  printf '%s' '{\"is_error\": false, \"result\": \"Here it is: {\\\"ok\\\": true}\", \"usage\": {\"input_tokens\": 5, \"output_tokens\": 3}}'\n"
        "else\n  echo '{\"is_error\": true, \"result\": \"Please run /login\"}'; exit 1\nfi\n")
    fake.chmod(0o755)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-be-used")
    s = Settings(llm_provider="claude", claude_bin=str(fake), openrouter_key="")
    assert s.provider_order == ["claude"] and s.llm_names["provider"] == "claude"
    assert await llm.chat_json(db, s, "t", "sys", "user") == {"ok": True}
    row = db.one("SELECT model, cost_usd FROM llm_usage")
    assert row["model"] == "claude:haiku" and row["cost_usd"] == 0
    with pytest.raises(llm.BudgetExceeded):
        await llm.chat_json(db, Settings(llm_provider="claude", claude_bin=str(fake), claude_calls_day=1), "t", "s", "u")
    broken = Settings(llm_provider="claude", claude_bin=str(fake), claude_quick="x")
    monkeypatch.setattr(llm, "claude_calls_today", lambda d: 0)
    fake.write_text("#!/bin/sh\ncat > /dev/null\necho '{\"is_error\": true, \"result\": \"Please run /login\"}'\nexit 1\n")
    with pytest.raises(llm.LLMError):
        await llm.chat_json(db, broken, "t", "s", "u")
    assert db.get("llm_error")["kind"] == "auth"
    assert not Settings(llm_provider="claude", claude_bin="/nonexistent/claude").llm_enabled


async def test_openrouter_first_then_claude_fallback(db, tmp_path, monkeypatch):
    from arah import llm

    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\ncat > /dev/null\nprintf '%s' '{\"is_error\": false, \"result\": \"{\\\"from\\\": \\\"claude\\\"}\", \"usage\": {}}'\n")
    fake.chmod(0o755)
    s = Settings(llm_provider="openrouter", openrouter_key="k", claude_bin=str(fake))
    assert s.provider_order == ["openrouter", "claude"] and s.llm_names["fallback"] == "claude"
    assert Settings(llm_provider="openrouter", openrouter_key="k", claude_bin=str(fake), llm_fallback=False).provider_order == ["openrouter"]
    calls = []

    async def no_credit(db_, s_, *a):
        calls.append(1)
        db_.set("llm_error", {"at": 0, "kind": "credit"})
        raise llm.LLMError("OpenRouter refused the request (402)")

    monkeypatch.setattr(llm, "_openrouter_json", no_credit)
    assert await llm.chat_json(db, s, "t", "sys", "user") == {"from": "claude"}
    assert db.get("llm_last") == db.get("llm_last") | {"provider": "claude", "fallback": True}
    assert db.get("llm_error") is None
    # OpenRouter is skipped for a while after a credit refusal, so it is not retried on every call.
    assert await llm.chat_json(db, s, "t", "sys", "user") == {"from": "claude"}
    assert len(calls) == 1


def test_answers_have_three_states_and_calculator_uses_bank_rate(db):
    from arah.extras import calc, flips, weekly_report
    from arah.outlook import build_simple

    db.set("bca_rates", {"at": int(time.time()), "rates": {"USD": {"buy": 990.0, "sell": 1010.0}}})
    s = build_simple(db, {})
    cards = [s["indonesia"], s["usd"], s["cny"], *s["abroad"]["countries"]]
    states = ("good", "neutral", "bad")
    assert all(c["now"]["state"] in states and c["next"]["state"] in states for c in cards)
    assert s["abroad"]["now"]["state"] in states and s["abroad"]["next"]["state"] in states
    # The 60/40 rule on the owner's side: "good" needs at least 60%, "bad" at most 40%.
    for c in cards:
        pg = round(c["next"]["p_good"], 2)
        assert c["next"]["state"] == ("good" if pg >= 0.6 else "bad" if pg <= 0.4 else "neutral")
    assert s["usd"]["unit"] == "Rp" and s["indonesia"]["unit"] == ""
    assert "Rp " in s["usd"]["next"]["text"]["id"]
    usd = s["usd"]
    assert usd["price"] == 1000.0 and usd["bca"]["sell"] == 1010.0
    lo, hi = usd["next"]["range"]
    assert lo < 1000.0 < hi
    # The percentage in the sentence is the chance of the side the label picked.
    shown = int(usd["next"]["text"]["en"].split(": ")[1].split("%")[0])
    assert shown >= 50
    c = calc(db, 1_010_000, "USD")
    assert c["source"] == "bca" and c["rate"] == 1010.0 and abs(c["now"] - 1000.0) < 1e-6
    assert c["next_low"] < c["now"] < c["next_high"] and c["plan"] in ("now", "wait", "split")
    assert calc(db, 1000, "XXX") is None
    assert weekly_report(db) == {"days": 7, "total": 0, "right": 0, "wrong": 0}

    old = {"simple": s}
    import copy
    new = copy.deepcopy(old)
    assert flips(old, new, "id") == []
    new["simple"]["usd"]["next"]["state"] = "good" if usd["next"]["state"] != "good" else "bad"
    out = flips(old, new, "en")
    assert len(out) == 1 and "Rupiah vs US dollar" in out[0]
    assert flips(None, new, "id") == []


def test_calc_and_ask_endpoints_validate_input(db):
    c = TestClient(create_app(Settings(password="", secret="k" * 32, openrouter_key="", claude_bin="/nonexistent"), db, background=False))
    assert c.get("/api/calc?amount=1000000&currency=USD").status_code == 200
    assert c.get("/api/calc?amount=-5&currency=USD").status_code == 422
    assert c.get("/api/calc?amount=5&currency=DROP").status_code == 422
    assert c.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert c.post("/api/ask", json={"question": "Bagus tidak ekspansi?"}).status_code == 409


def test_session_slides_and_password_change_signs_out(db):
    app = create_app(Settings(password="first-password-1", secret="k" * 32), db, background=False)
    c = TestClient(app)
    assert c.post("/api/login", json={"password": "first-password-1"}).status_code == 200
    r = c.get("/api/session")
    assert r.json()["authed"] and "arah_session" in r.headers.get("set-cookie", "") and "Max-Age=15552000" in r.headers["set-cookie"]
    cookie = c.cookies.get("arah_session")
    # Same secret, new password: the old cookie no longer opens the door.
    c2 = TestClient(create_app(Settings(password="second-password-2", secret="k" * 32), db, background=False))
    c2.cookies.set("arah_session", cookie)
    assert c2.get("/api/brief").status_code == 401 and not c2.get("/api/session").json()["authed"]


def test_forecast_and_summary_horizons(db):
    from arah.techniques import techniques

    c = TestClient(create_app(Settings(password="", secret="k" * 32), db, background=False))
    for h in ("1m", "2m", "3m"):
        r = c.get(f"/api/forecast/IHSG?h={h}")
        assert r.status_code == 200
        j = r.json()
        assert len(j["techniques"]) == 7 and j["votes"]["up"] + j["votes"]["down"] + j["votes"]["none"] == 7
        cc = j["conclusion"]
        assert cc["q05"] < cc["q50"] < cc["q95"] and abs(j["tilt"]) <= 0.08
        assert "sim" in j["used"] and all(x["purpose"]["id"] and x["status"]["id"] for x in j["techniques"])
        # A technique counts as used only when it gives a view and carries weight.
        assert all(x["key"] == "sim" or (x["vote"] != 0 and x["weight"] > 0) for x in j["techniques"] if x["status"]["used"])
    assert c.get("/api/forecast/IHSG?h=1h").status_code == 422  # hourly horizons are not offered here
    s = c.get("/api/simple?h=3m").json()
    assert s["horizon"] == "3m" and s["indonesia"]["next"]["state"] in ("good", "neutral", "bad")
    assert "3 bulan" in s["indonesia"]["next"]["text"]["id"]
    assert c.get("/api/simple?h=5m").status_code == 422
    assert techniques(db, BY_KEY["SPX"], "2m")["steps"] == 42


def test_number_format_and_units():
    from arah.outlook import next_state
    from arah.signals import fmt_num, fmt_pct, fmt_price
    from arah.universe import BY_KEY

    assert fmt_num(18228.4, 0, "id") == "18,228" and fmt_num(1234.5, 2, "en") == "1,234.50"
    assert fmt_pct(-1.25, "id") == "-1.2%" or fmt_pct(-1.25, "id") == "-1.3%"
    assert fmt_price(BY_KEY["USDIDR"], 18228) == "Rp 18,228"
    assert fmt_price(BY_KEY["BBCA"], 9875) == "Rp 9,875"
    assert fmt_price(BY_KEY["NVDA"], 181.5) == "$ 181.50"
    assert fmt_price(BY_KEY["IHSG"], 5115.04) == "5,115.04"
    assert fmt_price(BY_KEY["USDJPY"], 154.2) == "¥ 154.20"
    # 62% up for IHSG is good; 62% up for USD/IDR (rupiah weakening) is not good; 55% is neutral.
    assert next_state(0.62, BY_KEY["IHSG"]) == "good" and next_state(0.62, BY_KEY["USDIDR"]) == "bad"
    assert next_state(0.55, BY_KEY["IHSG"]) == "neutral" and next_state(0.40, BY_KEY["IHSG"]) == "bad"
