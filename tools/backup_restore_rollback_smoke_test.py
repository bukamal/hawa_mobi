# -*- coding: utf-8 -*-
"""A failed post-replace migration must restore both database and config."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="hawaa_restore_rollback_"))
    os.environ["HAWAA_DATA_DIR"] = str(root)
    os.environ.pop("FLET_APP_STORAGE_DATA", None)
    os.environ.pop("FLET_APP_STORAGE_TEMP", None)

    from database.connection import DatabaseConnection, get_local_db_path
    from database.migrations import init_database
    from services.file_export_service import FileExportService
    import database.migrations as migrations

    init_database()
    active_db = Path(get_local_db_path())
    conn = sqlite3.connect(active_db)
    try:
        conn.execute(
            "INSERT INTO expenses(company_name,amount,amount_base,type,date,currency,amount_original,currency_original,exchange_rate_to_usd,status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "قاعدة أصلية",
                10,
                10,
                "incoming",
                "2026-01-01",
                "USD",
                10,
                "USD",
                1,
                "approved",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    DatabaseConnection.reset_after_restore()

    config_path = active_db.parent / "config.json"
    original_config = {"company/name": "الإعداد الأصلي", "report/footer": "قديم"}
    config_path.write_text(
        json.dumps(original_config, ensure_ascii=False), encoding="utf-8"
    )

    source_dir = root / "source"
    source_dir.mkdir()
    source_db = source_dir / "candidate.db"
    source_conn = sqlite3.connect(source_db)
    try:
        source_conn.executescript(
            """
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                date TEXT NOT NULL
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        source_conn.execute(
            "INSERT INTO expenses(company_name,amount,type,date) VALUES(?,?,?,?)",
            ("قاعدة بديلة", 99, "outgoing", "2020-01-01"),
        )
        source_conn.commit()
    finally:
        source_conn.close()

    archive = source_dir / "candidate.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_db, "hawaa_data.db")
        zf.writestr(
            "config.json",
            json.dumps(
                {"company/name": "إعداد بديل", "report/footer": "جديد"},
                ensure_ascii=False,
            ),
        )

    original_migrate = migrations.migrate_database_file
    calls = {"count": 0}

    def fail_after_replace(db_path: str, *, create_admin_if_empty: bool = True):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated post-replace failure")
        return original_migrate(db_path, create_admin_if_empty=create_admin_if_empty)

    migrations.migrate_database_file = fail_after_replace
    try:
        try:
            FileExportService.restore_backup_archive(str(archive))
        except RuntimeError as exc:
            assert "simulated post-replace failure" in str(exc)
        else:
            raise AssertionError("restore should have failed")
    finally:
        migrations.migrate_database_file = original_migrate
        DatabaseConnection.reset_after_restore()

    check = sqlite3.connect(active_db)
    try:
        names = [
            row[0]
            for row in check.execute("SELECT company_name FROM expenses ORDER BY id")
        ]
        assert names == ["قاعدة أصلية"], names
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()
    assert json.loads(config_path.read_text(encoding="utf-8")) == original_config
    print("✅ backup_restore_rollback_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
