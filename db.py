"""SQLite persistence for RelayPilot.

Tables:
  channel_probes  — scheduled probe results per channel
  usage_windows   — aggregated per-key usage windows (detector input)
  keys            — key registry with quarantine status
  alerts          — alert history (also used for the daily digest)
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS channel_probes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    ts INTEGER NOT NULL,
    latency_ms REAL,
    ok INTEGER NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS usage_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    requests INTEGER NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    top_region TEXT,
    suspicious INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0.0
);
CREATE TABLE IF NOT EXISTS keys (
    key_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    quarantined_at INTEGER,
    quarantine_reason TEXT,
    consecutive_suspicious INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_probes_channel_ts ON channel_probes(channel_id, ts);
CREATE INDEX IF NOT EXISTS idx_windows_key_ts ON usage_windows(key_id, window_start);
"""


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def now_s() -> int:
    return int(time.time())


# --- channel probes -------------------------------------------------------

def record_probe(db_path: str, channel_id: str, channel_name: str,
                 latency_ms: float | None, ok: bool, error: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO channel_probes (channel_id, channel_name, ts, latency_ms, ok, error)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (channel_id, channel_name, now_s(), latency_ms, int(ok), error),
        )


def latest_probes(db_path: str) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM channel_probes WHERE id IN "
            "(SELECT MAX(id) FROM channel_probes GROUP BY channel_id)"
        ).fetchall()
        return [dict(r) for r in rows]


# --- keys -----------------------------------------------------------------

def upsert_key(db_path: str, key_id: str, channel_id: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO keys (key_id, channel_id) VALUES (?, ?)"
            " ON CONFLICT(key_id) DO UPDATE SET channel_id=excluded.channel_id",
            (key_id, channel_id),
        )


def get_key(db_path: str, key_id: str) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM keys WHERE key_id=?", (key_id,)).fetchone()
        return dict(row) if row else None


def list_keys(db_path: str) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM keys ORDER BY key_id")]


def mark_quarantined(db_path: str, key_id: str, reason: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE keys SET status='quarantined', quarantined_at=?, quarantine_reason=?,"
            " consecutive_suspicious=0 WHERE key_id=?",
            (now_s(), reason, key_id),
        )


def bump_suspicious(db_path: str, key_id: str) -> int:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE keys SET consecutive_suspicious=consecutive_suspicious+1 WHERE key_id=?",
            (key_id,),
        )
        row = conn.execute(
            "SELECT consecutive_suspicious FROM keys WHERE key_id=?", (key_id,)
        ).fetchone()
        return int(row["consecutive_suspicious"]) if row else 0


def reset_suspicious(db_path: str, key_id: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE keys SET consecutive_suspicious=0 WHERE key_id=?", (key_id,))


# --- usage windows --------------------------------------------------------

def record_window(db_path: str, *, key_id: str, channel_id: str, window_start: int,
                  window_seconds: int, requests: int, tokens_in: int, tokens_out: int,
                  top_region: str | None, suspicious: bool, score: float) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage_windows (key_id, channel_id, window_start, window_seconds,"
            " requests, tokens_in, tokens_out, top_region, suspicious, score)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key_id, channel_id, window_start, window_seconds, requests,
             tokens_in, tokens_out, top_region, int(suspicious), score),
        )


def recent_windows(db_path: str, key_id: str, limit: int = 12) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM usage_windows WHERE key_id=? ORDER BY window_start DESC LIMIT ?",
            (key_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# --- alerts ---------------------------------------------------------------

def record_alert(db_path: str, severity: str, title: str, body: str,
                 delivered: bool = False) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO alerts (ts, severity, title, body, delivered) VALUES (?, ?, ?, ?, ?)",
            (now_s(), severity, title, body, int(delivered)),
        )


def alerts_since(db_path: str, since_ts: int) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE ts >= ? ORDER BY ts", (since_ts,)
        ).fetchall()
        return [dict(r) for r in rows]
