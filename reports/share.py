# -*- coding: utf-8 -*-
"""Report sharing helpers for Android/Flet.

Important Android rule:
- Do not pretend that ``file://`` opening means the file was shared.
- Prefer Flet's native Share service (``ft.Share`` + ``ft.ShareFile``), which
  uses the platform share sheet.
- Keep web/WhatsApp URL opening as a text-only fallback, not as proof that the
  file attachment was delivered.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
import re
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
    # Showing the Android share sheet may return success or dismissed depending
    # on user action/platform. Both mean the native sheet was invoked.
    return any(token in text for token in ("success", "dismiss", "completed", "shared", "ok")) or bool(result)


def _path_to_share_file(ft, path: str):
    """Build ShareFile. Prefer bytes for Android scoped-storage reliability."""
    name = os.path.basename(path) or "hawaa_export"
    mime = guess_mime(path)
    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0

    # For typical reports/backups this is more reliable than exposing a raw
    # private app path. Use path for large files to avoid excessive memory use.
    if size and size <= 25 * 1024 * 1024:
        try:
            with open(path, "rb") as f:
                return ft.ShareFile.from_bytes(f.read(), mime_type=mime, name=name)
        except Exception:
            pass
    try:
        return ft.ShareFile.from_path(path, name=name)
    except TypeError:
        return ft.ShareFile.from_path(path)


async def share_file_async(
    page,
    path: str,
    text: str = "",
    *,
    phone: Optional[str] = None,
    open_whatsapp: bool = False,
    title: str = "مشاركة ملف هوى الشام",
) -> ShareResultInfo:
    """Share a file through the platform share sheet.

    The returned ``ok`` means a platform share/open intent was dispatched; it
    does not mean the user completed sending the file.
    """
    if not path or not os.path.exists(path):
        return ShareResultInfo(False, "missing", "الملف غير موجود")

    # 1) Preferred modern Flet API. Docs define ft.Share and ft.ShareFile for
    # sharing text/links/files using the platform sheet.
    try:
        import flet as ft  # type: ignore

        share = ft.Share()
        share_file = _path_to_share_file(ft, path)
        result = await share.share_files([share_file], title=title, text=text or None, subject=title)
        return ShareResultInfo(_share_status_ok(result), "flet_share", "تم فتح نافذة المشاركة", str(getattr(result, "status", result)))
    except Exception as exc:
        last_error = str(exc)

    # 2) Older/dynamic Flet Page share API, if available.
    try:
        share_method = getattr(page, "share", None)
        if callable(share_method):
            maybe = share_method(text=text, files=[path])
            if asyncio.iscoroutine(maybe):
                await maybe
            return ShareResultInfo(True, "page_share", "تم طلب المشاركة")
    except Exception as exc:
        last_error = f"{last_error}; {exc}" if 'last_error' in locals() else str(exc)

    # 3) Text-only WhatsApp fallback. It cannot attach the file reliably.
    if open_whatsapp:
        try:
            if hasattr(page, "launch_url"):
                page.launch_url(whatsapp_url(text, phone))
                return ShareResultInfo(True, "whatsapp_text", "تم فتح واتساب للنص فقط")
        except Exception as exc:
            last_error = f"{last_error}; {exc}" if 'last_error' in locals() else str(exc)

    return ShareResultInfo(False, "none", f"تعذر فتح نافذة المشاركة: {last_error if 'last_error' in locals() else ''}".strip())


def share_file(page, path: str, text: str = "", *, phone: Optional[str] = None, open_whatsapp: bool = True) -> bool:
    """Compatibility wrapper for older synchronous callers.

    Prefer ``await share_file_async(...)`` in UI code. This wrapper schedules the
    native share task when possible and returns True only if scheduling happened.
    """
    try:
        coro = share_file_async(page, path, text, phone=phone, open_whatsapp=open_whatsapp)
        runner = getattr(page, "run_task", None)
        if callable(runner):
            runner(coro)
            return True
        try:
            loop = asyncio.get_event_loop()
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
        return asyncio.run(share_text_to_whatsapp_async(page, text, phone)).ok
    except Exception:
        return False
