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
