# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


class Picked:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def main() -> int:
    root = tempfile.mkdtemp(prefix="hawaa_external_picker_bytes_")
    os.environ["HAWAA_DATA_DIR"] = os.path.join(root, "data")
    os.environ["FLET_APP_STORAGE_TEMP"] = os.path.join(root, "tmp")
    os.environ.pop("FLET_APP_STORAGE_DATA", None)

    from database.migrations import init_database
    from database.connection import DatabaseConnection, get_local_db_path
    from services.file_export_service import FileExportService

    init_database()
    db = DatabaseConnection()
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("شركة خارجية", 909.0, 909.0, "incoming", "2026-07-10", "external-picker-bytes", "USD", 1, "now", 1, "now", 909.0, "USD", 1.0, "approved"),
    )
    conn.commit()
    backup = FileExportService.create_backup_archive()
    payload = Path(backup).read_bytes()

    # Simulate Android scoped storage: no readable path, but FilePicker returns bytes.
    picked = Picked(name=os.path.basename(backup), path=None, size=len(payload), bytes=payload)
    staged = FileExportService.resolve_picker_file_path(picked)
    assert staged and os.path.exists(staged), staged
    assert staged != backup
    info = FileExportService.inspect_backup_archive(staged)
    assert info["counts"]["expenses"] >= 1

    # Delete current data, then restore from staged external bytes.
    conn.execute("DELETE FROM expenses")
    conn.commit()
    db.close()
    restored = FileExportService.restore_backup_archive(staged)
    assert restored["ok"] is True
    c = sqlite3.connect(get_local_db_path())
    try:
        row = c.execute("SELECT notes FROM expenses WHERE company_name='شركة خارجية'").fetchone()
        assert row and row[0] == "external-picker-bytes", row
    finally:
        c.close()

    # Simulate an externally re-zipped backup where hawaa_data.db is nested.
    nested_zip = os.path.join(root, "external_nested_backup.zip")
    with zipfile.ZipFile(backup, "r") as src:
        db_bytes = src.read("hawaa_data.db")
    with zipfile.ZipFile(nested_zip, "w", compression=zipfile.ZIP_DEFLATED) as out:
        out.writestr("WhatsApp/Hawaa/hawaa_data.db", db_bytes)
        out.writestr("readme.txt", "external wrapper")
    nested_info = FileExportService.inspect_backup_archive(nested_zip)
    assert nested_info["db_member"] == "WhatsApp/Hawaa/hawaa_data.db", nested_info

    print("✅ backup_external_filepicker_bytes_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
