# -*- coding: utf-8 -*-
"""Prove that a database exported by old Hawaa releases is restored losslessly."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def _legacy_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="hawaa_legacy_restore_"))
    os.environ["HAWAA_DATA_DIR"] = str(root / "active")
    os.environ.pop("FLET_APP_STORAGE_DATA", None)
    os.environ.pop("FLET_APP_STORAGE_TEMP", None)

    from auth.password import verify_password
    from database.connection import DatabaseConnection, get_local_db_path
    from database.migrations import CURRENT_SCHEMA_VERSION, init_database
    from services.file_export_service import FileExportService

    init_database()
    active_db = get_local_db_path()
    current = sqlite3.connect(active_db)
    try:
        current.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('network/server_url','https://safe.example')"
        )
        current.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('network/allow_insecure_http','false')"
        )
        current.execute(
            "INSERT INTO expenses(company_name,amount,amount_base,type,date,currency,amount_original,currency_original,exchange_rate_to_usd,status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "البيانات الحالية",
                1,
                1,
                "incoming",
                "2026-01-01",
                "USD",
                1,
                "USD",
                1,
                "approved",
            ),
        )
        current.commit()
    finally:
        current.close()
    DatabaseConnection.reset_after_restore()

    old_db = root / "old_hawaa_export.db"
    conn = sqlite3.connect(old_db)
    try:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                created_at TEXT,
                last_login TEXT
            );
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                notes TEXT,
                currency TEXT DEFAULT 'USD'
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        salt = "legacy-salt-001"
        conn.execute(
            "INSERT INTO users(username,password_hash,salt,full_name,role,created_at) VALUES(?,?,?,?,?,?)",
            (
                "legacy_admin",
                _legacy_hash("OldPass!234", salt),
                salt,
                "مدير قديم",
                "admin",
                "2022-01-01",
            ),
        )
        rows = [
            ("شركة دمشق", 1250.75, "incoming", "2022-05-10", "قيد قديم أول", "USD"),
            ("شركة درعا", 875000.0, "outgoing", "2022-05-11", "قيد قديم ثان", "SYP"),
        ]
        conn.executemany(
            "INSERT INTO expenses(company_name,amount,type,date,notes,currency) VALUES(?,?,?,?,?,?)",
            rows,
        )
        conn.executemany(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            [
                ("schema_version", "3"),
                ("auth/network_token", "must-not-survive"),
                ("network/mode", "client"),
                ("network/server_url", "http://old-server:8000"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    archive = root / "old_export_with_bad_config.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(old_db, "legacy/folder/hawaa-old.db")
        zf.writestr("config.json", b"{not-valid-json")
        zf.writestr("notes.txt", "old exported backup")

    inspected = FileExportService.inspect_backup_archive(str(archive))
    assert inspected["legacy"] is True
    restored = FileExportService.restore_backup_archive(str(archive))
    assert restored["ok"] is True
    assert Path(restored["safety_backup"]).exists()

    check = sqlite3.connect(active_db)
    try:
        check.row_factory = sqlite3.Row
        version = check.execute(
            "SELECT value FROM settings WHERE key='schema_version'"
        ).fetchone()[0]
        assert int(version) == CURRENT_SCHEMA_VERSION
        assert (
            check.execute(
                "SELECT value FROM settings WHERE key='network/mode'"
            ).fetchone()[0]
            == "local"
        )
        assert (
            check.execute(
                "SELECT value FROM settings WHERE key='network/server_url'"
            ).fetchone()[0]
            == "https://safe.example"
        )
        assert (
            check.execute(
                "SELECT COUNT(*) FROM settings WHERE key='auth/network_token'"
            ).fetchone()[0]
            == 0
        )
        expenses = check.execute(
            "SELECT company_name,amount,amount_original,amount_base,currency,currency_original,exchange_rate_to_usd "
            "FROM expenses ORDER BY id"
        ).fetchall()
        assert len(expenses) == 2
        assert tuple(expenses[0]) == (
            "شركة دمشق",
            1250.75,
            1250.75,
            1250.75,
            "USD",
            "USD",
            1.0,
        )
        assert tuple(expenses[1]) == (
            "شركة درعا",
            875000.0,
            875000.0,
            875000.0,
            "SYP",
            "SYP",
            1.0,
        )
        user = check.execute(
            "SELECT password_hash,salt,force_password_change FROM users WHERE username='legacy_admin'"
        ).fetchone()
        assert user is not None and verify_password(
            "OldPass!234", user["password_hash"], user["salt"]
        )
        assert int(user["force_password_change"]) == 0
    finally:
        check.close()

    # The malformed optional config was deliberately ignored; current config
    # must not be deleted or replaced with attacker-controlled content.
    config_path = Path(active_db).parent / "config.json"
    if config_path.exists():
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    print("✅ legacy_backup_migration_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
