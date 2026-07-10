# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path


def main():
    root = tempfile.mkdtemp(prefix="hawaa_import_runtime_")
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
        "INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("شركة اختبار الاستيراد", 777.0, 777.0, "incoming", "2026-07-10", "backup-import-runtime", "USD", 1, "now", 1, "now", 777.0, "USD", 1.0, "approved"),
    )
    conn.commit()
    backup = FileExportService.create_backup_archive()
    assert os.path.exists(backup)

    # Simulate destructive local changes after export.
    conn.execute("DELETE FROM expenses")
    conn.commit()
    assert DatabaseConnection().get_expenses() == []

    restored = FileExportService.restore_backup_archive(backup)
    assert restored["ok"] is True
    assert restored.get("verified_counts", {}).get("expenses", 0) >= 1

    # The already-created singleton must reopen the restored database without an app restart.
    rows = DatabaseConnection().get_expenses()
    assert any(r.get("company_name") == "شركة اختبار الاستيراد" for r in rows), rows

    # A backup with network/mode=client must not make local restored data disappear.
    db_path = get_local_db_path()
    c = sqlite3.connect(db_path)
    try:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("network/mode", "client"))
        c.commit()
    finally:
        c.close()
    backup_client_mode = FileExportService.create_backup_archive()
    FileExportService.restore_backup_archive(backup_client_mode)
    assert DatabaseConnection().is_remote() is False
    assert DatabaseConnection().get_setting("network/mode", "") == "local"
    print("✅ backup_import_runtime_refresh_smoke_test passed")


if __name__ == "__main__":
    main()
