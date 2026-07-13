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
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote, urlparse


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
    def restore_log_path() -> str:
        path = os.path.join(_app_storage_dir(), "logs")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "backup_restore.log")

    @staticmethod
    def log_restore_event(message: str) -> None:
        try:
            with open(FileExportService.restore_log_path(), "a", encoding="utf-8") as f:
                f.write(f"[{_dt.datetime.now().isoformat(timespec='seconds')}] {message}\n")
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
            return [line.rstrip("\n") for line in data[-max(1, int(lines or 40)):]]
        except Exception:
            return []

    @staticmethod
    def find_external_backup_archives(limit: int = 12, *, validate: bool = True) -> list[str]:
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
                                if name.endswith(suffixes) and FileExportService._is_readable_file(entry.path):
                                    candidates.append(entry.path)
                            elif entry.is_dir() and depth < 2:
                                # Keep the scan bounded; large phone storage
                                # walks are slow and unreliable on Android.
                                stack.append((entry.path, depth + 1))
                        except Exception:
                            continue
            except Exception:
                continue
        candidates = sorted(set(candidates), key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
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
                FileExportService.log_restore_event(f"skip invalid external candidate: {path} :: {ex}")
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
            os.path.join(os.environ.get("EXTERNAL_STORAGE", ""), "Download") if os.environ.get("EXTERNAL_STORAGE") else "",
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
    def _write_picker_bytes_to_cache(raw_value, *, suggested_name: str = "hawaa_import.zip") -> str | None:
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
        safe_name = _safe_filename(os.path.basename(suggested_name or "hawaa_import.zip"))
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
    def _copy_android_content_uri_to_cache(content_uri: str, *, suggested_name: str = "hawaa_import.zip") -> str | None:
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
            safe_name = _safe_filename(os.path.basename(suggested_name or "hawaa_import.zip"))
            lower = safe_name.lower()
            if not lower.endswith((".zip", ".db", ".sqlite", ".sqlite3")):
                safe_name += ".zip"
            target = FileExportService.build_path(f"picked_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_name}", "picked_imports", temporary=True)
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
    def _find_readable_backup_by_name(name: str, *, size: int | None = None) -> str | None:
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
                    if os.path.isfile(p) and item == name and FileExportService._is_readable_file(p):
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
        candidates = sorted(set(candidates), key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
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
            FileExportService.log_restore_event("picker result: " + FileExportService.describe_picker_file(file_obj))
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
                suggested_name=str(getattr(file_obj, "name", None) or "hawaa_import.zip"),
            )
            if materialized:
                FileExportService.log_restore_event(f"picker bytes materialized: {materialized}")
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
                copied = FileExportService._copy_android_content_uri_to_cache(value, suggested_name=str(display_name or "hawaa_import.zip"))
                if copied and FileExportService._is_readable_file(copied):
                    FileExportService.log_restore_event(f"content uri copied: {copied}")
                    return copied
                continue
            if FileExportService._is_readable_file(value):
                FileExportService.log_restore_event(f"direct readable picker path: {value}")
                return value

        # 3: common Android/Flet case: only a display name was returned.
        if display_name:
            found = FileExportService._find_readable_backup_by_name(str(display_name), size=display_size)
            if found:
                FileExportService.log_restore_event(f"found backup by display name: {found}")
                return found
        for _attr, raw in candidates:
            base = os.path.basename(str(raw or ""))
            if base:
                found = FileExportService._find_readable_backup_by_name(base, size=display_size)
                if found:
                    FileExportService.log_restore_event(f"found backup by basename: {found}")
                    return found
        FileExportService.log_restore_event("picker result could not be resolved")
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
    def _extract_valid_sqlite_from_zip(zf: zipfile.ZipFile, tmp_dir: str) -> tuple[str, str]:
        """Extract the first valid Hawaa SQLite DB from a backup ZIP.

        Older/exported/shared backups are not guaranteed to keep ``hawaa_data.db``
        at the ZIP root.  Accept a valid SQLite DB anywhere in the archive and
        prefer the canonical name.  This fixes external backups saved by Files,
        Drive, WhatsApp, or manually re-zipped folders.
        """
        names = [n for n in zf.namelist() if not n.endswith("/")]
        preferred = [n for n in names if os.path.basename(n).lower() == "hawaa_data.db"]
        db_candidates = preferred + [
            n for n in names
            if n not in preferred and os.path.basename(n).lower().endswith((".db", ".sqlite", ".sqlite3"))
        ]
        errors: list[str] = []
        for member in db_candidates:
            safe_member = _safe_filename(os.path.basename(member))
            candidate = os.path.join(tmp_dir, f"candidate_{len(errors)}_{safe_member}")
            try:
                with zf.open(member) as src, open(candidate, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                FileExportService._validate_sqlite_backup_db(candidate)
                return candidate, member
            except Exception as ex:
                errors.append(f"{member}: {ex}")
                try:
                    os.remove(candidate)
                except Exception:
                    pass
        # One extra tolerant case: a ZIP that contains exactly one nested ZIP.
        nested_zips = [n for n in names if os.path.basename(n).lower().endswith(".zip")]
        for member in nested_zips[:3]:
            nested_path = os.path.join(tmp_dir, f"nested_{_safe_filename(os.path.basename(member))}")
            try:
                with zf.open(member) as src, open(nested_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                with zipfile.ZipFile(nested_path, "r") as nested:
                    nested_tmp = tempfile.mkdtemp(prefix="hawaa_nested_restore_")
                    try:
                        nested_candidate, nested_member = FileExportService._extract_valid_sqlite_from_zip(nested, nested_tmp)
                        final_candidate = os.path.join(tmp_dir, f"nested_candidate_{_safe_filename(os.path.basename(nested_candidate))}")
                        shutil.copy2(nested_candidate, final_candidate)
                        return final_candidate, f"{member}!/{nested_member}"
                    except Exception as ex:
                        errors.append(f"{member}: {ex}")
                    finally:
                        shutil.rmtree(nested_tmp, ignore_errors=True)
            except Exception as ex:
                errors.append(f"{member}: {ex}")
        listed = ", ".join(names[:12])
        extra = " | ".join(errors[:5])
        raise ValueError(
            "ملف ZIP لا يحتوي قاعدة بيانات هوى الشام صالحة. "
            f"محتوى ZIP: {listed}" + (f". أخطاء الفحص: {extra}" if extra else "")
        )

    @staticmethod
    def inspect_backup_archive(backup_path: str) -> dict:
        """Inspect a backup ZIP or direct .db file without modifying current data."""
        FileExportService.log_restore_event(f"inspect backup start: {backup_path}")
        try:
            if not backup_path or not os.path.exists(backup_path):
                FileExportService.log_restore_event(f"restore failed: missing path {backup_path}")
                raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")
            try:
                FileExportService.log_restore_event(f"inspect backup size={os.path.getsize(backup_path)}")
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
                    FileExportService.log_restore_event("inspect zip members: " + ", ".join(zf.namelist()[:20]))
                except Exception:
                    pass
                names = set(zf.namelist())
                tmp_dir = tempfile.mkdtemp(prefix="hawaa_inspect_")
                try:
                    candidate_db, member_name = FileExportService._extract_valid_sqlite_from_zip(zf, tmp_dir)
                    info = FileExportService._validate_sqlite_backup_db(candidate_db)
                    info.update({
                        "format": "hawaa-backup-zip",
                        "source": backup_path,
                        "db_member": member_name,
                        "has_config": "config.json" in names,
                    })
                    FileExportService.log_restore_event(f"inspect backup ok zip: {info}")
                    return info
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as ex:
            FileExportService.log_restore_event(f"inspect backup failed: {backup_path} :: {ex}")
            raise

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
            FileExportService.log_restore_event(f"restore failed: missing path {backup_path}")
            raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود")

        FileExportService.log_restore_event(f"restore backup start: {backup_path}")
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
                    extracted_db, _member_name = FileExportService._extract_valid_sqlite_from_zip(zf, tmp_dir)
                    shutil.copy2(extracted_db, candidate_db)
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
            FileExportService.log_restore_event(f"restore success: {backup_path} -> {target_db} counts={verified_counts}")
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
