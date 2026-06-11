# -*- coding: utf-8 -*-
"""Report sharing helpers.

The APK-safe strategy is:
1) generate a report file locally;
2) try the Android share sheet when running on Android;
3) fall back to opening the file and WhatsApp web/deep-link with a text note.

Directly attaching a file to a specific WhatsApp conversation is intentionally not
assumed because Android/Flet builds differ in available native APIs. The native
Intent path is best-effort and never blocks the application if unavailable.
"""
from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote


def normalize_phone(phone: Optional[str]) -> str:
    """Return a WhatsApp-compatible number without spaces or symbols."""
    if not phone:
        return ""
    phone = str(phone).strip()
    # Keep leading + only long enough to preserve international numbers, then strip it for wa.me.
    digits = re.sub(r"\D+", "", phone)
    return digits


def file_uri(path: str) -> str:
    try:
        return Path(path).resolve().as_uri()
    except Exception:
        return "file://" + os.path.abspath(path)


def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def build_statement_message(company_name: str, path: str, *, report_type: str = "كشف حساب") -> str:
    filename = os.path.basename(path)
    return (
        f"{report_type} - {company_name}\n"
        f"تم إنشاء الملف: {filename}\n\n"
        "افتح المرفق أو الرابط المرسل لعرض الكشف."
    )


def whatsapp_url(text: str, phone: Optional[str] = None) -> str:
    number = normalize_phone(phone)
    encoded = quote(text or "")
    if number:
        return f"https://wa.me/{number}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def _try_android_share(path: str, text: str, chooser_title: str = "مشاركة التقرير") -> bool:
    """Best-effort Android native share sheet using pyjnius when available."""
    try:
        from jnius import autoclass  # type: ignore

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")

        intent = Intent(Intent.ACTION_SEND)
        intent.setType(guess_mime(path))
        intent.putExtra(Intent.EXTRA_TEXT, text or "")
        intent.putExtra(Intent.EXTRA_STREAM, Uri.parse(file_uri(path)))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(intent, chooser_title)
        PythonActivity.mActivity.startActivity(chooser)
        return True
    except Exception:
        return False


def share_file(page, path: str, text: str = "", *, phone: Optional[str] = None, open_whatsapp: bool = True) -> bool:
    """Share a generated report file with robust fallbacks.

    Returns True if any sharing/opening action was dispatched.
    """
    dispatched = False

    if path and os.path.exists(path):
        dispatched = _try_android_share(path, text) or dispatched

    # Some future/desktop Flet builds may expose a share method. Keep it dynamic.
    try:
        share_method = getattr(page, "share", None)
        if callable(share_method):
            try:
                share_method(text=text, files=[path])
            except TypeError:
                share_method(text)
            dispatched = True
    except Exception:
        pass

    # Always try to open the local report as a fallback so the user can print/share from the viewer.
    try:
        if path and os.path.exists(path) and hasattr(page, "launch_url"):
            page.launch_url(file_uri(path))
            dispatched = True
    except Exception:
        pass

    if open_whatsapp:
        try:
            if hasattr(page, "launch_url"):
                page.launch_url(whatsapp_url(text, phone))
                dispatched = True
        except Exception:
            pass

    return dispatched


def share_text_to_whatsapp(page, text: str, phone: Optional[str] = None) -> bool:
    try:
        if hasattr(page, "launch_url"):
            page.launch_url(whatsapp_url(text, phone))
            return True
    except Exception:
        return False
    return False
