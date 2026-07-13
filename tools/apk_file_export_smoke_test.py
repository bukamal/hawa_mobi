# -*- coding: utf-8 -*-
"""Smoke test for APK-safe export/share path policy."""

from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

from services.file_export_service import FileExportService

ROOT = Path(__file__).resolve().parents[1]


def assert_no_hardcoded_export_paths() -> None:
    forbidden = ["~/storage/downloads", "~/Downloads", "os.getcwd()"]
    files = [
        ROOT / "views" / "settings_mobile_view.py",
        ROOT / "reports" / "account_statement.py",
        ROOT / "services" / "file_export_service.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                raise AssertionError(
                    f"Hard-coded export path remains in {path}: {token}"
                )


def assert_report_dir_uses_export_service() -> None:
    path = FileExportService.export_dir("reports", temporary=True)
    if not os.path.isdir(path):
        raise AssertionError("report export dir was not created")
    if "hawaa_exports" not in path:
        raise AssertionError(f"unexpected export dir: {path}")


def assert_backup_archive_created() -> None:
    tmp = tempfile.mkdtemp(prefix="hawaa_export_test_")
    db_path = os.path.join(tmp, "hawaa_data.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO sample(name) VALUES ('ok')")
    conn.commit()
    conn.close()
    backup = FileExportService.create_backup_archive(db_path)
    if not backup.endswith(".zip") or not os.path.exists(backup):
        raise AssertionError("backup ZIP was not created")


def main() -> int:
    assert_no_hardcoded_export_paths()
    assert_report_dir_uses_export_service()
    assert_backup_archive_created()
    print("✅ apk_file_export_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
