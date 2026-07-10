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

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        zip_path = FileExportService.build_path(f"hawaa_backup_{timestamp}.zip", "backups", temporary=True)

        # SQLite is configured with WAL. Copying hawaa_data.db alone can miss
        # recently committed changes that still live in the -wal file. Create a
        # consistent snapshot with SQLite backup API, then zip that snapshot.
        snapshot_path = FileExportService.build_path(f"hawaa_data_snapshot_{timestamp}.db", "backups_snapshots", temporary=True)
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(snapshot_path)
        try:
            try:
                src.execute("PRAGMA wal_checkpoint(FULL)")
            except Exception:
                pass
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

        # Keep a persistent internal copy for APK builds where FilePicker is not
        # available. Android may clear cache files; the app-owned backups folder
        # gives the Restore fallback dialog something stable to offer.
        try:
            persistent_dir = os.path.join(_app_storage_dir(), "backups")
            os.makedirs(persistent_dir, exist_ok=True)
            persistent_path = os.path.join(persistent_dir, os.path.basename(zip_path))
            shutil.copy2(zip_path, persistent_path)
        except Exception:
            pass
        return zip_path


    @staticmethod
    def find_recent_backup_archives(limit: int = 10) -> list[str]:
        """Return recent backup archives from app-owned cache/storage.

        This is the no-FilePicker fallback for Android runtimes that do not
        support the FilePicker service. It scans only Hawaa-owned directories,
        not arbitrary external storage.
        """
        roots = []
        for root in (
            os.path.join(_cache_root(), "backups"),
            os.path.join(_app_storage_dir(), "exports", "backups"),
            os.path.join(_app_storage_dir(), "backups"),
        ):
            if root and root not in roots:
                roots.append(root)
        found: list[str] = []
        for root in roots:
            try:
                if not os.path.isdir(root):
                    continue
                for name in os.listdir(root):
                    lower = name.lower()
                    if lower.startswith("hawaa_backup_") and lower.endswith(".zip"):
                        found.append(os.path.join(root, name))
            except Exception:
                continue
        found = sorted(set(found), key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        return found[: max(1, int(limit or 10))]

    @staticmethod
    def describe_backup_file(path: str) -> str:
        try:
            size = os.path.getsize(path)
            mtime = _dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            return f"{os.path.basename(path)} — {size/1024:.1f} KB — {mtime}"
        except Exception:
            return os.path.basename(path or "")

    @staticmethod
    def create_csv_archive(tables: Sequence[str] | None = None) -> str:
        """Export selected SQLite tables to a ZIP of CSV files in app cache."""
        from database.connection import DatabaseConnection

        db = DatabaseConnection()
        if db.is_remote():
            raise RuntimeError("لا يمكن تصدير قاعدة البيانات مباشرة في وضع العميل")
        conn = db.get_connection()
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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
    def _validate_sqlite_backup_db(db_path: str) -> dict:
        """Validate a candidate Hawaa SQLite database before restore."""
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError("ملف قاعدة البيانات داخل النسخة غير موجود")
        conn = sqlite3.connect(db_path)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if str(integrity).lower() != "ok":
                raise ValueError(f"فحص سلامة SQLite فشل: {integrity}")
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = {r[0] for r in rows}
            required = {"users", "expenses", "settings", "exchange_rates"}
            missing = sorted(required - tables)
            if missing:
                raise ValueError("النسخة لا تحتوي الجداول الأساسية: " + ", ".join(missing))
            schema_version = None
            try:
                row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
                schema_version = row[0] if row else None
            except Exception:
                schema_version = None
            counts = {}
            for table in ("users", "expenses", "settings"):
                try:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except Exception:
                    counts[table] = 0
            return {"schema_version": schema_version, "tables": sorted(tables), "counts": counts}
        finally:
            conn.close()

    @staticmethod
    def resolve_picker_file_path(file_obj) -> str | None:
        """Best-effort readable path resolver for Flet FilePicker results.

        On Android, some providers return only a display name or a content URI.
        Python cannot read content:// streams directly in the current Flet line,
        so this function accepts only real readable filesystem paths and common
        file:// variants.  The caller can then show the fallback importer with a
        precise reason instead of silently doing nothing.
        """
        candidates = []
        for attr in ("path", "src", "uri", "url", "name"):
            try:
                value = getattr(file_obj, attr, None)
            except Exception:
                value = None
            if value:
                candidates.append(str(value))
        for raw in candidates:
            value = (raw or "").strip().strip('"').strip("'")
            if not value:
                continue
            if value.startswith("file://"):
                try:
                    from urllib.parse import unquote, urlparse
                    value = unquote(urlparse(value).path or value[7:])
                except Exception:
                    value = value[7:]
            if value.startswith("content://"):
                continue
            try:
                if os.path.exists(value) and os.path.isfile(value):
                    return value
            except Exception:
                continue
        return None

    @staticmethod
    def _count_current_rows() -> dict:
        from database.connection import get_local_db_path
        db_path = get_local_db_path()
        counts = {}
        conn = sqlite3.connect(db_path)
        try:
            for table in ("users", "expenses", "settings", "exchange_rates", "audit_log", "third_party_payments"):
                try:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except Exception:
                    counts[table] = 0
            return counts
        finally:
            conn.close()

    @staticmethod
    def inspect_backup_archive(backup_path: str) -> dict:
        """Inspect a backup ZIP or direct .db file without modifying current data."""
        if not backup_path or not os.path.exists(backup_path):
            raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")
        ext = os.path.splitext(str(backup_path))[1].lower()
        if ext in {".db", ".sqlite", ".sqlite3"}:
            info = FileExportService._validate_sqlite_backup_db(backup_path)
            info.update({"format": "sqlite-db", "source": backup_path})
            return info
        if ext != ".zip":
            raise ValueError("صيغة النسخة غير مدعومة. اختر ملف ZIP أو DB")
        with zipfile.ZipFile(backup_path, "r") as zf:
            names = set(zf.namelist())
            if "hawaa_data.db" not in names:
                raise ValueError("ملف النسخة الاحتياطية غير صالح: لا يحتوي hawaa_data.db")
            tmp_dir = tempfile.mkdtemp(prefix="hawaa_inspect_")
            try:
                zf.extract("hawaa_data.db", tmp_dir)
                info = FileExportService._validate_sqlite_backup_db(os.path.join(tmp_dir, "hawaa_data.db"))
                info.update({"format": "hawaa-backup-zip", "source": backup_path, "has_config": "config.json" in names})
                return info
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def restore_backup_archive(backup_path: str) -> dict:
        """Restore a Hawaa backup ZIP or direct SQLite DB into local Android storage.

        Safety rules:
        - restore is allowed only in local mode; client mode data belongs to Windows Server.
        - validate the candidate database before replacing current data.
        - create a safety backup of current data first.
        - close SQLite and remove WAL/SHM sidecars before replacing the database.
        """
        from database.connection import DatabaseConnection, get_local_db_path

        db = DatabaseConnection()
        if db.is_remote():
            raise RuntimeError("أنت في وضع العميل. الاستعادة تتم من نسخة Windows فقط. غيّر الوضع إلى محلي لاستعادة نسخة داخل الهاتف.")
        if not backup_path or not os.path.exists(backup_path):
            raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")

        inspected = FileExportService.inspect_backup_archive(backup_path)
        safety_backup = None
        try:
            safety_backup = FileExportService.create_backup_archive()
        except Exception:
            safety_backup = None

        target_db = get_local_db_path()
        target_dir = os.path.dirname(target_db)
        os.makedirs(target_dir, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(prefix="hawaa_restore_")
        try:
            ext = os.path.splitext(str(backup_path))[1].lower()
            candidate_db = os.path.join(tmp_dir, "hawaa_data.db")
            config_candidate = None
            if ext in {".db", ".sqlite", ".sqlite3"}:
                shutil.copy2(backup_path, candidate_db)
            else:
                with zipfile.ZipFile(backup_path, "r") as zf:
                    zf.extract("hawaa_data.db", tmp_dir)
                    if "config.json" in set(zf.namelist()):
                        zf.extract("config.json", tmp_dir)
                        config_candidate = os.path.join(tmp_dir, "config.json")
            FileExportService._validate_sqlite_backup_db(candidate_db)

            # Preserve device-local bootstrap settings.  A backup copied from a
            # Windows/client setup may contain network/mode=client; after import
            # that would make the Android app look at the server and the restored
            # local data would appear to be missing.
            preserved_settings = {}
            try:
                local_conn = sqlite3.connect(target_db)
                try:
                    for key in ("network/mode", "network/server_url", "auth/network_token"):
                        row = local_conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                        if row is not None:
                            preserved_settings[key] = row[0]
                finally:
                    local_conn.close()
            except Exception:
                pass

            # Close singleton connection before replacing and remove sidecars.
            db.close()
            try:
                DatabaseConnection.reset_after_restore()
            except Exception:
                pass
            for sidecar in (target_db + "-wal", target_db + "-shm"):
                try:
                    if os.path.exists(sidecar):
                        os.remove(sidecar)
                except Exception:
                    pass

            restore_tmp = os.path.join(target_dir, f".hawaa_restore_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db")
            shutil.copy2(candidate_db, restore_tmp)
            os.replace(restore_tmp, target_db)
            if config_candidate and os.path.exists(config_candidate):
                shutil.copy2(config_candidate, os.path.join(target_dir, "config.json"))

            # Restore device-local network bootstrap after database replacement.
            try:
                local_conn = sqlite3.connect(target_db)
                try:
                    local_conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
                    for key, value in preserved_settings.items():
                        if key == "network/mode":
                            # Backup import in the APK is a local-data operation.
                            value = "local"
                        local_conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
                    if "network/mode" not in preserved_settings:
                        local_conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("network/mode", "local"))
                    local_conn.commit()
                finally:
                    local_conn.close()
            except Exception:
                pass

            # Run migrations/ensure schema on restored DB, then reset all handles
            # again so UI repositories reopen the migrated restored database.
            try:
                from database.migrations import ensure_db
                ensure_db()
                DatabaseConnection.reset_after_restore()
            except Exception:
                raise
            verified_counts = FileExportService._count_current_rows()
            return {"ok": True, "safety_backup": safety_backup, "restored_db": target_db, "inspected": inspected, "verified_counts": verified_counts}
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
