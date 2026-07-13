# -*- coding: utf-8 -*-
"""Verify that backups do not carry reusable network session credentials."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="hawaa_secure_backup_"))
    os.environ["HAWAA_DATA_DIR"] = str(root)
    os.environ.pop("FLET_APP_STORAGE_DATA", None)
    os.environ.pop("FLET_APP_STORAGE_TEMP", None)

    from database.connection import DatabaseConnection, get_local_db_path
    from database.migrations import init_database
    from services.file_export_service import FileExportService

    init_database()
    conn = sqlite3.connect(get_local_db_path())
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            [
                ("auth/network_token", "super-secret-token"),
                ("network/mode", "client"),
                ("network/server_url", "https://api.example"),
                ("network/allow_insecure_http", "true"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    DatabaseConnection.reset_after_restore()

    backup = FileExportService.create_backup_archive()
    with zipfile.ZipFile(backup, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == "hawaa-backup-v2"
        assert manifest["credentials_included"] is False
        extracted = root / "snapshot.db"
        extracted.write_bytes(zf.read("hawaa_data.db"))

    snap = sqlite3.connect(extracted)
    try:
        assert (
            snap.execute(
                "SELECT COUNT(*) FROM settings WHERE key='auth/network_token'"
            ).fetchone()[0]
            == 0
        )
        assert (
            snap.execute(
                "SELECT value FROM settings WHERE key='network/mode'"
            ).fetchone()[0]
            == "local"
        )
        assert (
            snap.execute(
                "SELECT value FROM settings WHERE key='network/server_url'"
            ).fetchone()[0]
            == ""
        )
        assert (
            snap.execute(
                "SELECT value FROM settings WHERE key='network/allow_insecure_http'"
            ).fetchone()[0]
            == "false"
        )
        assert snap.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        snap.close()

    raw = Path(backup).read_bytes()
    assert b"super-secret-token" not in raw
    print("✅ secure_backup_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
