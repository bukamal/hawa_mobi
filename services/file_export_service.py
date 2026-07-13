# -*- coding: utf-8 -*-
"""APK-safe file export, backup, sharing and opening helpers.

Design rules:
- Never write user files to hard-coded desktop/Termux paths such as Downloads or /root.
- Generate files inside app-owned storage or cache first.
- Let Android/iOS/desktop choose the final destination through share/open flows.
- Keep all report/backup path policy in one place so views do not guess paths.
"""

from __future__ import annotations

import base64
import csv
import datetime as _dt
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse

MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 256


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
    cleaned = "".join(
        ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name or "file")
    )
    return cleaned.strip("._ ") or "file"


class FileExportService:
    """Single export/share policy for reports, backups and print files."""

    @staticmethod
    def app_storage_dir() -> str:
        return _app_storage_dir()

    @staticmethod
    def export_dir(kind: str = "general", *, temporary: bool = True) -> str:
        base = (
            _cache_root() if temporary else os.path.join(_app_storage_dir(), "exports")
        )
        path = os.path.join(base, _safe_filename(kind))
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def build_path(
        filename: str, kind: str = "general", *, temporary: bool = True
    ) -> str:
        return os.path.join(
            FileExportService.export_dir(kind, temporary=temporary),
            _safe_filename(filename),
        )

    @staticmethod
    def create_backup_archive(db_path: str | None = None) -> str:
        """Create a consistent, portable backup without session credentials."""
        if db_path is None:
            from database.connection import get_local_db_path

            db_path = get_local_db_path()
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError("ملف قاعدة البيانات غير موجود")

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        zip_path = FileExportService.build_path(
            f"hawaa_backup_{timestamp}.zip", "backups", temporary=True
        )
        snapshot_path = FileExportService.build_path(
            f"hawaa_data_snapshot_{timestamp}.db", "backups_snapshots", temporary=True
        )
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(snapshot_path)
        try:
            try:
                src.execute("PRAGMA wal_checkpoint(FULL)")
            except sqlite3.DatabaseError:
                pass
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        snapshot = sqlite3.connect(snapshot_path)
        try:
            snapshot.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            snapshot.execute("DELETE FROM settings WHERE key='auth/network_token'")
            snapshot.execute(
                "INSERT OR REPLACE INTO settings (key,value) VALUES ('network/mode','local')"
            )
            snapshot.execute(
                "INSERT OR REPLACE INTO settings (key,value) VALUES ('network/server_url','')"
            )
            snapshot.execute(
                "INSERT OR REPLACE INTO settings (key,value) VALUES ('network/allow_insecure_http','false')"
            )
            snapshot.commit()
            snapshot.execute("VACUUM")
        finally:
            snapshot.close()

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot_path, "hawaa_data.db")
            config_path = os.path.join(os.path.dirname(db_path), "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as file_obj:
                        raw_config = json.load(file_obj)
                    allowed_prefixes = ("company/", "report/")
                    safe_config = {
                        str(key): value
                        for key, value in dict(raw_config or {}).items()
                        if str(key).startswith(allowed_prefixes)
                    }
                    zf.writestr(
                        "config.json",
                        json.dumps(safe_config, ensure_ascii=False, indent=2),
                    )
                except (OSError, ValueError, TypeError):
                    pass
            manifest = {
                "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "format": "hawaa-backup-v2",
                "sqlite_snapshot": "backup_api",
                "credentials_included": False,
            }
            zf.writestr(
                "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
            )

        try:
            persistent_dir = os.path.join(_app_storage_dir(), "backups")
            os.makedirs(persistent_dir, exist_ok=True)
            shutil.copy2(
                zip_path, os.path.join(persistent_dir, os.path.basename(zip_path))
            )
        except OSError:
            pass
        try:
            os.remove(snapshot_path)
        except OSError:
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
        found = sorted(
            set(found),
            key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0,
            reverse=True,
        )
        return found[: max(1, int(limit or 10))]

    @staticmethod
    def describe_backup_file(path: str) -> str:
        try:
            size = os.path.getsize(path)
            mtime = _dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                "%Y-%m-%d %H:%M"
            )
            return f"{os.path.basename(path)} — {size / 1024:.1f} KB — {mtime}"
        except Exception:
            return os.path.basename(path or "")

    @staticmethod
    def restore_log_path() -> str:
        path = os.path.join(_app_storage_dir(), "logs")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "backup_restore.log")

    @staticmethod
    def log_restore_event(message: str) -> None:
        try:
            with open(FileExportService.restore_log_path(), "a", encoding="utf-8") as f:
                f.write(
                    f"[{_dt.datetime.now().isoformat(timespec='seconds')}] {message}\n"
                )
        except Exception:
            pass

    @staticmethod
    def read_restore_log_tail(lines: int = 40) -> list[str]:
        try:
            path = FileExportService.restore_log_path()
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.readlines()
            return [line.rstrip("\n") for line in data[-max(1, int(lines or 40)) :]]
        except Exception:
            return []

    @staticmethod
    def find_external_backup_archives(
        limit: int = 12, *, validate: bool = True
    ) -> list[str]:
        """Find readable external backup candidates without FilePicker.

        This is the hard Android fallback when the native chooser opens but does
        not deliver an on_result event to Python.  It scans a small set of common
        user folders only (Downloads, Documents, WhatsApp/Telegram documents)
        and optionally validates that each ZIP/DB is a Hawaa backup.
        """
        candidates: list[str] = []
        suffixes = (".zip", ".db", ".sqlite", ".sqlite3")
        for root in FileExportService._public_import_roots():
            try:
                if not os.path.isdir(root):
                    continue
                stack = [(root, 0)]
                while stack and len(candidates) < 80:
                    current, depth = stack.pop()
                    try:
                        entries = list(os.scandir(current))
                    except Exception:
                        continue
                    for entry in entries:
                        try:
                            if entry.is_file():
                                name = entry.name.lower()
                                if name.endswith(
                                    suffixes
                                ) and FileExportService._is_readable_file(entry.path):
                                    candidates.append(entry.path)
                            elif entry.is_dir() and depth < 2:
                                # Keep the scan bounded; large phone storage
                                # walks are slow and unreliable on Android.
                                stack.append((entry.path, depth + 1))
                        except Exception:
                            continue
            except Exception:
                continue
        candidates = sorted(
            set(candidates),
            key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0,
            reverse=True,
        )
        if not validate:
            return candidates[: max(1, int(limit or 12))]
        valid: list[str] = []
        for path in candidates:
            try:
                FileExportService.inspect_backup_archive(path)
                valid.append(path)
                if len(valid) >= max(1, int(limit or 12)):
                    break
            except Exception as ex:
                FileExportService.log_restore_event(
                    f"skip invalid external candidate: {path} :: {ex}"
                )
        return valid

    @staticmethod
    def create_csv_archive(tables: Sequence[str] | None = None) -> str:
        """Export selected SQLite tables to a ZIP of CSV files in app cache."""
        from database.connection import DatabaseConnection

        db = DatabaseConnection()
        if db.is_remote():
            raise RuntimeError("لا يمكن تصدير قاعدة البيانات مباشرة في وضع العميل")
        conn = db.get_connection()
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        zip_path = FileExportService.build_path(
            f"hawaa_csv_export_{timestamp}.zip", "exports", temporary=True
        )
        export_queries = {
            "expenses": "SELECT * FROM expenses",
            "users": "SELECT * FROM users",
            "audit_log": "SELECT * FROM audit_log",
            "exchange_rates": "SELECT * FROM exchange_rates",
            "payment_reminders": "SELECT * FROM payment_reminders",
            "third_party_payments": "SELECT * FROM third_party_payments",
            "service_cases": "SELECT * FROM service_cases",
            "service_case_components": "SELECT * FROM service_case_components",
        }
        tables = list(tables or ["expenses", "users", "audit_log"])
        invalid = sorted({str(table) for table in tables} - export_queries.keys())
        if invalid:
            raise ValueError("جداول تصدير غير مسموحة: " + ", ".join(invalid))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for table in tables:
                cursor = conn.execute(export_queries[str(table)])
                rows = cursor.fetchall()
                if not rows:
                    continue
                tmp_csv = os.path.join(
                    FileExportService.export_dir("csv_tmp", temporary=True),
                    f"{table}_{timestamp}.csv",
                )
                with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([desc[0] for desc in cursor.description])
                    writer.writerows(rows)
                zf.write(tmp_csv, os.path.basename(tmp_csv))
        return zip_path

    @staticmethod
    def _validate_sqlite_backup_db(db_path: str) -> dict:
        """Validate current and legacy Hawaa SQLite databases without modifying them."""
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError("ملف قاعدة البيانات داخل النسخة غير موجود")
        size = os.path.getsize(db_path)
        if size <= 0 or size > MAX_BACKUP_BYTES:
            raise ValueError("حجم قاعدة البيانات غير صالح أو يتجاوز الحد الآمن")
        conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if str(integrity).lower() != "ok":
                raise ValueError(f"فحص سلامة SQLite فشل: {integrity}")
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "expenses" not in tables:
                raise ValueError("النسخة لا تحتوي جدول القيود expenses")
            expense_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(expenses)").fetchall()
            }
            missing_core = sorted(
                {"company_name", "amount", "type", "date"} - expense_columns
            )
            if missing_core:
                raise ValueError(
                    "جدول القيود يفتقد أعمدة أساسية: " + ", ".join(missing_core)
                )
            current_required = {"users", "expenses", "settings", "exchange_rates"}
            missing_tables = sorted(current_required - tables)
            schema_version = None
            if "settings" in tables:
                try:
                    row = conn.execute(
                        "SELECT value FROM settings WHERE key='schema_version'"
                    ).fetchone()
                    schema_version = row[0] if row else None
                except sqlite3.DatabaseError:
                    schema_version = None
            count_queries = {
                "users": "SELECT COUNT(*) FROM users",
                "expenses": "SELECT COUNT(*) FROM expenses",
                "settings": "SELECT COUNT(*) FROM settings",
                "exchange_rates": "SELECT COUNT(*) FROM exchange_rates",
                "audit_log": "SELECT COUNT(*) FROM audit_log",
            }
            counts = {
                table: int(conn.execute(query).fetchone()[0]) if table in tables else 0
                for table, query in count_queries.items()
            }
            return {
                "schema_version": schema_version,
                "tables": sorted(tables),
                "counts": counts,
                "legacy": bool(missing_tables or str(schema_version or "") != "23"),
                "missing_tables": missing_tables,
                "size_bytes": size,
            }
        finally:
            conn.close()

    @staticmethod
    def _public_import_roots() -> list[str]:
        """Candidate roots where Android may expose user-selected backups.

        This is intentionally best-effort.  Android 10/11+ scoped storage can
        hide files from plain Python paths even when the native picker can show
        them.  Searching these roots still fixes the common Flet case where
        FilePicker returns only the display name while the backup is in
        Download/Hawaa or Download.
        """
        roots: list[str] = []
        package = os.environ.get("ANDROID_PACKAGE") or "com.hawaa"
        for candidate in (
            os.environ.get("PUBLIC_DOWNLOADS"),
            os.path.join(os.environ.get("EXTERNAL_STORAGE", ""), "Download")
            if os.environ.get("EXTERNAL_STORAGE")
            else "",
            "/storage/emulated/0/Download/Hawaa",
            "/storage/emulated/0/Download",
            "/storage/emulated/0/Documents/Hawaa",
            "/storage/emulated/0/Documents",
            "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents",
            "/storage/emulated/0/Android/media/org.telegram.messenger/Telegram/Telegram Documents",
            f"/storage/emulated/0/Android/data/{package}/files",
            "/sdcard/Download/Hawaa",
            "/sdcard/Download",
            "/sdcard/Documents/Hawaa",
            "/sdcard/Documents",
            os.path.join(_app_storage_dir(), "backups"),
            os.path.join(_app_storage_dir(), "exports", "backups"),
            os.path.join(_cache_root(), "backups"),
        ):
            if candidate and candidate not in roots:
                roots.append(candidate)
        return roots

    @staticmethod
    def _is_readable_file(path: str) -> bool:
        try:
            return bool(path and os.path.isfile(path) and os.access(path, os.R_OK))
        except Exception:
            return False

    @staticmethod
    def _write_picker_bytes_to_cache(
        raw_value, *, suggested_name: str = "hawaa_import.zip"
    ) -> str | None:
        """Materialize FilePickerFile.bytes into an app-readable cache file.

        This is the most reliable Android restore path.  Flet's native picker can
        expose no absolute path on Android, but ``pick_files(with_data=True)`` can
        return the file contents in ``FilePickerFile.bytes``.  Store those bytes
        in app-owned cache, then validate/import from that normal file path.
        """
        if raw_value in (None, ""):
            return None
        data = None
        try:
            if isinstance(raw_value, (bytes, bytearray, memoryview)):
                data = bytes(raw_value)
            elif isinstance(raw_value, str):
                text = raw_value.strip()
                if not text:
                    return None
                if text.startswith("data:") and "," in text:
                    text = text.split(",", 1)[1]
                # Flet normally returns bytes, but some bridges serialise bytes
                # as base64 strings.  Validate so paths/URIs are not decoded by
                # accident.
                try:
                    data = base64.b64decode(text, validate=True)
                except Exception:
                    return None
            elif isinstance(raw_value, (list, tuple)):
                data = bytes(int(x) & 0xFF for x in raw_value)
            else:
                return None
        except Exception:
            return None
        if not data:
            return None
        safe_name = _safe_filename(
            os.path.basename(suggested_name or "hawaa_import.zip")
        )
        lower = safe_name.lower()
        if not lower.endswith((".zip", ".db", ".sqlite", ".sqlite3")):
            safe_name += ".zip"
        target = FileExportService.build_path(
            f"picked_bytes_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_name}",
            "picked_imports",
            temporary=True,
        )
        try:
            with open(target, "wb") as out:
                out.write(data)
            return target if FileExportService._is_readable_file(target) else None
        except Exception:
            return None

    @staticmethod
    def _copy_android_content_uri_to_cache(
        content_uri: str, *, suggested_name: str = "hawaa_import.zip"
    ) -> str | None:
        """Best-effort copy for Android SAF ``content://`` results.

        Some Flet Android builds return a content URI instead of a real path.
        Python cannot normally open that URI.  When a Java bridge is available
        in the APK, this function streams it through Android's ContentResolver
        into app-owned cache.  If the bridge is not present, it returns None
        and the UI falls back to the internal-backup/import-by-name path.
        """
        if not content_uri or not str(content_uri).startswith("content://"):
            return None
        try:
            jnius = __import__("jnius")
            autoclass = getattr(jnius, "autoclass")
            jarray = getattr(jnius, "jarray")
        except Exception:
            return None

        context = None
        # Flet Android runtimes are not all built on the same Android bridge.
        # Try the plain Android ActivityThread first, then the python-for-android
        # activity name used by some embedded Python builds.  If neither exists
        # we rely on FilePickerFile.bytes / readable paths instead.
        try:
            ActivityThread = autoclass("android.app.ActivityThread")
            app = ActivityThread.currentApplication()
            if app is not None:
                context = app.getApplicationContext()
        except Exception:
            context = None
        if context is None:
            try:
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = getattr(PythonActivity, "mActivity", None)
                if activity is not None:
                    context = activity.getApplicationContext()
            except Exception:
                context = None
        if context is None:
            return None

        try:
            Uri = autoclass("android.net.Uri")
            uri_obj = Uri.parse(content_uri)
            resolver = context.getContentResolver()
            stream = resolver.openInputStream(uri_obj)
            if stream is None:
                return None
            safe_name = _safe_filename(
                os.path.basename(suggested_name or "hawaa_import.zip")
            )
            lower = safe_name.lower()
            if not lower.endswith((".zip", ".db", ".sqlite", ".sqlite3")):
                safe_name += ".zip"
            target = FileExportService.build_path(
                f"picked_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_name}",
                "picked_imports",
                temporary=True,
            )
            buf = jarray("b")(64 * 1024)
            with open(target, "wb") as out:
                while True:
                    n = stream.read(buf)
                    n = int(n)
                    if n == -1:
                        break
                    if n == 0:
                        break
                    # pyjnius returns a signed Java byte[]; bytearray handles it
                    # after masking to unsigned byte values.
                    out.write(bytes((int(buf[i]) & 0xFF for i in range(n))))
            try:
                stream.close()
            except Exception:
                pass
            return target if FileExportService._is_readable_file(target) else None
        except Exception:
            try:
                stream.close()  # type: ignore[name-defined]
            except Exception:
                pass
            return None

    @staticmethod
    def _find_readable_backup_by_name(
        name: str, *, size: int | None = None
    ) -> str | None:
        """Find a picked file by display name in app/Public backup folders."""
        name = os.path.basename(str(name or "").strip())
        if not name:
            return None
        candidates: list[str] = []
        for root in FileExportService._public_import_roots():
            try:
                if not os.path.isdir(root):
                    continue
                # Exact path in root first.
                direct = os.path.join(root, name)
                if FileExportService._is_readable_file(direct):
                    candidates.append(direct)
                # Then scan one level deep.  Avoid walking the whole phone.
                for item in os.listdir(root):
                    p = os.path.join(root, item)
                    if (
                        os.path.isfile(p)
                        and item == name
                        and FileExportService._is_readable_file(p)
                    ):
                        candidates.append(p)
                    elif os.path.isdir(p):
                        try:
                            nested = os.path.join(p, name)
                            if FileExportService._is_readable_file(nested):
                                candidates.append(nested)
                        except Exception:
                            pass
            except Exception:
                continue
        if not candidates:
            return None
        if size:
            sized = []
            for path in candidates:
                try:
                    if int(os.path.getsize(path)) == int(size):
                        sized.append(path)
                except Exception:
                    pass
            if sized:
                candidates = sized
        candidates = sorted(
            set(candidates),
            key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0,
            reverse=True,
        )
        return candidates[0] if candidates else None

    @staticmethod
    def describe_picker_file(file_obj) -> str:
        """Diagnostic summary for Android FilePicker results."""
        parts = []
        for attr in ("name", "path", "src", "uri", "url", "size"):
            try:
                value = getattr(file_obj, attr, None)
            except Exception:
                value = None
            if value not in (None, ""):
                parts.append(f"{attr}={value}")
        for attr in ("bytes", "content", "data"):
            try:
                value = getattr(file_obj, attr, None)
            except Exception:
                value = None
            if value not in (None, ""):
                try:
                    parts.append(f"{attr}_len={len(value)}")
                except Exception:
                    parts.append(f"{attr}=present")
        return " | ".join(parts) or str(file_obj or "")

    @staticmethod
    def resolve_picker_file_path(file_obj) -> str | None:
        """Resolve a Flet FilePicker result into a readable local file.

        Resolution order:
        1. Direct readable path / file:// path returned by Flet.
        2. Android content:// URI copied through ContentResolver when a Java
           bridge is available.
        3. Display-name lookup in Download/Hawaa, Download, and app-owned backup
           folders.

        Returning ``None`` means the native picker showed the file, but this
        Python runtime still cannot read it.  The Settings UI then opens the
        fallback importer instead of pretending that restore succeeded.
        """
        if file_obj is None:
            FileExportService.log_restore_event("picker result: None")
            return None
        try:
            FileExportService.log_restore_event(
                "picker result: " + FileExportService.describe_picker_file(file_obj)
            )
        except Exception:
            pass

        candidates = []
        # First: if pick_files(with_data=True) is supported, Android can return
        # bytes even when it cannot return an absolute path.  This is the only
        # fully reliable external-import path under scoped storage.
        for attr in ("bytes", "content", "data"):
            try:
                raw_bytes = getattr(file_obj, attr, None)
            except Exception:
                raw_bytes = None
            materialized = FileExportService._write_picker_bytes_to_cache(
                raw_bytes,
                suggested_name=str(
                    getattr(file_obj, "name", None) or "hawaa_import.zip"
                ),
            )
            if materialized:
                FileExportService.log_restore_event(
                    f"picker bytes materialized: {materialized}"
                )
                return materialized

        for attr in ("path", "src", "uri", "url", "name"):
            try:
                value = getattr(file_obj, attr, None)
            except Exception:
                value = None
            if value:
                candidates.append((attr, str(value)))

        display_name = None
        display_size = None
        try:
            display_name = getattr(file_obj, "name", None)
        except Exception:
            display_name = None
        try:
            raw_size = getattr(file_obj, "size", None)
            display_size = int(raw_size) if raw_size not in (None, "") else None
        except Exception:
            display_size = None

        # 1/2: direct path and content URI variants.
        for attr, raw in candidates:
            value = (raw or "").strip().strip('"').strip("'")
            if not value:
                continue
            if value.startswith("file://"):
                try:
                    value = unquote(urlparse(value).path or value[7:])
                except Exception:
                    value = value[7:]
            if value.startswith("content://"):
                copied = FileExportService._copy_android_content_uri_to_cache(
                    value, suggested_name=str(display_name or "hawaa_import.zip")
                )
                if copied and FileExportService._is_readable_file(copied):
                    FileExportService.log_restore_event(f"content uri copied: {copied}")
                    return copied
                continue
            if FileExportService._is_readable_file(value):
                FileExportService.log_restore_event(
                    f"direct readable picker path: {value}"
                )
                return value

        # 3: common Android/Flet case: only a display name was returned.
        if display_name:
            found = FileExportService._find_readable_backup_by_name(
                str(display_name), size=display_size
            )
            if found:
                FileExportService.log_restore_event(
                    f"found backup by display name: {found}"
                )
                return found
        for _attr, raw in candidates:
            base = os.path.basename(str(raw or ""))
            if base:
                found = FileExportService._find_readable_backup_by_name(
                    base, size=display_size
                )
                if found:
                    FileExportService.log_restore_event(
                        f"found backup by basename: {found}"
                    )
                    return found
        FileExportService.log_restore_event("picker result could not be resolved")
        return None

    @staticmethod
    def _count_current_rows() -> dict:
        from database.connection import get_local_db_path

        db_path = get_local_db_path()
        count_queries = {
            "users": "SELECT COUNT(*) FROM users",
            "expenses": "SELECT COUNT(*) FROM expenses",
            "settings": "SELECT COUNT(*) FROM settings",
            "exchange_rates": "SELECT COUNT(*) FROM exchange_rates",
            "audit_log": "SELECT COUNT(*) FROM audit_log",
            "third_party_payments": "SELECT COUNT(*) FROM third_party_payments",
        }
        counts = {}
        conn = sqlite3.connect(db_path)
        try:
            for table, query in count_queries.items():
                try:
                    counts[table] = int(conn.execute(query).fetchone()[0])
                except sqlite3.DatabaseError:
                    counts[table] = 0
            return counts
        finally:
            conn.close()

    @staticmethod
    def _extract_valid_sqlite_from_zip(
        zf: zipfile.ZipFile, tmp_dir: str
    ) -> tuple[str, str]:
        """Extract the first valid Hawaa DB while enforcing archive limits."""
        infos = [info for info in zf.infolist() if not info.is_dir()]
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("ملف ZIP يحتوي عددًا غير منطقي من الملفات")
        if sum(max(0, info.file_size) for info in infos) > MAX_BACKUP_BYTES:
            raise ValueError("الحجم المفكوك لملف ZIP يتجاوز الحد الآمن")
        names = [info.filename for info in infos]
        preferred = [
            name for name in names if os.path.basename(name).lower() == "hawaa_data.db"
        ]
        db_candidates = preferred + [
            name
            for name in names
            if name not in preferred
            and os.path.basename(name).lower().endswith((".db", ".sqlite", ".sqlite3"))
        ]
        errors: list[str] = []
        for index, member in enumerate(db_candidates):
            info = zf.getinfo(member)
            if info.file_size <= 0 or info.file_size > MAX_BACKUP_BYTES:
                errors.append(f"{member}: حجم غير صالح")
                continue
            candidate = os.path.join(
                tmp_dir, f"candidate_{index}_{_safe_filename(os.path.basename(member))}"
            )
            try:
                with zf.open(member) as src, open(candidate, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                FileExportService._validate_sqlite_backup_db(candidate)
                return candidate, member
            except Exception as ex:
                errors.append(f"{member}: {ex}")
                try:
                    os.remove(candidate)
                except OSError:
                    pass
        nested_zips = [
            name for name in names if os.path.basename(name).lower().endswith(".zip")
        ]
        for member in nested_zips[:3]:
            info = zf.getinfo(member)
            if info.file_size <= 0 or info.file_size > MAX_BACKUP_BYTES:
                continue
            nested_path = os.path.join(
                tmp_dir, f"nested_{_safe_filename(os.path.basename(member))}"
            )
            try:
                with zf.open(member) as src, open(nested_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                with zipfile.ZipFile(nested_path, "r") as nested:
                    nested_tmp = tempfile.mkdtemp(prefix="hawaa_nested_restore_")
                    try:
                        nested_candidate, nested_member = (
                            FileExportService._extract_valid_sqlite_from_zip(
                                nested, nested_tmp
                            )
                        )
                        final_candidate = os.path.join(
                            tmp_dir,
                            f"nested_candidate_{_safe_filename(os.path.basename(nested_candidate))}",
                        )
                        shutil.copy2(nested_candidate, final_candidate)
                        return final_candidate, f"{member}!/{nested_member}"
                    finally:
                        shutil.rmtree(nested_tmp, ignore_errors=True)
            except Exception as ex:
                errors.append(f"{member}: {ex}")
        listed = ", ".join(names[:12])
        extra = " | ".join(errors[:5])
        raise ValueError(
            "ملف ZIP لا يحتوي قاعدة بيانات هوى الشام صالحة. "
            + f"محتوى ZIP: {listed}"
            + (f". أخطاء الفحص: {extra}" if extra else "")
        )

    @staticmethod
    def inspect_backup_archive(backup_path: str) -> dict:
        """Inspect a backup ZIP or direct .db file without modifying current data."""
        FileExportService.log_restore_event(f"inspect backup start: {backup_path}")
        try:
            if not backup_path or not os.path.exists(backup_path):
                FileExportService.log_restore_event(
                    f"restore failed: missing path {backup_path}"
                )
                raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")
            try:
                FileExportService.log_restore_event(
                    f"inspect backup size={os.path.getsize(backup_path)}"
                )
            except Exception:
                pass
            ext = os.path.splitext(str(backup_path))[1].lower()
            if ext in {".db", ".sqlite", ".sqlite3"}:
                info = FileExportService._validate_sqlite_backup_db(backup_path)
                info.update({"format": "sqlite-db", "source": backup_path})
                FileExportService.log_restore_event(f"inspect backup ok db: {info}")
                return info
            if ext != ".zip":
                raise ValueError("صيغة النسخة غير مدعومة. اختر ملف ZIP أو DB")
            with zipfile.ZipFile(backup_path, "r") as zf:
                try:
                    FileExportService.log_restore_event(
                        "inspect zip members: " + ", ".join(zf.namelist()[:20])
                    )
                except Exception:
                    pass
                names = set(zf.namelist())
                tmp_dir = tempfile.mkdtemp(prefix="hawaa_inspect_")
                try:
                    candidate_db, member_name = (
                        FileExportService._extract_valid_sqlite_from_zip(zf, tmp_dir)
                    )
                    info = FileExportService._validate_sqlite_backup_db(candidate_db)
                    info.update(
                        {
                            "format": "hawaa-backup-zip",
                            "source": backup_path,
                            "db_member": member_name,
                            "has_config": "config.json" in names,
                        }
                    )
                    FileExportService.log_restore_event(
                        f"inspect backup ok zip: {info}"
                    )
                    return info
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as ex:
            FileExportService.log_restore_event(
                f"inspect backup failed: {backup_path} :: {ex}"
            )
            raise

    @staticmethod
    def restore_backup_archive(backup_path: str) -> dict:
        """Safely restore and migrate a current or legacy Hawaa backup."""
        from database.connection import DatabaseConnection, get_local_db_path
        from database.migrations import migrate_database_file

        db = DatabaseConnection()
        if db.is_remote():
            raise RuntimeError(
                "أنت في وضع العميل. غيّر الوضع إلى محلي لاستعادة نسخة داخل الهاتف."
            )
        if not backup_path or not os.path.exists(backup_path):
            raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")
        if os.path.getsize(backup_path) > MAX_BACKUP_BYTES:
            raise ValueError("ملف النسخة الاحتياطية يتجاوز الحد الآمن")

        FileExportService.log_restore_event(f"restore backup start: {backup_path}")
        inspected = FileExportService.inspect_backup_archive(backup_path)
        safety_backup = FileExportService.create_backup_archive()
        target_db = get_local_db_path()
        target_dir = os.path.dirname(target_db)
        os.makedirs(target_dir, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(prefix="hawaa_restore_")
        rollback_db = os.path.join(tmp_dir, "current_before_restore.db")
        candidate_db = os.path.join(tmp_dir, "candidate.db")
        config_candidate = None
        target_config = os.path.join(target_dir, "config.json")
        rollback_config = os.path.join(tmp_dir, "current_config_before_restore.json")
        config_existed = os.path.exists(target_config)
        replaced = False
        config_replaced = False
        try:
            if config_existed:
                shutil.copy2(target_config, rollback_config)
            if os.path.exists(target_db):
                src = sqlite3.connect(target_db)
                dst = sqlite3.connect(rollback_db)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()

            ext = os.path.splitext(str(backup_path))[1].lower()
            if ext in {".db", ".sqlite", ".sqlite3"}:
                shutil.copy2(backup_path, candidate_db)
            else:
                with zipfile.ZipFile(backup_path, "r") as zf:
                    extracted_db, _member_name = (
                        FileExportService._extract_valid_sqlite_from_zip(zf, tmp_dir)
                    )
                    shutil.copy2(extracted_db, candidate_db)
                    config_names = [
                        name
                        for name in zf.namelist()
                        if os.path.basename(name) == "config.json"
                    ]
                    if config_names:
                        try:
                            with zf.open(config_names[0]) as file_obj:
                                raw = file_obj.read(2 * 1024 * 1024 + 1)
                            if len(raw) > 2 * 1024 * 1024:
                                raise ValueError(
                                    "ملف إعدادات النسخة أكبر من الحد المسموح"
                                )
                            config_data = json.loads(raw.decode("utf-8"))
                            if not isinstance(config_data, dict):
                                raise ValueError("صيغة ملف إعدادات النسخة غير صحيحة")
                            allowed_prefixes = ("company/", "report/")
                            safe_config = {
                                str(key): value
                                for key, value in config_data.items()
                                if str(key).startswith(allowed_prefixes)
                            }
                            config_candidate = os.path.join(tmp_dir, "config.json")
                            with open(
                                config_candidate, "w", encoding="utf-8"
                            ) as file_obj:
                                json.dump(
                                    safe_config, file_obj, ensure_ascii=False, indent=2
                                )
                        except (
                            OSError,
                            UnicodeDecodeError,
                            ValueError,
                            TypeError,
                        ) as config_exc:
                            # A malformed optional config must not block recovery
                            # of a valid accounting database. Log it and restore
                            # the database without importing those preferences.
                            FileExportService.log_restore_event(
                                f"ignored invalid backup config: {config_exc}"
                            )
                            config_candidate = None

            migration = migrate_database_file(candidate_db, create_admin_if_empty=True)
            FileExportService._validate_sqlite_backup_db(candidate_db)

            preserved_settings = {}
            try:
                local_conn = sqlite3.connect(target_db)
                try:
                    for key in ("network/server_url", "network/allow_insecure_http"):
                        row = local_conn.execute(
                            "SELECT value FROM settings WHERE key=?", (key,)
                        ).fetchone()
                        if row is not None:
                            preserved_settings[key] = row[0]
                finally:
                    local_conn.close()
            except sqlite3.DatabaseError:
                preserved_settings = {}

            candidate_conn = sqlite3.connect(candidate_db)
            try:
                candidate_conn.execute(
                    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
                )
                candidate_conn.execute(
                    "DELETE FROM settings WHERE key='auth/network_token'"
                )
                candidate_conn.execute(
                    "INSERT OR REPLACE INTO settings (key,value) VALUES ('network/mode','local')"
                )
                for key, value in preserved_settings.items():
                    candidate_conn.execute(
                        "INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                        (key, str(value)),
                    )
                candidate_conn.commit()
            finally:
                candidate_conn.close()

            db.close()
            DatabaseConnection.reset_after_restore()
            for sidecar in (target_db + "-wal", target_db + "-shm"):
                try:
                    os.remove(sidecar)
                except FileNotFoundError:
                    pass
            restore_tmp = os.path.join(
                target_dir,
                f".hawaa_restore_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db",
            )
            shutil.copy2(candidate_db, restore_tmp)
            os.replace(restore_tmp, target_db)
            replaced = True
            if config_candidate:
                config_tmp = os.path.join(
                    target_dir,
                    f".hawaa_config_restore_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json",
                )
                shutil.copy2(config_candidate, config_tmp)
                os.replace(config_tmp, target_config)
                config_replaced = True

            migrate_database_file(target_db, create_admin_if_empty=True)
            DatabaseConnection.reset_after_restore()
            verified_counts = FileExportService._count_current_rows()
            FileExportService.log_restore_event(
                f"restore success: {backup_path} -> {target_db} counts={verified_counts} migration={migration}"
            )
            return {
                "ok": True,
                "safety_backup": safety_backup,
                "restored_db": target_db,
                "inspected": inspected,
                "migration": migration,
                "verified_counts": verified_counts,
            }
        except Exception as exc:
            FileExportService.log_restore_event(
                f"restore failed, rollback requested: {exc}"
            )
            if replaced and os.path.exists(rollback_db):
                try:
                    DatabaseConnection.reset_after_restore()
                    rollback_tmp = os.path.join(target_dir, ".hawaa_db_rollback.db")
                    shutil.copy2(rollback_db, rollback_tmp)
                    os.replace(rollback_tmp, target_db)
                    DatabaseConnection.reset_after_restore()
                    FileExportService.log_restore_event("database rollback completed")
                except Exception as rollback_exc:
                    FileExportService.log_restore_event(
                        f"database rollback failed: {rollback_exc}"
                    )
            if config_replaced:
                try:
                    if config_existed and os.path.exists(rollback_config):
                        config_tmp = os.path.join(
                            target_dir, ".hawaa_config_rollback.json"
                        )
                        shutil.copy2(rollback_config, config_tmp)
                        os.replace(config_tmp, target_config)
                    elif os.path.exists(target_config):
                        os.remove(target_config)
                    FileExportService.log_restore_event("config rollback completed")
                except Exception as rollback_exc:
                    FileExportService.log_restore_event(
                        f"config rollback failed: {rollback_exc}"
                    )
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    async def share_file_async(
        page,
        path: str,
        text: str = "",
        *,
        phone: str | None = None,
        open_whatsapp: bool = False,
        title: str = "مشاركة ملف هوى الشام",
    ):
        from reports.share import share_file_async

        return await share_file_async(
            page, path, text, phone=phone, open_whatsapp=open_whatsapp, title=title
        )

    @staticmethod
    def share_file(
        page,
        path: str,
        text: str = "",
        *,
        phone: str | None = None,
        open_whatsapp: bool = False,
    ) -> bool:
        from reports.share import share_file

        return share_file(page, path, text, phone=phone, open_whatsapp=open_whatsapp)

    @staticmethod
    async def open_file_async(page, path: str, *, title: str = "فتح ملف هوى الشام"):
        # Android cannot reliably open private file:// paths from Flet. Use the
        # platform share/open sheet instead. The user can choose browser, Files,
        # printer provider, Drive, WhatsApp, Telegram, etc.
        return await FileExportService.share_file_async(
            page,
            path,
            f"ملف من نظام هوى الشام: {os.path.basename(path)}",
            open_whatsapp=False,
            title=title,
        )

    @staticmethod
    def open_file(page, path: str) -> bool:
        return FileExportService.share_file(
            page,
            path,
            f"ملف من نظام هوى الشام: {os.path.basename(path)}",
            open_whatsapp=False,
        )
