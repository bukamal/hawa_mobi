# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import sqlite3
from database.connection import get_local_db_path


class LocalNotificationRepository:
    """Device-local schedule ledger. It is intentionally never sent to REST."""

    @staticmethod
    def _connect():
        conn = sqlite3.connect(get_local_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn


    def get_setting(self, key: str, default=None):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))

    def list_all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM local_notification_schedule ORDER BY scheduled_at ASC, id ASC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_by_key(self, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM local_notification_schedule WHERE notification_key=?", (key,)
            ).fetchone()
            return dict(row) if row else None

    def upsert(self, item, *, status: str, last_error: str | None = None):
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO local_notification_schedule(
                       notification_key, notification_id, expense_id, reminder_id, kind,
                       scheduled_at, title, body, payload, channel_id, status,
                       last_error, created_at, updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(notification_key) DO UPDATE SET
                       notification_id=excluded.notification_id,
                       expense_id=excluded.expense_id,
                       reminder_id=excluded.reminder_id,
                       kind=excluded.kind,
                       scheduled_at=excluded.scheduled_at,
                       title=excluded.title,
                       body=excluded.body,
                       payload=excluded.payload,
                       channel_id=excluded.channel_id,
                       status=excluded.status,
                       last_error=excluded.last_error,
                       updated_at=excluded.updated_at""",
                (
                    item.key, item.notification_id, item.expense_id, item.reminder_id,
                    item.kind, item.scheduled_at.isoformat(timespec="seconds"), item.title,
                    item.body, item.payload, item.channel_id, status, last_error, now, now,
                ),
            )

    def remove(self, key: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM local_notification_schedule WHERE notification_key=?", (key,))

    def mark_opened(self, notification_id: int):
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE local_notification_schedule SET status='opened', opened_at=?, updated_at=? WHERE notification_id=?",
                (now, now, int(notification_id)),
            )

    def is_dirty(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM notification_state WHERE key='financial_dirty'"
            ).fetchone()
            return not row or str(row[0]) == "1"

    def set_dirty(self, dirty: bool = True):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO notification_state(key,value,updated_at)
                   VALUES('financial_dirty',?,CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
                ("1" if dirty else "0",),
            )
