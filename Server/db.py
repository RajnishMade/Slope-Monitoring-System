"""
db.py
SQLite layer for the slope-stability platform.

Two tables:
  slopes   — one row per slope created via "Current Slope Status" (Option 1).
             Holds the 9 baseline model features, the baseline FoS and the
             user-defined FoS alert threshold, keyed by a unique Slope ID.
  readings — time series of FoS predictions (manual / simulated / esp32),
             one row per prediction, linked to a slope.

One connection per call (safe across FastAPI's threadpool workers).
"""

import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoring.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS slopes (
    slope_id     TEXT PRIMARY KEY,
    name         TEXT,
    created_ts   TEXT NOT NULL,
    params_json  TEXT NOT NULL,       -- 9 baseline model features
    baseline_fos REAL NOT NULL,
    threshold    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS readings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slope_id     TEXT NOT NULL,
    ts           TEXT NOT NULL,       -- ISO-8601 UTC
    source       TEXT NOT NULL,       -- manual | simulated | esp32
    sensors_json TEXT,                -- raw sensor payload
    water_level  REAL,                -- dynamic model input
    seismic_kh   REAL,                -- dynamic model input
    fos          REAL NOT NULL,
    status       TEXT NOT NULL,       -- STABLE | WARNING | ALERT
    alert        INTEGER NOT NULL     -- 0/1
);
CREATE INDEX IF NOT EXISTS idx_readings_slope ON readings (slope_id, id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# ------------------------------- slopes -------------------------------

def next_slope_id() -> str:
    """SLOPE-001, SLOPE-002, ... based on the current max numeric suffix."""
    with _connect() as conn:
        ids = [r["slope_id"] for r in conn.execute("SELECT slope_id FROM slopes").fetchall()]
    n = 0
    for sid in ids:
        try:
            n = max(n, int(sid.split("-")[-1]))
        except (ValueError, IndexError):
            pass
    return f"SLOPE-{n + 1:03d}"


def create_slope(slope: dict) -> None:
    row = {
        "slope_id": slope["slope_id"],
        "name": slope.get("name") or slope["slope_id"],
        "created_ts": now_iso(),
        "params_json": json.dumps(slope["params"]),
        "baseline_fos": slope["baseline_fos"],
        "threshold": slope["threshold"],
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO slopes (slope_id, name, created_ts, params_json, baseline_fos, threshold)
               VALUES (:slope_id, :name, :created_ts, :params_json, :baseline_fos, :threshold)""",
            row,
        )


def _slope_from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["params"] = json.loads(d.pop("params_json"))
    return d


def get_slope(slope_id: str):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM slopes WHERE slope_id = ?", (slope_id,)).fetchone()
        return _slope_from_row(row) if row else None


def list_slopes() -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM slopes ORDER BY slope_id").fetchall()
        return [_slope_from_row(r) for r in rows]


def update_threshold(slope_id: str, threshold: float) -> None:
    with _connect() as conn:
        conn.execute("UPDATE slopes SET threshold = ? WHERE slope_id = ?", (threshold, slope_id))


def delete_slope(slope_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM readings WHERE slope_id = ?", (slope_id,))
        conn.execute("DELETE FROM slopes WHERE slope_id = ?", (slope_id,))


# ------------------------------ readings ------------------------------

def insert_reading(r: dict) -> int:
    row = dict(r)
    row["sensors_json"] = json.dumps(r.get("sensors", {}))
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO readings
               (slope_id, ts, source, sensors_json, water_level, seismic_kh, fos, status, alert)
               VALUES (:slope_id, :ts, :source, :sensors_json, :water_level, :seismic_kh, :fos, :status, :alert)""",
            row,
        )
        return cur.lastrowid


def _reading_from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["sensors"] = json.loads(d.pop("sensors_json") or "{}")
    return d


def latest_reading(slope_id: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM readings WHERE slope_id = ? ORDER BY id DESC LIMIT 1", (slope_id,)
        ).fetchone()
        return _reading_from_row(row) if row else None


def recent_readings(slope_id: str, limit: int = 120):
    """Most recent `limit` readings, oldest-first (for the FoS-vs-time chart)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM readings WHERE slope_id = ? ORDER BY id DESC LIMIT ?", (slope_id, limit)
        ).fetchall()
        return [_reading_from_row(r) for r in reversed(rows)]
