# -*- coding: utf-8 -*-
"""Optional camera permission bridge for Flet Android.

Declaring CAMERA in pyproject makes Android include the native permission, but
recent Flet builds still need a runtime request before camera controls can open.
This service uses Flet's PermissionHandler when available and degrades safely
when the extension/runtime is not bundled.
"""
from __future__ import annotations

import flet as ft


def _camera_permission_type():
    for owner in (ft,):
        permission_type = getattr(owner, "PermissionType", None)
        if permission_type is not None:
            value = getattr(permission_type, "CAMERA", None)
            if value is not None:
                return value
    return "camera"


class CameraPermissionService:
    @staticmethod
    def ensure_declared() -> bool:
        """Static hook used by smoke tests; native declaration lives in pyproject."""
        return True

    @staticmethod
    def request(page) -> tuple[bool, str]:
        """Request/check camera permission when PermissionHandler is available.

        Returns (ok, message).  ok=True means either granted or there is no
        runtime permission service available, in which case the caller may still
        try to open the scanner and show a scanner-specific fallback.
        """
        try:
            permission_handler_cls = getattr(ft, "PermissionHandler", None)
            if permission_handler_cls is None:
                try:
                    from flet_permission_handler import PermissionHandler as permission_handler_cls  # type: ignore
                except Exception:
                    permission_handler_cls = None
            if permission_handler_cls is None:
                return True, "لا تتوفر خدمة طلب صلاحية الكاميرا في نسخة Flet هذه. إذا رفض النظام الكاميرا، فعّلها من إعدادات التطبيق أو استخدم لصق نص الربط."

            handler = permission_handler_cls()
            try:
                ov = getattr(page, "overlay", None)
                if ov is not None and handler not in ov:
                    ov.append(handler)
                    page.update()
            except Exception:
                pass
            perm = _camera_permission_type()
            try:
                status = handler.check_permission(perm)
                status_s = str(status).lower()
                if "grant" in status_s or "allow" in status_s:
                    return True, "صلاحية الكاميرا ممنوحة"
            except Exception:
                pass
            try:
                status = handler.request_permission(perm)
                status_s = str(status).lower()
                if "denied" in status_s or "permanent" in status_s:
                    return False, "تم رفض صلاحية الكاميرا. افتح إعدادات Android > التطبيقات > هوى الشام > الأذونات وفعّل الكاميرا، أو استخدم لصق نص الربط."
                return True, "تم طلب صلاحية الكاميرا"
            except Exception as ex:
                return True, f"تعذر طلب صلاحية الكاميرا مباشرة: {ex}. جرّب المسح، وإن فشل استخدم لصق نص الربط."
        except Exception as ex:
            return True, f"تعذر فحص صلاحية الكاميرا: {ex}. استخدم اللصق كخيار احتياطي."
