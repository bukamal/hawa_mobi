# -*- coding: utf-8 -*-
"""APK-safe file export, backup, sharing and opening helpers.

Design rules:
- Never write user files to hard-coded desktop/Termux paths such as Downloads or /root.
- Generate files inside app-owned storage or cache first.
- Let Android/iOS/desktop choose the final destination through share/open flows.
- Keep all report/backup path policy in one place so views do not guess paths.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Sequence


def _app_storage_dir() -> str:
    """Return a writable app-owned directory on APK and desktop."""
    root = (
        os.environ.get("FLET_APP_STORAGE_DATA")
        or os.environ.get("HAWAA_DATA_DIR")
        or os.path.join(Path.home(), ".hawaa")
    )
    os.makedirs(root, exist_ok=True)
    return root


def _cache_root() -> str:
    root = os.environ.get("FLET_APP_STORAGE_TEMP") or tempfile.gettempdir()
    path = os.path.join(root, "hawaa_exports")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name or "file"))
    return cleaned.strip("._ ") or "file"


class FileExportService:
    """Single export/share policy for reports, backups and print files."""

    @staticmethod
    def app_storage_dir() -> str:
        return _app_storage_dir()

    @staticmethod
    def export_dir(kind: str = "general", *, temporary: bool = True) -> str:
        base = _cache_root() if temporary else os.path.join(_app_storage_dir(), "exports")
        path = os.path.join(base, _safe_filename(kind))
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def build_path(filename: str, kind: str = "general", *, temporary: bool = True) -> str:
        return os.path.join(FileExportService.export_dir(kind, temporary=temporary), _safe_filename(filename))

    @staticmethod
    def create_backup_archive(db_path: str | None = None) -> str:
        """Create a ZIP backup in app-owned cache and return its path.

        The result is intended to be shared/saved by the OS picker. It is not
        silently written to Downloads because that is unreliable on Android 11+.
        """
        if db_path is None:
            from database.connection import get_local_db_path
            db_path = get_local_db_path()
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError("ملف قاعدة البيانات غير موجود")

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = FileExportService.build_path(f"hawaa_backup_{timestamp}.zip", "backups", temporary=True)

        # SQLite is configured with WAL. Copying hawaa_data.db alone can miss
        # recently committed changes that still live in the -wal file. Create a
        # consistent snapshot with SQLite backup API, then zip that snapshot.
        snapshot_path = FileExportService.build_path(f"hawaa_data_snapshot_{timestamp}.db", "backups_snapshots", temporary=True)
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(snapshot_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot_path, "hawaa_data.db")
            config_path = os.path.join(os.path.dirname(db_path), "config.json")
            if os.path.exists(config_path):
                zf.write(config_path, "config.json")
            manifest = (
                f"created_at={_dt.datetime.now().isoformat()}\n"
                "format=hawaa-backup-v1\n"
                "sqlite_snapshot=backup_api\n"
                "restore_hint=استورد هذا الملف من شاشة النسخ الاحتياطي داخل التطبيق.\n"
            )
            zf.writestr("manifest.txt", manifest)
        return zip_path

    @staticmethod
    def create_csv_archive(tables: Sequence[str] | None = None) -> str:
        """Export selected SQLite tables to a ZIP of CSV files in app cache."""
        from database.connection import DatabaseConnection

        db = DatabaseConnection()
        if db.is_remote():
            raise RuntimeError("لا يمكن تصدير قاعدة البيانات مباشرة في وضع العميل")
        conn = db.get_connection()
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = FileExportService.build_path(f"hawaa_csv_export_{timestamp}.zip", "exports", temporary=True)
        tables = list(tables or ["expenses", "users", "audit_log"])
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                if not rows:
                    continue
                tmp_csv = os.path.join(FileExportService.export_dir("csv_tmp", temporary=True), f"{table}_{timestamp}.csv")
                with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([desc[0] for desc in cursor.description])
                    writer.writerows(rows)
                zf.write(tmp_csv, os.path.basename(tmp_csv))
        return zip_path

    @staticmethod
    def restore_backup_archive(backup_zip_path: str) -> None:
        """Restore a backup ZIP created by create_backup_archive.

        This is intentionally conservative and only accepts files containing
        hawaa_data.db. The caller should ask the user for confirmation first.
        """
        if not backup_zip_path or not os.path.exists(backup_zip_path):
            raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")
        from database.connection import get_local_db_path
        target_db = get_local_db_path()
        target_dir = os.path.dirname(target_db)
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(backup_zip_path, "r") as zf:
            names = set(zf.namelist())
            if "hawaa_data.db" not in names:
                raise ValueError("ملف النسخة الاحتياطية غير صالح")
            tmp_dir = tempfile.mkdtemp(prefix="hawaa_restore_")
            try:
                zf.extract("hawaa_data.db", tmp_dir)
                shutil.copy2(os.path.join(tmp_dir, "hawaa_data.db"), target_db)
                if "config.json" in names:
                    zf.extract("config.json", tmp_dir)
                    shutil.copy2(os.path.join(tmp_dir, "config.json"), os.path.join(target_dir, "config.json"))
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    async def share_file_async(page, path: str, text: str = "", *, phone: str | None = None, open_whatsapp: bool = False, title: str = "مشاركة ملف هوى الشام"):
        from reports.share import share_file_async
        return await share_file_async(page, path, text, phone=phone, open_whatsapp=open_whatsapp, title=title)

    @staticmethod
    def share_file(page, path: str, text: str = "", *, phone: str | None = None, open_whatsapp: bool = False) -> bool:
        from reports.share import share_file
        return share_file(page, path, text, phone=phone, open_whatsapp=open_whatsapp)

    @staticmethod
    async def open_file_async(page, path: str, *, title: str = "فتح ملف هوى الشام"):
        # Android cannot reliably open private file:// paths from Flet. Use the
        # platform share/open sheet instead. The user can choose browser, Files,
        # printer provider, Drive, WhatsApp, Telegram, etc.
        return await FileExportService.share_file_async(page, path, f"ملف من نظام هوى الشام: {os.path.basename(path)}", open_whatsapp=False, title=title)

    @staticmethod
    def open_file(page, path: str) -> bool:
        return FileExportService.share_file(page, path, f"ملف من نظام هوى الشام: {os.path.basename(path)}", open_whatsapp=False)
