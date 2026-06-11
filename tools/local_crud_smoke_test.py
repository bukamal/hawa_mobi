# -*- coding: utf-8 -*-
"""Local CRUD smoke tests for the accounting core.

Run from project root:
    python tools/local_crud_smoke_test.py

The test uses a temporary database directory and does not touch production data.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def reset_singleton() -> None:
    from database.connection import DatabaseConnection
    try:
        DatabaseConnection().close()
    except Exception:
        pass
    DatabaseConnection._instance = None
    DatabaseConnection._local_conn = None


def assert_one(conn: sqlite3.Connection, sql: str, params=()) -> sqlite3.Row:
    row = conn.execute(sql, params).fetchone()
    assert row is not None, f"Expected one row for: {sql} {params}"
    return row


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hawaa_crud_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)

    try:
        reset_singleton()
        from database.migrations import init_database
        from database.connection import DatabaseConnection, get_local_db_path
        from database.repositories.expense_repo import ExpenseRepository

        init_database()
        db = DatabaseConnection()
        repo = ExpenseRepository()

        eid = repo.add(
            "شركة اختبار",
            125.50,
            "incoming",
            "2026-06-11",
            "قيد اختبار",
            "USD",
            1,
        )
        assert isinstance(eid, int) and eid > 0, "Add must return a positive integer id"

        conn = db.get_connection()
        row = assert_one(conn, "SELECT * FROM expenses WHERE id=?", (eid,))
        assert row["company_name"] == "شركة اختبار"
        assert float(row["amount_original"]) == 125.50
        assert row["status"] == "approved"

        repo.update(
            eid,
            "شركة اختبار",
            0,
            "incoming",
            "2026-06-12",
            "تسديد/انتظار دفع",
            "USD",
            1,
            "2026-06-20",
            "بانتظار الدفع",
        )
        rows = conn.execute("SELECT * FROM expenses WHERE company_name=?", ("شركة اختبار",)).fetchall()
        assert len(rows) == 1, "Updating amount=0 must not create a second expense"
        row = rows[0]
        assert row["id"] == eid
        assert float(row["amount_original"]) == 0.0
        assert row["status"] == "waiting_payment"
        rem = assert_one(conn, "SELECT * FROM payment_reminders WHERE expense_id=? AND is_done=0", (eid,))
        assert rem["reminder_date"] == "2026-06-20"

        summary = repo.get_summary()
        assert abs(float(summary["total_incoming"])) < 1e-9, "waiting_payment rows must not affect dashboard totals"

        repo.delete(eid, 1)
        count = conn.execute("SELECT COUNT(*) AS c FROM expenses WHERE id=?", (eid,)).fetchone()["c"]
        assert count == 0, "Deleted expense must disappear from the database"
        rem_count = conn.execute("SELECT COUNT(*) AS c FROM payment_reminders WHERE expense_id=?", (eid,)).fetchone()["c"]
        assert rem_count == 0, "Deleting expense must delete its reminders"

        try:
            repo.delete(eid, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("Deleting a missing expense must raise ValueError")

        assert os.path.exists(get_local_db_path())
        print("✅ local_crud_smoke_test passed")
        return 0
    finally:
        reset_singleton()
        if old_data_dir is None:
            os.environ.pop("HAWAA_DATA_DIR", None)
        else:
            os.environ["HAWAA_DATA_DIR"] = old_data_dir
        if old_server_flag is None:
            os.environ.pop("HAWAA_SERVER_PROCESS", None)
        else:
            os.environ["HAWAA_SERVER_PROCESS"] = old_server_flag
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
