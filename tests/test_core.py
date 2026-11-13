import numpy as np
import pytest

from arah.config import parse_horizon
from arah.data.news import parse_rss
from arah.data.yahoo import spike_mask
from arah.forecast.backtest import grade, walk_forward
from arah.forecast.engine import direction_of, simulate, tilt_to_drift
from arah.recommend import idx_tick
from arah.universe import resolve


def series(n=900, vol=0.01, drift=0.0, seed=1):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


def test_parse_horizon_presets_and_custom():
    assert parse_horizon("1w") == ("1d", 5, "1w")
    assert parse_horizon("1w", days_per_week=7) == ("1d", 7, "1w")
    assert parse_horizon("6h") == ("1h", 6, "6h")
    assert parse_horizon("3d") == ("1d", 3, "3d")
    for bad in ("", "abc", "0d", "99h", "400d", "-1w"):
        with pytest.raises(ValueError):
            parse_horizon(bad)


def test_resolve_aliases():
    assert resolve("usd/idr").key == "USDIDR"
    assert resolve("bbca.jk").key == "BBCA"
    assert resolve("emas").key == "GOLD"
    assert resolve("nonsense") is None


def test_simulate_is_roughly_fair_without_drift():
    f = simulate(series(), 10, seed=3)
    assert 0.45 < f.p_up < 0.55
    assert f.q05 < f.q25 < f.q50 < f.q75 < f.q95
    assert len(f.band) == 10


def test_touch_probability_orders_by_distance():
    c = series()
    s0 = c[-1]
    f = simulate(c, 10, levels=[s0 * 1.01, s0 * 1.05, s0 * 1.5, s0 * 0.99], seed=3)
    t = list(f.touch.values())
    assert t[0] > t[1] > t[2]
    assert t[2] < 0.01
    assert t[3] > 0.3
    # Touching a level is at least as likely as closing beyond it.
    assert t[0] >= 0.3


def test_tilt_moves_probability_by_about_the_requested_amount():
    c = series()
    base = simulate(c, 5, seed=7)
    extra = tilt_to_drift(base.p_up, base.p_up + 0.06, base.vol_step, 5)
    tilted = simulate(c, 5, seed=7, extra_drift_total=extra)
    assert 0.03 < tilted.p_up - base.p_up < 0.10


def test_stale_quotes_do_not_fake_a_direction():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.002, 900)
    r[rng.random(900) < 0.6] = 0.0
    c = 18000 * np.exp(np.cumsum(r))
    base = simulate(c, 1, seed=1)
    pushed = simulate(c, 1, seed=1, extra_drift_total=tilt_to_drift(0.5, 0.56, base.vol_step, 1))
    assert pushed.p_up < 0.75


def test_direction_thresholds():
    assert direction_of(0.6) == "up" and direction_of(0.4) == "down" and direction_of(0.52) == "flat"


def test_spike_mask_catches_bad_ticks_and_keeps_real_moves():
    c = series(400, vol=0.003)
    bad = c.copy()
    bad[200] = bad[200] / 100
    bad[300:304] = bad[300:304] * 0.965
    mask = spike_mask(bad)
    assert mask[200] and mask[300:304].all() and mask.sum() == 5
    real = c.copy()
    real[250:] *= 0.9  # a level shift that never comes back is real
    assert not spike_mask(real).any()


def test_walk_forward_ranges_are_calibrated_on_a_random_walk():
    res = walk_forward(series(1600, seed=5), 5, n_paths=500, max_origins=150)
    assert res["enough"]
    assert 0.80 <= res["cover90"] <= 0.97
    assert grade(res) in ("range_only", "validated", "experimental")
    assert grade({"enough": False}) == "insufficient"


def test_parse_rss_strips_publisher_and_survives_garbage():
    xml = """<rss><channel><item><title>Rupiah melemah - Kontan</title><source>Kontan</source>
    <link>https://x.test/a</link><pubDate>Thu, 12 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    items = parse_rss(xml)
    assert items[0]["title"] == "Rupiah melemah" and items[0]["published_at"] > 0
    assert parse_rss("<not xml") == []


def test_idx_tick_table():
    assert idx_tick(150) == 1 and idx_tick(450) == 2 and idx_tick(1500) == 5 and idx_tick(4000) == 10 and idx_tick(9000) == 25


def test_bca_parse_takes_erate_and_rejects_bad_rows():
    from arah.data.bca import parse

    html = '''
      <a data-value-buy="18172.00-18010.00-18010.00" data-value-sell="18282.00-18290.00-18290.00" data-text=USD>USD</a>
      <a data-value-buy="2698.47-2639.21-0" data-value-sell="2764.06-2807.97-0" data-text=CNH>CNH</a>
      <a data-value-buy="18172.00-1-1" data-value-sell="18282.00-1-1" data-text=USD>duplicate, ignored</a>
      <a data-value-buy="100.00-1-1" data-value-sell="90.00-1-1" data-text=XXX>sell below buy</a>
      <a data-value-buy="1.00-1-1" data-value-sell="1.00-1-1" data-text=IDR>IDR</a>'''
    rates = parse(html)
    assert rates == {"USD": {"buy": 18172.0, "sell": 18282.0}, "CNH": {"buy": 2698.47, "sell": 2764.06}}
    assert parse("<html>nothing here</html>") == {}


def test_calendar_keeps_high_impact_and_merges_twins():
    from arah.data.calendar import pick

    raw = [
        {"title": "CPI m/m", "country": "USD", "date": "2026-11-10T08:30:00-05:00", "impact": "High"},
        {"title": "Core CPI m/m", "country": "USD", "date": "2026-11-10T08:30:00-05:00", "impact": "High"},
        {"title": "Fed speaker", "country": "USD", "date": "2026-11-11T08:30:00-05:00", "impact": "Medium"},
        {"title": "BOJ Policy Rate", "country": "JPY", "date": "2026-11-12T00:00:00-05:00", "impact": "Medium"},
        {"title": "ECB Main Refinancing Rate", "country": "EUR", "date": "2026-11-12T00:00:00-05:00", "impact": "High"},
        {"title": "German ZEW", "country": "EUR", "date": "2026-11-12T01:00:00-05:00", "impact": "Medium"},
        {"title": "Something", "country": "AUD", "date": "2026-11-12T00:00:00-05:00", "impact": "High"},
        {"title": "Broken date", "country": "USD", "date": "soon", "impact": "High"},
        "not a dict",
    ]
    events = pick(raw)
    assert [e["title"] for e in events] == ["CPI m/m, Core CPI m/m", "BOJ Policy Rate", "ECB Main Refinancing Rate"]
    assert events[2]["country"] == "EU"
    assert events[0]["country"] == "US" and "inflasi" in events[0]["why"]["id"].lower()
    assert pick({"oops": 1}) == []


def test_stockbit_session_parsing_and_read_only_guard():
    import json
    from urllib.parse import quote

    from arah.data.stockbit import is_read_path, parse_session, token_exp

    def jwt(exp):
        import base64
        body = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
        return f"eyJhbGciOiJSUzI1NiJ9.{body}.c2ln"

    cookie = quote(json.dumps({"state": {"access": {"token": jwt(100)}, "refresh": {"token": jwt(200)}}}))
    s = parse_session(cookie)
    assert token_exp(s["access"]) == 100 and token_exp(s["refresh"]) == 200
    assert parse_session(jwt(300)) == {"access": "", "refresh": jwt(300)}
    assert parse_session("not a token") is None
    assert is_read_path("/charts/BBCA/daily?timeframe=1d")
    assert is_read_path("/company-price-feed/v2/orderbook/companies/BBCA")
    for bad in ("/order/buy", "/charts/../order/buy", "/charts/%2e%2e/order", "/login/refresh"):
        assert not is_read_path(bad)


def test_technique_helpers_vote_sensibly():
    import numpy as np

    from arah.techniques import _analog_at, _analog_index, _revert_votes, _trend_votes, _weight

    up = np.exp(np.linspace(0, 1, 400)) * 100
    tv, _ = _trend_votes(up)
    assert tv[-1] == 1 and tv[100] == 0  # no vote before the 200-day average exists
    base = np.full(300, 100.0) * np.exp(np.random.default_rng(1).normal(0, 0.01, 300))
    stretched = np.r_[base, base[-1] * np.linspace(1, 1.25, 8)[1:]]
    assert _revert_votes(stretched)[0][-1] == -1  # far above its 50-day average: expect a pull back
    assert _revert_votes(base)[0][-1] == 0
    c = 100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.01, 900)))
    vote, strength, med, paths = _analog_at(c, _analog_index(c), len(c) - 1, 21)
    assert vote in (-1, 0, 1) and len(paths) == 20 and all(len(p) == 22 for p in paths)
    assert _weight({"n_eff": 40, "hit": 0.60, "chance": 0.52}, 0) > 0
    assert _weight({"n_eff": 40, "hit": 0.75, "chance": 0.75}, 0) == 0  # right only as often as luck
    assert _weight({"n_eff": 5, "hit": 0.9, "chance": 0.5}, 0) == 0
    assert _weight(None, 0.25) == 0.25



def test_frankfurter_parse_keeps_valid_days():
    from arah.data.frankfurter import parse

    data = {"rates": {"2026-11-11": {"IDR": 18210.5}, "2026-11-10": {"IDR": 18190}, "bad": {"IDR": 1}, "2026-11-12": {"IDR": None}}}
    rows = parse(data, "IDR")
    assert [v for _, v in rows] == [18190.0, 18210.5]
    assert rows[1][0] - rows[0][0] == 86400 and rows[0][0] % 86400 == 0


def test_relay_is_used_only_when_fully_set(monkeypatch):
    import importlib

    from arah.data import relay

    try:
        monkeypatch.setenv("ARAH_RELAY_URL", "https://arah-relay.example.workers.dev/")
        monkeypatch.setenv("ARAH_RELAY_KEY", "k" * 32)
        importlib.reload(relay)
        assert relay.base("yahoo", "https://query1.finance.yahoo.com") == "https://arah-relay.example.workers.dev/yahoo"
        assert relay.headers() == {"x-relay-key": "k" * 32}
        monkeypatch.setenv("ARAH_RELAY_KEY", "short")  # a weak key leaves the relay off
        importlib.reload(relay)
        assert not relay.ON and relay.headers() == {}
        assert relay.base("stockbit", "https://exodus.stockbit.com") == "https://exodus.stockbit.com"
    finally:
        monkeypatch.delenv("ARAH_RELAY_URL", raising=False)
        monkeypatch.delenv("ARAH_RELAY_KEY", raising=False)
        importlib.reload(relay)
    # Without the relay, both clients talk to the sites directly and never send a relay key.
    from arah.data import stockbit, yahoo
    assert yahoo.BASE == "https://query1.finance.yahoo.com" and "x-relay-key" not in yahoo.HEADERS
    assert stockbit.EXODUS == "https://exodus.stockbit.com"


def test_top_stories_merges_one_story_and_ranks_by_outlets(tmp_path):
    import time as _t

    from arah.data.news import _store, top_stories
    from arah.db import DB

    db = DB(tmp_path / "n.db")
    now = int(_t.time())
    same = "Asing borong saham bank besar usai rebalancing MSCI"
    _store(db, "id_insider", "ID", [
        {"title": same, "source": "Kontan", "url": "u1", "published_at": now - 3600},
        {"title": same + " pekan ini", "source": "Bisnis.com", "url": "u2", "published_at": now - 1800},
        {"title": "Asing borong saham bank besar setelah rebalancing MSCI", "source": "CNBC Indonesia", "url": "u3",
         "published_at": now - 600},
    ])
    _store(db, "id_market", "ID", [{"title": "Video: lomba lari pagi di Jakarta", "source": "", "url": "u4", "published_at": now}])
    top = top_stories(db, ["id_insider", "id_market"], limit=5)
    # The unnamed source is hidden; the three listed outlets make one story.
    assert top[0]["outlets"] == 3 and "MSCI" in top[0]["title"] and len(top) == 1 and top[0]["tier"] == 1


def test_verdict_rules_follow_the_approved_thresholds():
    from arah.verdict_rules import action, direction, text_tag

    assert action(70, 0.60) == "masuk" and action(85, 0.59) == "bertahap"
    assert action(69, 0.70) == "tunggu" and action(None, 0.7) == "tunggu" and action(80, None) == "tunggu"
    assert action(39, 0.70) == "hindari" and action(90, 0.40) == "hindari"
    assert direction(0.61) == "naik" and direction(0.5) == "datar" and direction(0.38) == "turun"
    assert text_tag("bertahap") == "◐ Masuk bertahap"


def test_news_tiers_hide_unlisted_sources_and_can_be_configured(tmp_path, monkeypatch):
    import time as _t

    from arah.data.news import _store, top_stories
    from arah.db import DB

    db = DB(tmp_path / "n.db")
    now = int(_t.time())
    _store(db, "id_market", "ID", [
        {"title": "IHSG ditutup menguat tajam sore ini", "source": "Kontan", "url": "a", "published_at": now},
        {"title": "Saham teknologi dunia bergerak liar hari ini", "source": "Blog Saham Acak", "url": "b", "published_at": now},
        {"title": "Rupiah melemah terhadap dolar Amerika Serikat", "source": "Reuters", "url": "c", "published_at": now},
    ])
    got = {s["source"]: s["tier"] for s in top_stories(db, ["id_market"])}
    assert got == {"Kontan": 1, "Reuters": 2}
    monkeypatch.setenv("ARAH_NEWS_TIER2", "blog saham acak")
    got = {s["source"]: s["tier"] for s in top_stories(db, ["id_market"])}
    assert got == {"Kontan": 1, "Blog Saham Acak": 2}


def test_ai_text_numbers_become_indonesian():
    from arah.signals import id_numbers

    assert id_numbers("IHSG naik 4.4% ke 5,311.36") == "IHSG naik 4,4% ke 5.311,36"
    assert id_numbers("Net buy Rp 1,234 miliar, yield 4.25%") == "Net buy Rp 1.234 miliar, yield 4,25%"
    # Already Indonesian, years and clock times stay as they are.
    assert id_numbers("Rupiah Rp18.250 per dolar, naik 2,5% pada 2026") == "Rupiah Rp18.250 per dolar, naik 2,5% pada 2026"
    assert id_numbers("Rilis 20.30 WIB") == "Rilis 20.30 WIB"


def test_story_cluster_lists_sources_impact_and_tickers(tmp_path):
    import time as _t

    from arah.data.news import _store, impact, tickers, top_stories
    from arah.db import DB

    db = DB(tmp_path / "n.db")
    now = int(_t.time())
    same = "Asing jual bersih BBRI dan Telkom usai rebalancing MSCI"
    _store(db, "id_flow", "ID", [
        {"title": same, "source": "Reuters", "url": "a1", "published_at": now - 900},
        {"title": same + " hari ini", "source": "Kontan", "url": "a2", "published_at": now - 600},
        {"title": "Asing jual bersih BBRI dan Telkom setelah rebalancing MSCI", "source": "CNBC Indonesia", "url": "a3",
         "published_at": now - 300},
    ])
    top = top_stories(db, ["id_flow"])
    assert len(top) == 1 and top[0]["outlets"] == 3
    # Tier 1 outlets first, then tier 2; each named once.
    assert top[0]["sources"] == ["CNBC Indonesia", "Kontan", "Reuters"]
    assert top[0]["impact"] == "negatif" and top[0]["tickers"] == ["BBRI", "TLKM"]

    # Phrases outrank single words: a rate cut is good news although it "falls".
    assert impact("BI pangkas suku bunga, IHSG menguat") == "positif"
    assert impact("Suku bunga turun 25 bps") == "positif" and impact("Inflasi naik ke 3,1%") == "negatif"
    assert impact("RUPS tahunan digelar pekan depan") == "netral"
    # Short US codes such as V or MA are only matched by name; four-letter codes need capitals.
    assert tickers("Visa and Mastercard settle") == ["MA"] and tickers("bbca naik") == [] and tickers("BBCA naik") == ["BBCA"]


def test_indonesian_agenda_follows_published_rules(monkeypatch):
    from datetime import date, datetime

    from arah.data import agenda_id

    monkeypatch.setenv("ARAH_BI_RDG", "2026-11-19, bukan-tanggal")
    now = datetime(2026, 11, 13, 10, tzinfo=agenda_id.WIB).timestamp()
    got = {e["kind"]: datetime.fromtimestamp(e["at"], agenda_id.WIB).date() for e in agenda_id.upcoming(now, days=80)}
    # 30 Nov 2026 is the last business day of November; 1 Dec 2026 a Tuesday; 1 Jan 2027 a Friday (no holiday list).
    assert got["msci"] == date(2026, 11, 30) and got["rdg"] == date(2026, 11, 19)
    items = agenda_id.upcoming(now, days=80)
    bps = [datetime.fromtimestamp(e["at"], agenda_id.WIB).date() for e in items if e["kind"] == "bps"]
    assert bps == [date(2026, 12, 1), date(2027, 1, 1)]
    assert all(e["why"]["id"] and e["note"] == "jadwal rutin" and e["country"] == "ID" for e in items)
    # Index changes take effect on the first trading day of February: 1 Feb 2027 is a Monday.
    later = datetime(2027, 1, 20, tzinfo=agenda_id.WIB).timestamp()
    assert {e["kind"]: datetime.fromtimestamp(e["at"], agenda_id.WIB).date() for e in agenda_id.upcoming(later)}["idx"] == date(2027, 2, 1)


def test_one_outlet_counts_once_and_record_low_is_negative(tmp_path):
    import time as _t

    from arah.data.news import _store, impact, top_stories
    from arah.db import DB

    db = DB(tmp_path / "n.db")
    now = int(_t.time())
    t = "IHSG ditutup menguat 135 poin sore ini"
    _store(db, "id_market", "ID", [{"title": t, "source": "ANTARA News", "url": "b1", "published_at": now - 60},
                                   {"title": t, "source": "ANTARA Foto", "url": "b2", "published_at": now - 30}])
    top = top_stories(db, ["id_market"])
    assert top[0]["outlets"] == 1 and top[0]["sources"] == ["ANTARA News"]
    assert impact("Rupiah cetak rekor penutupan terendah") == "negatif"
    assert impact("Delapan saham terdepak dari indeks MSCI") == "negatif"


def test_same_move_in_different_words_is_one_story(tmp_path):
    import time as _t

    from arah.data.news import _store, top_stories
    from arah.db import DB

    db = DB(tmp_path / "n.db")
    now = int(_t.time())
    _store(db, "id_market", "ID", [
        {"title": "IHSG Ditutup Rebound 2,66% Pasca Review MSCI November 2026, Tren Pemulihan Berlanjut?", "source": "kontan.co.id", "url": "c1", "published_at": now - 300},
        {"title": "IHSG Melonjak 2,66% Jadi 5.250 Hari Kamis (12/11), Ada Net Buy Asing di Saham Ini", "source": "Pusat Data Kontan", "url": "c2", "published_at": now - 200},
        {"title": "IHSG Naik 2,66 Persen di Tengah Gejolak Politik dan Evaluasi Indeks MSCI", "source": "Kompas.com", "url": "c3", "published_at": now - 100},
        {"title": "IHSG Naik 1,10 Persen Ditopang Saham Bank", "source": "Kompas.com", "url": "c4", "published_at": now - 50},
        {"title": "Rupiah Kamis kian melemah jadi Rp18.198 per dolar AS", "source": "ANTARA News", "url": "c5", "published_at": now - 40},
    ])
    top = top_stories(db, ["id_market"])
    big = [s for s in top if "2,66" in s["title"]]
    assert len(big) == 1 and big[0]["outlets"] == 2 and big[0]["sources"] == ["Kompas.com", "kontan.co.id"]
    # A different number on the same index is a different story; so is the rupiah.
    assert any("1,10" in s["title"] for s in top) and any("Rupiah" in s["title"] for s in top) and len(top) == 3
