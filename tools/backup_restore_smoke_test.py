# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
import tempfile


def main() -> int:
    root = tempfile.mkdtemp(prefix="hawaa_restore_smoke_")
    os.environ["HAWAA_DATA_DIR"] = root
    os.environ.pop("FLET_APP_STORAGE_DATA", None)
    os.environ.pop("FLET_APP_STORAGE_TEMP", None)

    from database.migrations import init_database
    from database.connection import DatabaseConnection, get_local_db_path
    from services.file_export_service import FileExportService

    init_database()
    db = DatabaseConnection()
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, amount_original, currency_original, exchange_rate_to_usd, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "شركة الاختبار",
            100.0,
            100.0,
            "incoming",
            "2026-01-01",
            "قبل النسخ",
            "USD",
            100.0,
            "USD",
            1.0,
            "approved",
        ),
    )
    conn.commit()
    backup = FileExportService.create_backup_archive()
    assert backup.endswith(".zip") and os.path.exists(backup)
    info = FileExportService.inspect_backup_archive(backup)
    assert info["counts"]["expenses"] >= 1

    conn.execute("DELETE FROM expenses")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0
    db.close()

    restored = FileExportService.restore_backup_archive(backup)
    assert restored["ok"] is True
    assert restored.get("safety_backup")

    conn2 = sqlite3.connect(get_local_db_path())
    try:
        count = conn2.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        assert count >= 1, count
        note = conn2.execute(
            "SELECT notes FROM expenses WHERE company_name='شركة الاختبار'"
        ).fetchone()[0]
        assert note == "قبل النسخ"
    finally:
        conn2.close()
    print("✅ backup_restore_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
