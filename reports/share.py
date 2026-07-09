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
    filename = os.path.basename(path)
    return (
        f"{report_type} - {company_name}\n"
        f"تم إنشاء الملف: {filename}\n\n"
        "اختر التطبيق المناسب من نافذة المشاركة لفتح الملف أو حفظه أو إرساله."
    )


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

    # 1) Modern Flet service, only when available in the actual runtime.
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

    # 2) Older/dynamic page-level share APIs, if this runtime provides them.
    page_share = await _try_page_share_api(page, path, text, title)
    if page_share.ok:
        return page_share
    if page_share.message:
        errors.append(page_share.message)

    # 3) Copy to a public Downloads/Hawaa fallback when Android permissions allow it.
    public_path = copy_to_public_downloads(path)
    final_path = public_path or path

    # 4) Text-only WhatsApp fallback. It cannot attach the file reliably.
    if open_whatsapp:
        try:
            if hasattr(page, "launch_url"):
                page.launch_url(whatsapp_url((text or "") + "\n" + os.path.basename(final_path), phone))
                _show_manual_export_dialog(page, final_path, title=title, text=text, open_whatsapp=False, phone=phone)
                return ShareResultInfo(True, "whatsapp_text_manual_file", "تم فتح واتساب للنص فقط، والملف جاهز من نافذة التفاصيل", path=final_path)
        except Exception as exc:
            errors.append(str(exc))

    # 5) Manual non-crashing export dialog.
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
