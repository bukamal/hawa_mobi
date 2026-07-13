# -*- coding: utf-8 -*-
"""Regression guard for Flet Android SQLite/thread startup crashes."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import tempfile
import threading
from queue import Queue

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

with tempfile.TemporaryDirectory(prefix="hawaa-sqlite-thread-") as tmp:
    os.environ["HAWAA_DATA_DIR"] = tmp

    from database.migrations import ensure_db
    from database.connection import DatabaseConnection

    ensure_db()
    db = DatabaseConnection()

    main_conn = db.get_connection()
    main_thread = threading.get_ident()
    assert main_conn.execute("SELECT 1").fetchone()[0] == 1

    q: Queue = Queue()

    def worker():
        try:
            worker_conn = db.get_connection()
            worker_thread = threading.get_ident()
            row = worker_conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
            q.put((True, worker_thread, worker_conn is main_conn, row[0] if row else None))
        except Exception as exc:
            q.put((False, threading.get_ident(), False, repr(exc)))

    t = threading.Thread(target=worker, name="hawaa-db-thread-smoke")
    t.start()
    t.join(timeout=10)
    assert not t.is_alive(), "worker thread did not finish"

    ok, worker_thread, same_connection, value = q.get_nowait()
    assert ok, value
    assert worker_thread != main_thread
    assert same_connection is False, "DatabaseConnection must not reuse one sqlite connection across threads"
    assert value == "ar"

    # Main-thread connection remains usable after the worker used its own handle.
    assert main_conn.execute("SELECT 1").fetchone()[0] == 1
    db.close()

print("✅ sqlite_thread_safety_smoke_test passed")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
