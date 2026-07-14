# -*- coding: utf-8 -*-
"""Regression test for stale closed SQLite handles in Android/Flet callbacks.

A thread-local sqlite3 connection can remain referenced after another workflow
closed the global connection pool (backup restore, startup migration, mode
refresh, or a previous page instance).  UI pages must recover by opening a new
connection instead of surfacing: "Cannot operate on a closed database".
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def reset_singleton() -> None:
    from database.connection import DatabaseConnection
    try:
        DatabaseConnection().close()
    except Exception:
        pass
    DatabaseConnection._instance = None
    DatabaseConnection._local_conn = None
    try:
        DatabaseConnection._thread_local.conn = None
    except Exception:
        pass
    try:
        DatabaseConnection._connections.clear()
    except Exception:
        pass


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hawaa_closed_db_recovery_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    try:
        reset_singleton()
        from database.migrations import ensure_db
        ensure_db()
        from auth.session import UserSession
        from database.connection import DatabaseConnection
        from database import ExpenseRepository
        from reports.reporting_center import PERIOD_ALL, REPORT_COMPANY_BALANCES, ReportingCenterService

        UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})
        ExpenseRepository().add("شركة اختبار", 100, "incoming", "2026-07-01", "اختبار", "USD", 1)

        service = ReportingCenterService()
        first = service.build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
        assert first.rows and any(r.get("company") == "شركة اختبار" for r in first.rows)

        db = DatabaseConnection()
        stale = db.get_connection()
        stale.close()

        # Same service / same thread after the handle was closed.  This is what
        # used to fail in the Reports tab and sometimes on account screens.
        second = service.build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
        assert second.rows and any(r.get("company") == "شركة اختبار" for r in second.rows)

        # Existing repositories must recover too, not only newly created ones.
        repo = ExpenseRepository()
        conn = db.get_connection()
        conn.close()
        rows = repo.get_all(convert_to_display=False)
        assert any(r.get("company_name") == "شركة اختبار" for r in rows)

        print("sqlite_closed_connection_recovery_smoke_test passed", flush=True)
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
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
