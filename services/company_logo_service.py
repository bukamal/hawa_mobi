# -*- coding: utf-8 -*-
"""Company logo import/storage helpers for Android/Flet reports.

Android must not rely on arbitrary external paths in reports.  A selected logo is
copied into app-owned storage, and print HTML embeds it as a data URI so the
logo survives sharing/opening outside the app.
"""

from __future__ import annotations

import base64
import os
import shutil
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 3 * 1024 * 1024


def _app_storage_dir() -> str:
    root = (
        os.environ.get("FLET_APP_STORAGE_DATA")
        or os.environ.get("HAWAA_DATA_DIR")
        or os.path.join(Path.home(), ".hawaa")
    )
    os.makedirs(root, exist_ok=True)
    return root


def logo_dir() -> str:
    path = os.path.join(_app_storage_dir(), "branding")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_ext(source_path: str) -> str:
    ext = os.path.splitext(source_path or "")[1].lower()
    if ext in SUPPORTED_EXTENSIONS:
        return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def validate_logo_path(source_path: str) -> None:
    if not source_path:
        raise ValueError("لم يتم اختيار ملف شعار")
    if not os.path.exists(source_path):
        raise FileNotFoundError("ملف الشعار غير موجود أو لا يمكن للتطبيق الوصول إليه")
    if os.path.getsize(source_path) > MAX_LOGO_BYTES:
        raise ValueError("حجم الشعار كبير جداً. استخدم صورة أقل من 3MB")
    ext = os.path.splitext(source_path)[1].lower()
    if ext and ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("صيغة الشعار غير مدعومة. استخدم PNG أو JPG أو WEBP")


def import_logo(source_path: str) -> str:
    """Copy a selected logo into app storage and return the stored path."""
    validate_logo_path(source_path)
    ext = _safe_ext(source_path)
    target = os.path.join(logo_dir(), f"company_logo{ext}")
    shutil.copy2(source_path, target)
    return target


def remove_logo(path: str | None = None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    for ext in SUPPORTED_EXTENSIONS:
        candidate = os.path.join(logo_dir(), f"company_logo{ext}")
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except Exception:
                pass


def image_to_base64(path: str) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if not raw:
            return None
        return base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


def image_to_data_uri(path: str) -> Optional[str]:
    b64 = image_to_base64(path)
    if not b64:
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext not in {"png", "jpeg", "webp"}:
        ext = "png"
    return f"data:image/{ext};base64,{b64}"
