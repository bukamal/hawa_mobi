# -*- coding: utf-8 -*-
"""Best-effort Android storage permission bridge for backup import.

Flet's FilePicker should normally read the selected file through Android's
Storage Access Framework without broad storage permission.  In practice, some
APK/runtime/device combinations return only a public filesystem path or display
name.  For those fallbacks, requesting storage permission improves access to
Download/Hawaa and Download on Android versions that still honor these grants.
"""
from __future__ import annotations

import flet as ft


def _permission_handler_cls():
    try:
        cls = getattr(ft, "PermissionHandler", None)
        if cls is not None:
            return cls
    except Exception:
        pass
    try:
        from flet_permission_handler import PermissionHandler  # type: ignore
        return PermissionHandler
    except Exception:
        return None


def _permission_type_candidates():
    names = (
        "MANAGE_EXTERNAL_STORAGE",
        "STORAGE",
        "READ_EXTERNAL_STORAGE",
        "WRITE_EXTERNAL_STORAGE",
        "PHOTOS",
        "MEDIA_LIBRARY",
    )
    values = []
    try:
        permission_type = getattr(ft, "PermissionType", None)
    except Exception:
        permission_type = None
    for name in names:
        value = None
        try:
            if permission_type is not None:
                value = getattr(permission_type, name, None)
        except Exception:
            value = None
        values.append(value if value is not None else name.lower())
    return values


class StoragePermissionService:
    @staticmethod
    def request(page) -> tuple[bool, str]:
        """Request/check storage permissions when available.

        Returns (ok, message).  ok=True does not guarantee Android will expose
        every public folder because scoped storage still applies on recent
        Android versions.  It only means the app made the best runtime request
        available in the current Flet APK.
        """
        cls = _permission_handler_cls()
        if cls is None:
            return True, "لا تتوفر خدمة طلب صلاحية التخزين في نسخة Flet هذه؛ سيتم الاعتماد على منتقي الملفات أو فحص Download/Hawaa إن كان متاحًا."
        try:
            handler = cls()
            try:
                from views.flet_compat import attach_service_control
                attach_service_control(page, handler)
            except Exception:
                pass
            messages = []
            granted_any = False
            for perm in _permission_type_candidates():
                try:
                    status = handler.check_permission(perm)
                    status_s = str(status).lower()
                    if "grant" in status_s or "allow" in status_s:
                        granted_any = True
                        messages.append(f"{perm}: granted")
                        continue
                except Exception:
                    pass
                try:
                    status = handler.request_permission(perm)
                    status_s = str(status).lower()
                    messages.append(f"{perm}: {status_s}")
                    if "grant" in status_s or "allow" in status_s or "limited" in status_s:
                        granted_any = True
                except Exception as ex:
                    messages.append(f"{perm}: {ex}")
            if granted_any:
                return True, "تم طلب/فحص صلاحيات التخزين."
            return True, "تم طلب صلاحية التخزين، لكن Android قد يطلب تفعيلها يدويًا من إعدادات التطبيق. التفاصيل: " + " | ".join(messages[:4])
        except Exception as ex:
            return True, f"تعذر طلب صلاحية التخزين مباشرة: {ex}. سيتم الاعتماد على منتقي الملفات وفحص Download/Hawaa."
