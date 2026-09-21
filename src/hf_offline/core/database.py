"""SQLite core for HF: one local database, WAL + foreign keys + transactions.

Mirrors the reference app's operational discipline (row factory, WAL, FKs,
cache pragmas, a ``transaction()`` context manager) with a lean schema
sized for a workshop tool rather than a full ERP.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per phone/tablet under repair or in the queue. `status` drives
-- the shop board; the full lifecycle history lives in `diagnoses`.
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT UNIQUE,
    imei TEXT,
    imei2 TEXT,
    brand TEXT,
    model TEXT,
    color TEXT,
    os_version TEXT,
    customer_name TEXT,
    customer_phone TEXT,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'in_queue'
        CHECK(status IN ('in_queue','in_repair','diagnosing','done')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A diagnosis session: the plan that was started, when it finished, and its
-- aggregate result. Items (one row per test) hang off this row.
CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    -- JSON list of planned "category|test" entries; defines the total work
    -- so progress = recorded items / plan length even mid-run.
    plan TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    result TEXT CHECK(result IN ('passed','failed','incomplete')),
    summary TEXT
);

-- One row per executed test inside a diagnosis.
CREATE TABLE IF NOT EXISTS diagnosis_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnosis_id INTEGER NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    test_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('passed','failed','warning','na')),
    detail TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER
);

-- Generated print/share artifacts, kept as metadata only (the HTML itself
-- is regenerated from the diagnosis rows on demand — no stale files).
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnosis_id INTEGER REFERENCES diagnoses(id) ON DELETE SET NULL,
    device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_diagnoses_device ON diagnoses(device_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_diagnosis_items_diag ON diagnosis_items(diagnosis_id);
CREATE INDEX IF NOT EXISTS idx_reports_device ON reports(device_id, created_at DESC);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA cache_size = -8000")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('app_name','HF | إتش-إف')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('theme_mode','system')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('accent','default')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('shop_name','ورشة إتش-إف')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('technician_name','المهندس')"
            )
            conn.commit()

    def schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            return int(row[0]) if row else 0

    def integrity_check(self) -> str:
        with self.connect() as conn:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])

    def checkpoint(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


__all__ = ["Database", "SCHEMA_VERSION"]
