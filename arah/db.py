from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
  symbol TEXT NOT NULL, interval TEXT NOT NULL, ts INTEGER NOT NULL,
  o REAL, h REAL, l REAL, c REAL NOT NULL, v REAL,
  PRIMARY KEY (symbol, interval, ts)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS quotes (
  symbol TEXT PRIMARY KEY, price REAL, prev_close REAL, market_ts INTEGER,
  currency TEXT, fetched_at INTEGER
);

CREATE TABLE IF NOT EXISTS news (
  id TEXT PRIMARY KEY, topic TEXT NOT NULL, country TEXT, title TEXT NOT NULL,
  source TEXT, url TEXT, published_at INTEGER, fetched_at INTEGER
);
CREATE INDEX IF NOT EXISTS news_topic_time ON news (topic, published_at DESC);

-- Append-only: rows are written once and only the score columns are filled in later.
CREATE TABLE IF NOT EXISTS forecasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset TEXT NOT NULL, horizon TEXT NOT NULL, interval TEXT NOT NULL, steps INTEGER NOT NULL,
  base_ts INTEGER NOT NULL, made_at INTEGER NOT NULL, s0 REAL NOT NULL,
  p_up_quant REAL NOT NULL, p_up REAL NOT NULL, direction TEXT NOT NULL,
  q05 REAL, q25 REAL, q50 REAL, q75 REAL, q95 REAL,
  touch TEXT, source TEXT NOT NULL,
  scored_at INTEGER, s_t REAL, went_up INTEGER,
  UNIQUE (asset, horizon, base_ts, source)
);
CREATE INDEX IF NOT EXISTS forecasts_open ON forecasts (scored_at, asset);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, key TEXT,
  created_at INTEGER NOT NULL, body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_kind ON reports (kind, key, created_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, asset TEXT NOT NULL, op TEXT NOT NULL,
  level REAL NOT NULL, created_at INTEGER NOT NULL, triggered_at INTEGER, last_price REAL
);

CREATE TABLE IF NOT EXISTS llm_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, model TEXT, role TEXT,
  tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL
);

CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class DB:
    """One SQLite connection guarded by a lock. Enough for a single-user app."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def x(self, sql: str, args: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, args)
            return cur.lastrowid or 0

    def get(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value: Any) -> None:
        self.x(
            "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    def save_report(self, kind: str, body: dict, key: str | None = None) -> int:
        return self.x(
            "INSERT INTO reports (kind, key, created_at, body) VALUES (?, ?, ?, ?)",
            (kind, key, int(time.time()), json.dumps(body, ensure_ascii=False)),
        )

    def latest_report(self, kind: str, key: str | None = None, max_age: int | None = None) -> dict | None:
        if key is None:
            row = self.one("SELECT * FROM reports WHERE kind=? ORDER BY created_at DESC LIMIT 1", (kind,))
        else:
            row = self.one(
                "SELECT * FROM reports WHERE kind=? AND key=? ORDER BY created_at DESC LIMIT 1", (kind, key)
            )
        if not row:
            return None
        if max_age is not None and time.time() - row["created_at"] > max_age:
            return None
        body = json.loads(row["body"])
        body["_id"], body["_created_at"] = row["id"], row["created_at"]
        return body

    def close(self) -> None:
        with self._lock:
            self._conn.close()
