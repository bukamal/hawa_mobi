# -*- coding: utf-8 -*-
"""Report sharing helpers for Android/Flet.

The Android APK is pinned to a Flet line where ``ft.Share`` is not guaranteed
at runtime.  Sharing must therefore be best-effort and must never crash the UI.
Policy:
- Use Flet native Share service only when the runtime actually exposes it.
- Try older Page-level share APIs when present.
- If no native share API exists, copy the generated file to a public Downloads
  fallback when Android permissions allow it, then show a manual export dialog
  with the final path and open/copy actions.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote


@dataclass
class ShareResultInfo:
    ok: bool
    method: str = "none"
    message: str = ""
    raw_status: str = ""
    path: str = ""


def normalize_phone(phone: Optional[str]) -> str:
    """Return a WhatsApp-compatible number without spaces or symbols."""
    if not phone:
        return ""
    phone = str(phone).strip()
    return re.sub(r"\D+", "", phone)


def file_uri(path: str) -> str:
    try:
        return Path(path).resolve().as_uri()
    except Exception:
        return "file://" + os.path.abspath(path)


def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime:
        return mime
    lower = str(path or "").lower()
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "text/html"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".zip"):
        return "application/zip"
    if lower.endswith(".db"):
        return "application/vnd.sqlite3"
    return "application/octet-stream"


def build_statement_message(company_name: str, path: str, *, report_type: str = "كشف حساب") -> str:
    """Build a short caption for file shares.

    Keep this text short.  If native Android sharing fails and the runtime falls
    back to text-only WhatsApp, the user must not receive a misleading message
    that looks like a successful file attachment.
    """
    filename = os.path.basename(path)
    return f"{report_type} - {company_name}\n{filename}"


def whatsapp_url(text: str, phone: Optional[str] = None) -> str:
    number = normalize_phone(phone)
    encoded = quote(text or "")
    if number:
        return f"https://wa.me/{number}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def _share_status_ok(result) -> bool:
    """Interpret Flet ShareResult without binding to a single Flet version."""
    status = getattr(result, "status", None)
    text = str(status or result or "").lower()
    return any(token in text for token in ("success", "dismiss", "completed", "shared", "ok")) or bool(result)


def _path_to_share_file(ft, path: str):
    """Build a Flet ShareFile when the runtime exposes that service."""
    name = os.path.basename(path) or "hawaa_export"
    mime = guess_mime(path)
    share_file_cls = getattr(ft, "ShareFile", None)
    if share_file_cls is None:
        raise AttributeError("flet runtime has no ShareFile")
    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0
    if size and size <= 25 * 1024 * 1024 and hasattr(share_file_cls, "from_bytes"):
        try:
            with open(path, "rb") as f:
                return share_file_cls.from_bytes(f.read(), mime_type=mime, name=name)
        except Exception:
            pass
    if hasattr(share_file_cls, "from_path"):
        try:
            return share_file_cls.from_path(path, name=name)
        except TypeError:
            return share_file_cls.from_path(path)
    raise AttributeError("flet ShareFile does not support from_path/from_bytes")


def _public_download_roots() -> list[str]:
    roots: list[str] = []
    for candidate in (
        os.environ.get("PUBLIC_DOWNLOADS"),
        os.path.join(os.environ.get("EXTERNAL_STORAGE", ""), "Download") if os.environ.get("EXTERNAL_STORAGE") else "",
        "/storage/emulated/0/Download",
        "/sdcard/Download",
    ):
        if candidate and candidate not in roots:
            roots.append(candidate)
    return roots


def copy_to_public_downloads(path: str, *, subdir: str = "Hawaa") -> Optional[str]:
    """Best-effort Android fallback: copy an export to Downloads/Hawaa.

    Android 10 and some vendor builds allow this with WRITE_EXTERNAL_STORAGE.
    Android 11+ may reject it under scoped storage; callers must tolerate None.
    """
    if not path or not os.path.exists(path):
        return None
    for root in _public_download_roots():
        try:
            target_dir = os.path.join(root, subdir)
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, os.path.basename(path))
            shutil.copy2(path, target)
            if os.path.exists(target):
                return target
        except Exception:
            continue
    return None


def _call_maybe_async(value):
    if asyncio.iscoroutine(value):
        return value
    return None



def _load_jnius_runtime():
    """Return pyjnius helpers only on Android runtimes that expose them."""
    try:
        jnius = __import__("jnius")
        return getattr(jnius, "autoclass"), getattr(jnius, "cast", None)
    except Exception:
        return None, None


def _android_context():
    autoclass, _cast = _load_jnius_runtime()
    if autoclass is None:
        return None
    # Flet Android generally exposes the current Application via ActivityThread.
    # Use application context + FLAG_ACTIVITY_NEW_TASK to avoid relying on Kivy
    # classes or a specific Flet Activity class name.
    for class_name, method_name in (
        ("android.app.ActivityThread", "currentApplication"),
    ):
        try:
            cls = autoclass(class_name)
            method = getattr(cls, method_name)
            app = method()
            if app is not None:
                try:
                    return app.getApplicationContext()
                except Exception:
                    return app
        except Exception:
            continue
    return None


def _android_sdk_int() -> int:
    autoclass, _cast = _load_jnius_runtime()
    if autoclass is None:
        return 0
    try:
        BuildVersion = autoclass("android.os.Build$VERSION")
        return int(getattr(BuildVersion, "SDK_INT", 0) or 0)
    except Exception:
        return 0


def _content_values_put(values, key: str, value):
    """Best-effort ContentValues.put wrapper for pyjnius overloads."""
    try:
        values.put(key, value)
        return
    except Exception:
        pass
    try:
        values.put(str(key), str(value))
        return
    except Exception:
        pass


def _android_insert_file_into_downloads(path: str, *, display_name: str | None = None, mime: str | None = None):
    """Copy a private/internal file into MediaStore and return a content:// Uri.

    This is the key Android fix for WhatsApp/share/print.  WhatsApp cannot read
    the app's private ``/data/user/0/...`` path and a text-only ``wa.me`` URL
    never attaches the generated report.  MediaStore gives Android and other
    apps a readable ``content://`` URI without requiring a manifest FileProvider.
    """
    if not path or not os.path.exists(path):
        return None, "missing file"
    autoclass, _cast = _load_jnius_runtime()
    context = _android_context()
    if autoclass is None or context is None:
        return None, "android runtime unavailable"
    name = display_name or os.path.basename(path) or "hawaa_export"
    mime = mime or guess_mime(path)
    try:
        ContentValues = autoclass("android.content.ContentValues")
        MediaStore = autoclass("android.provider.MediaStore")
        values = ContentValues()
        _content_values_put(values, MediaStore.MediaColumns.DISPLAY_NAME, name)
        _content_values_put(values, MediaStore.MediaColumns.MIME_TYPE, mime)
        sdk = _android_sdk_int()
        if sdk >= 29:
            _content_values_put(values, MediaStore.MediaColumns.RELATIVE_PATH, "Download/Hawaa")
            _content_values_put(values, MediaStore.MediaColumns.IS_PENDING, 1)
            collection = MediaStore.Downloads.EXTERNAL_CONTENT_URI
        else:
            # Older Android: use MediaStore.Files when possible, otherwise fall
            # back to a public copy + file URI in the caller.
            try:
                collection = MediaStore.Files.getContentUri("external")
            except Exception:
                collection = MediaStore.Downloads.EXTERNAL_CONTENT_URI
        resolver = context.getContentResolver()
        uri = resolver.insert(collection, values)
        if uri is None:
            return None, "MediaStore insert returned null"
        stream = resolver.openOutputStream(uri)
        if stream is None:
            return None, "MediaStore output stream unavailable"
        try:
            with open(path, "rb") as src:
                while True:
                    chunk = src.read(1024 * 64)
                    if not chunk:
                        break
                    stream.write(chunk)
            try:
                stream.flush()
            except Exception:
                pass
        finally:
            try:
                stream.close()
            except Exception:
                pass
        if sdk >= 29:
            try:
                done = ContentValues()
                _content_values_put(done, MediaStore.MediaColumns.IS_PENDING, 0)
                resolver.update(uri, done, None, None)
            except Exception:
                pass
        return uri, "ok"
    except Exception as exc:
        return None, str(exc)


def _android_file_uri(path: str):
    autoclass, _cast = _load_jnius_runtime()
    if autoclass is None:
        return None
    try:
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        return Uri.fromFile(File(path))
    except Exception:
        return None



def _android_copy_to_cache_for_share(path: str) -> tuple[str | None, str]:
    """Copy a report into Android app cache for WhatsApp-only sharing.

    MediaStore copies are useful for public visibility, but some WhatsApp builds
    ignore MediaStore document streams and send only EXTRA_TEXT.  For the
    WhatsApp button we therefore first create a clean file inside the APK cache
    and share that stream.  The cache file is temporary; external apps get read
    access only through the outgoing intent flags.
    """
    if not path or not os.path.exists(path):
        return None, "missing file"
    context = _android_context()
    cache_root = None
    if context is not None:
        try:
            cache_root = str(context.getCacheDir().getAbsolutePath())
        except Exception:
            cache_root = None
    if not cache_root:
        cache_root = os.environ.get("FLET_APP_STORAGE_TEMP") or os.environ.get("TMPDIR") or os.path.dirname(path)
    try:
        target_dir = os.path.join(cache_root, "hawaa_whatsapp_share")
        os.makedirs(target_dir, exist_ok=True)
        # Clear stale exports so WhatsApp sees only the fresh document.
        try:
            for old in Path(target_dir).glob("*"):
                if old.is_file():
                    try:
                        old.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
        target = os.path.join(target_dir, os.path.basename(path) or f"hawaa_export_{int(time.time())}.html")
        shutil.copy2(path, target)
        if os.path.exists(target) and os.path.getsize(target) > 0:
            return target, "ok"
        return None, "cache copy failed"
    except Exception as exc:
        return None, str(exc)


def _disable_file_uri_exposure_guard() -> None:
    """Allow last-resort file:// sharing on Android builds without FileProvider.

    We still prefer content://.  This is only a fallback for the user's APK line
    where configuring a manifest provider is not available through the current
    Flet build pipeline.
    """
    autoclass, _cast = _load_jnius_runtime()
    if autoclass is None:
        return
    try:
        StrictMode = autoclass("android.os.StrictMode")
        disable = getattr(StrictMode, "disableDeathOnFileUriExposure", None)
        if callable(disable):
            disable()
    except Exception:
        pass


def _android_fileprovider_uri(path: str):
    """Try AndroidX/support FileProvider authorities when the APK has one."""
    autoclass, _cast = _load_jnius_runtime()
    context = _android_context()
    if autoclass is None or context is None or not path:
        return None, "runtime unavailable"
    try:
        File = autoclass("java.io.File")
        try:
            package_name = str(context.getPackageName())
        except Exception:
            package_name = "com.hawaa.hawaa_accounting"
        authorities = [
            f"{package_name}.fileprovider",
            f"{package_name}.provider",
            f"{package_name}.flutter.share_provider",
        ]
        providers = []
        for cls_name in ("androidx.core.content.FileProvider", "android.support.v4.content.FileProvider"):
            try:
                providers.append(autoclass(cls_name))
            except Exception:
                pass
        last = "FileProvider class unavailable"
        for provider in providers:
            for authority in authorities:
                try:
                    uri = provider.getUriForFile(context, authority, File(path))
                    if uri is not None:
                        return uri, f"fileprovider:{authority}"
                except Exception as exc:
                    last = str(exc)
        return None, last
    except Exception as exc:
        return None, str(exc)


def _android_cache_uri_for_whatsapp(path: str):
    """Return a URI for a cache-only WhatsApp share."""
    cache_path, status = _android_copy_to_cache_for_share(path)
    if not cache_path:
        return None, None, status
    uri, provider_status = _android_fileprovider_uri(cache_path)
    if uri is not None:
        return uri, cache_path, provider_status
    _disable_file_uri_exposure_guard()
    uri = _android_file_uri(cache_path)
    if uri is not None:
        return uri, cache_path, f"cache_file_uri:{provider_status}"
    return None, cache_path, f"cache uri failed:{provider_status}"

def _android_start_send_intent(uri, *, mime: str, text: str, title: str, open_whatsapp: bool = False) -> tuple[bool, str]:
    autoclass, _cast = _load_jnius_runtime()
    context = _android_context()
    if autoclass is None or context is None or uri is None:
        return False, "android intent runtime unavailable"
    try:
        Intent = autoclass("android.content.Intent")
        ActivityNotFoundException = autoclass("android.content.ActivityNotFoundException")
    except Exception as exc:
        return False, str(exc)

    def build_intent(package_name: str | None = None):
        intent = Intent(Intent.ACTION_SEND)
        # WhatsApp must receive a pure document stream.  If EXTRA_TEXT is added,
        # several WhatsApp builds send the text only and silently drop the file.
        intent.setType("application/octet-stream" if open_whatsapp else (mime or "application/octet-stream"))
        if text and not open_whatsapp:
            intent.putExtra(Intent.EXTRA_TEXT, text)
        if title:
            intent.putExtra(Intent.EXTRA_SUBJECT, title)
            try:
                intent.putExtra(Intent.EXTRA_TITLE, title)
            except Exception:
                pass
        intent.putExtra(Intent.EXTRA_STREAM, uri)
        try:
            ClipData = autoclass("android.content.ClipData")
            resolver = context.getContentResolver()
            intent.setClipData(ClipData.newUri(resolver, title or "Hawaa", uri))
        except Exception:
            pass
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if package_name:
            intent.setPackage(package_name)
            try:
                context.grantUriPermission(package_name, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            except Exception:
                pass
        return intent

    if open_whatsapp:
        for package_name in ("com.whatsapp", "com.whatsapp.w4b"):
            try:
                context.startActivity(build_intent(package_name))
                return True, package_name
            except Exception as exc:
                # Try business/chooser next.  Do not fail the whole operation.
                last = str(exc)
        try:
            chooser = Intent.createChooser(build_intent(None), title or "مشاركة ملف")
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(chooser)
            return True, "chooser_after_whatsapp"
        except Exception as exc:
            return False, str(exc)

    try:
        chooser = Intent.createChooser(build_intent(None), title or "مشاركة ملف")
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(chooser)
        return True, "chooser"
    except Exception as exc:
        return False, str(exc)


async def _try_android_native_share(path: str, text: str, title: str, *, open_whatsapp: bool = False) -> ShareResultInfo:
    """Android-native ACTION_SEND fallback with a real file attachment.

    This runs before Flet's ``ft.Share``/page APIs because the user's APK line
    does not expose ft.Share, and URL-based WhatsApp fallback sends text only.
    """
    if not path or not os.path.exists(path):
        return ShareResultInfo(False, "android_native_missing", "الملف غير موجود", path=path or "")
    if _android_context() is None:
        return ShareResultInfo(False, "android_native_unavailable", "Android runtime غير متاح", path=path)
    mime = guess_mime(path)
    if open_whatsapp:
        uri, cache_path, status = _android_cache_uri_for_whatsapp(path)
        if uri is not None:
            ok, raw = _android_start_send_intent(uri, mime=mime, text="", title=title, open_whatsapp=True)
            if ok:
                return ShareResultInfo(True, "android_cache_whatsapp", "تم فتح واتساب مع ملف الكشف من الكاش", raw, path=cache_path or path)
        # If cache-only fails, continue to MediaStore fallback but still without
        # EXTRA_TEXT so WhatsApp cannot degrade to text-only.
        cache_status = status
    else:
        cache_status = ""

    uri, status = _android_insert_file_into_downloads(path, display_name=os.path.basename(path), mime=mime)
    if uri is None:
        public_path = copy_to_public_downloads(path) or path
        uri = _android_file_uri(public_path)
        if uri is None:
            return ShareResultInfo(False, "android_native_uri_failed", f"{cache_status}; {status}".strip('; '), path=public_path)
        final_path = public_path
    else:
        final_path = path
    ok, raw = _android_start_send_intent(uri, mime=mime, text=("" if open_whatsapp else text), title=title, open_whatsapp=open_whatsapp)
    if ok:
        return ShareResultInfo(True, "android_native_whatsapp" if open_whatsapp else "android_native_share", "تم فتح نافذة المشاركة مع الملف المرفق", raw, path=final_path)
    return ShareResultInfo(False, "android_native_intent_failed", raw, path=final_path)


async def _try_page_share_api(page, path: str, text: str, title: str) -> ShareResultInfo:
    """Try dynamic page-level share methods used by some Flet runtimes."""
    if page is None:
        return ShareResultInfo(False, "page_share_missing", "لا توجد صفحة فعالة", path=path)
    attempts = []
    for name in ("share_files", "share"):
        method = getattr(page, name, None)
        if callable(method):
            attempts.append((name, method))
    last_error = ""
    for name, method in attempts:
        for kwargs in (
            {"files": [path], "text": text, "title": title},
            {"file_paths": [path], "text": text, "title": title},
            {"path": path, "text": text, "title": title},
            {"text": f"{text}\n{path}"},
        ):
            try:
                maybe = method(**kwargs)
                if asyncio.iscoroutine(maybe):
                    await maybe
                return ShareResultInfo(True, name, "تم فتح نافذة المشاركة", str(maybe), path=path)
            except TypeError as exc:
                last_error = str(exc)
                continue
            except Exception as exc:
                last_error = str(exc)
                break
    return ShareResultInfo(False, "page_share_unavailable", last_error, path=path)


def _show_manual_export_dialog(page, path: str, *, title: str, text: str = "", open_whatsapp: bool = False, phone: Optional[str] = None) -> bool:
    """Show a non-fatal manual export dialog when native sharing is unavailable."""
    if page is None:
        return False
    try:
        import flet as ft  # type: ignore
        from views.flet_compat import open_control, close_control
    except Exception:
        return False

    message = (
        "تم إنشاء الملف، لكن نسخة Flet داخل هذا APK لا توفر خدمة مشاركة ملفات مباشرة.\n"
        "استعمل الأزرار التالية، أو افتح المسار يدويًا من مدير الملفات إذا كان داخل Downloads/Hawaa."
    )
    path_text = ft.Text(path, selectable=True, size=11, color=ft.Colors.GREY_800, rtl=False)
    dlg = None

    def _snack(msg: str, is_error: bool = False):
        try:
            from views.flet_compat import show_snackbar
            show_snackbar(page, msg, is_error=is_error, duration=3500)
        except Exception:
            pass

    def _copy(ev=None):
        try:
            setter = getattr(page, "set_clipboard", None)
            if callable(setter):
                setter(path)
                _snack("تم نسخ مسار الملف")
            else:
                _snack("نسخ المسار غير مدعوم في هذه النسخة", True)
        except Exception as exc:
            _snack(f"تعذر نسخ المسار: {exc}", True)

    def _open(ev=None):
        try:
            launcher = getattr(page, "launch_url", None)
            if callable(launcher):
                launcher(file_uri(path))
                _snack("تم طلب فتح الملف")
            else:
                _snack("فتح الروابط غير مدعوم في هذه النسخة", True)
        except Exception as exc:
            _snack(f"تعذر فتح الملف: {exc}", True)

    def _wa(ev=None):
        try:
            launcher = getattr(page, "launch_url", None)
            if callable(launcher):
                launcher(whatsapp_url((text or "") + "\n" + os.path.basename(path), phone))
                _snack("تم فتح واتساب للنص فقط")
            else:
                _snack("فتح واتساب غير مدعوم", True)
        except Exception as exc:
            _snack(f"تعذر فتح واتساب: {exc}", True)

    actions = [
        ft.TextButton("نسخ المسار", on_click=_copy),
        ft.TextButton("فتح الملف", on_click=_open),
    ]
    if open_whatsapp:
        actions.append(ft.TextButton("واتساب نص فقط", on_click=_wa))
    actions.append(ft.TextButton("إغلاق", on_click=lambda ev: close_control(page, dlg)))

    try:
        dlg = ft.AlertDialog(
            modal=False,
            title=ft.Text(title or "ملف جاهز"),
            content=ft.Container(
                width=420,
                content=ft.Column([
                    ft.Text(message, size=12),
                    ft.Divider(),
                    ft.Text("المسار:", size=12, weight=ft.FontWeight.BOLD),
                    path_text,
                ], tight=True, spacing=8),
            ),
            actions=actions,
        )
        open_control(page, dlg)
        return True
    except Exception:
        return False


async def share_file_async(
    page,
    path: str,
    text: str = "",
    *,
    phone: Optional[str] = None,
    open_whatsapp: bool = False,
    title: str = "مشاركة ملف هوى الشام",
) -> ShareResultInfo:
    """Share or expose a generated file without crashing Android Flet 0.28.x."""
    if not path or not os.path.exists(path):
        return ShareResultInfo(False, "missing", "الملف غير موجود", path=path or "")

    errors: list[str] = []

    # 1) Android-native ACTION_SEND with a real content:// file attachment.
    # This is the most reliable path for the APK runtime when ft.Share is absent.
    android_share = await _try_android_native_share(path, text, title, open_whatsapp=open_whatsapp)
    if android_share.ok:
        return android_share
    if android_share.message:
        errors.append(f"{android_share.method}: {android_share.message}")

    # 2) Modern Flet service, only when available in the actual runtime.
    try:
        import flet as ft  # type: ignore
        share_cls = getattr(ft, "Share", None)
        if share_cls is not None and hasattr(share_cls, "share_files"):
            share = share_cls()
            share_file = _path_to_share_file(ft, path)
            result = await share.share_files([share_file], title=title, text=text or None, subject=title)
            return ShareResultInfo(_share_status_ok(result), "flet_share", "تم فتح نافذة المشاركة", str(getattr(result, "status", result)), path=path)
        errors.append("خدمة ft.Share غير موجودة في نسخة Flet الحالية")
    except Exception as exc:
        errors.append(str(exc))

    # 3) Older/dynamic page-level share APIs, if this runtime provides them.
    page_share = await _try_page_share_api(page, path, text, title)
    if page_share.ok:
        return page_share
    if page_share.message:
        errors.append(page_share.message)

    # 4) Copy to a public Downloads/Hawaa fallback when Android permissions allow it.
    public_path = copy_to_public_downloads(path)
    final_path = public_path or path

    # 5) Do not auto-open wa.me text-only fallback for file actions.
    # The user expects the report file to be attached.  If Android native file
    # sharing failed, show the manual dialog and let the user explicitly choose
    # "واتساب نص فقط" if they still want a text message.
    if open_whatsapp:
        errors.append("تم تعطيل fallback واتساب النصي التلقائي حتى لا تُرسل رسالة بلا ملف")

    # 6) Manual non-crashing export dialog.
    if _show_manual_export_dialog(page, final_path, title=title, text=text, open_whatsapp=open_whatsapp, phone=phone):
        if public_path:
            return ShareResultInfo(True, "manual_public_downloads", "تم إنشاء الملف ونسخه إلى Downloads/Hawaa", "; ".join(errors), path=final_path)
        return ShareResultInfo(True, "manual_internal_path", "تم إنشاء الملف. افتح نافذة التفاصيل لنسخ المسار أو محاولة فتحه", "; ".join(errors), path=final_path)

    # Last fallback: try opening the file URI directly. Do not expose the old
    # ft.Share AttributeError to the user as a red failure.
    try:
        if hasattr(page, "launch_url"):
            page.launch_url(file_uri(final_path))
            return ShareResultInfo(True, "file_uri", "تم إنشاء الملف ومحاولة فتحه", "; ".join(errors), path=final_path)
    except Exception as exc:
        errors.append(str(exc))

    return ShareResultInfo(False, "none", "تم إنشاء الملف لكن تعذر فتح نافذة مشاركة في نسخة Flet الحالية", "; ".join(errors), path=final_path)


def share_file(page, path: str, text: str = "", *, phone: Optional[str] = None, open_whatsapp: bool = True) -> bool:
    """Compatibility wrapper for older synchronous callers."""
    try:
        from views.flet_compat import run_async_task
        run_async_task(page, share_file_async, page, path, text, phone=phone, open_whatsapp=open_whatsapp)
        return True
    except Exception:
        try:
            coro = share_file_async(page, path, text, phone=phone, open_whatsapp=open_whatsapp)
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.ensure_future(coro)
                    return True
            except Exception:
                pass
            return asyncio.run(coro).ok
        except Exception:
            return False


async def share_text_to_whatsapp_async(page, text: str, phone: Optional[str] = None) -> ShareResultInfo:
    try:
        if hasattr(page, "launch_url"):
            page.launch_url(whatsapp_url(text, phone))
            return ShareResultInfo(True, "whatsapp_text", "تم فتح واتساب للنص")
    except Exception as exc:
        return ShareResultInfo(False, "none", str(exc))
    return ShareResultInfo(False, "none", "لا توجد خدمة فتح روابط")


def share_text_to_whatsapp(page, text: str, phone: Optional[str] = None) -> bool:
    try:
        from views.flet_compat import run_async_task
        run_async_task(page, share_text_to_whatsapp_async, page, text, phone)
        return True
    except Exception:
        try:
            coro = share_text_to_whatsapp_async(page, text, phone)
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.ensure_future(coro)
                    return True
            except Exception:
                pass
            return asyncio.run(coro).ok
        except Exception:
            return False
