# -*- coding: utf-8 -*-
"""Flet compatibility helpers for dialogs, transient controls and services.

The APK deliberately pins a FilePicker-stable Flet line for Android backup
restore/logo import.  Newer Flet lines may expose FilePicker in Python while the
Flutter client rejects it at runtime with ``Unknown control: FilePicker``.  Keep
all service controls behind helpers in this module instead of appending them
directly from views.
"""
from __future__ import annotations

import flet as ft

ARABIC_FONT_FAMILY = "Arial"
_STACK_ATTR = "_hawaa_dialog_stack"


def _flet_version_tuple():
    """Best-effort Flet version tuple.

    Flet 0.80+ Android builds observed in this project can expose FilePicker in
    Python while the Flutter client rejects it with ``Unknown control: FilePicker``.
    Flet 0.28.x keeps the legacy overlay FilePicker path working on Android.
    """
    try:
        raw = str(getattr(ft, "__version__", "") or "")
    except Exception:
        raw = ""
    parts = []
    for chunk in raw.replace("-", ".").split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _allow_legacy_filepicker_overlay() -> bool:
    """Return True for the FilePicker-stable Flet line pinned by this app.

    The APK must use a real Android picker for backup import/logo selection;
    the fallback path is not sufficient for production.  Flet 0.28.x is the
    pinned line here because it avoids the 0.80+ ``Unknown control: FilePicker``
    regression seen on Android builds.
    """
    return _flet_version_tuple() < (0, 80, 0)


def _overlay(page):
    return getattr(page, "overlay", None)


def _is_dialog_like(control) -> bool:
    """Controls managed by Flet's dialog stack: AlertDialog, DatePicker, etc."""
    try:
        return isinstance(control, ft.DialogControl)
    except Exception:
        # Older/newer Flet may not expose DialogControl as a public symbol.
        try:
            return isinstance(control, (ft.AlertDialog, ft.DatePicker, ft.TimePicker))
        except Exception:
            return False


def _get_stack(page) -> list:
    stack = getattr(page, _STACK_ATTR, None)
    if stack is None:
        stack = []
        try:
            setattr(page, _STACK_ATTR, stack)
        except Exception:
            pass
    return stack


def _remove_from_stack(page, control) -> None:
    try:
        stack = _get_stack(page)
        while control in stack:
            stack.remove(control)
    except Exception:
        pass


def _remove_from_overlay(page, control) -> None:
    try:
        ov = _overlay(page)
        if ov is None:
            return
        for item in list(ov):
            if item is control:
                try:
                    ov.remove(item)
                except Exception:
                    pass
    except Exception:
        pass


def open_control(page: ft.Page, control):
    """Open a dialog/transient control using the native Flet dialog stack first.

    Fallback is the classic overlay/open path.  The local stack lets close_control
    know whether ``page.pop_dialog()`` is safe to call for the exact top dialog.
    """
    if page is None or control is None:
        return None

    if _is_dialog_like(control) and hasattr(page, "show_dialog"):
        try:
            if not getattr(control, "open", False):
                page.show_dialog(control)
            stack = _get_stack(page)
            if control in stack:
                stack.remove(control)
            stack.append(control)
            try:
                page.update()
            except Exception:
                pass
            return None
        except Exception:
            pass

    try:
        ov = _overlay(page)
        if ov is not None and control not in ov:
            ov.append(control)
    except Exception:
        pass
    try:
        control.open = True
    except Exception:
        pass
    try:
        if isinstance(control, ft.AlertDialog):
            page.dialog = control
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass
    return None


def close_control(page: ft.Page, control):
    """Close one exact control reliably.

    For dialogs opened with ``show_dialog`` the correct close operation
    is ``page.pop_dialog()``.  We call it only when the requested control is the
    top item in our stack; otherwise we do a specific fallback close to avoid
    accidentally popping the visible parent dialog while trying to close an
    already-closed DatePicker.
    """
    if page is None or control is None:
        return None

    was_open = bool(getattr(control, "open", False))
    stack = _get_stack(page)
    is_top = bool(stack and stack[-1] is control)

    if _is_dialog_like(control) and was_open and is_top and hasattr(page, "pop_dialog"):
        try:
            page.pop_dialog()
            _remove_from_stack(page, control)
            try:
                control.open = False
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
            return None
        except Exception:
            pass

    # Specific fallback: never pop an unrelated/top parent dialog here.
    try:
        if hasattr(page, "close") and callable(getattr(page, "close")) and was_open:
            page.close(control)
    except Exception:
        pass
    try:
        control.open = False
    except Exception:
        pass
    _remove_from_stack(page, control)
    _remove_from_overlay(page, control)
    try:
        if getattr(page, "dialog", None) is control:
            page.dialog = None
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass
    return None


def close_all_dialogs(page: ft.Page):
    """Emergency cleanup of all dialog-like controls."""
    if page is None:
        return None
    try:
        stack = _get_stack(page)
        while stack and hasattr(page, "pop_dialog"):
            ctrl = stack.pop()
            try:
                if getattr(ctrl, "open", False):
                    page.pop_dialog()
            except Exception:
                break
    except Exception:
        pass
    try:
        ov = _overlay(page) or []
        for item in list(ov):
            if _is_dialog_like(item):
                try:
                    item.open = False
                except Exception:
                    pass
                try:
                    ov.remove(item)
                except Exception:
                    pass
        page.dialog = None
        page.update()
    except Exception:
        pass
    return None



def make_file_picker(on_result=None):
    """Create FilePicker across Flet versions.

    Some mobile/runtime builds reject ``FilePicker(on_result=...)`` with
    ``unexpected keyword argument 'on_result'``.  The compatible path is to
    instantiate first and then assign ``picker.on_result`` when available.
    """
    picker = None
    if on_result is not None:
        try:
            picker = ft.FilePicker(on_result=on_result)
        except TypeError:
            picker = None
        except Exception:
            picker = None
    if picker is None:
        picker = ft.FilePicker()
        if on_result is not None:
            try:
                picker.on_result = on_result
            except Exception:
                pass
    return picker


def _platform_name(page) -> str:
    """Return a lowercase platform name when Flet exposes one."""
    try:
        value = getattr(page, "platform", "") or ""
        name = getattr(value, "value", value)
        return str(name or "").lower()
    except Exception:
        return ""


def _is_mobile_page(page) -> bool:
    name = _platform_name(page)
    return "android" in name or "ios" in name


def attach_service_control(page: ft.Page, control):
    """Attach service controls such as FilePicker/PermissionHandler safely.

    Flet changed FilePicker/PermissionHandler from overlay-style controls to
    service controls in recent runtimes.  Some Android/Web builds show a fatal
    red overlay: ``Unknown control: FilePicker`` when the service is appended to
    ``page.overlay``.  Therefore we prefer ``page.services`` when available and
    never force service controls into overlay on mobile.
    """
    if page is None or control is None:
        return control

    attached = False

    # Newer Flet service API.
    for attr in ("services", "_services"):
        try:
            services = getattr(page, attr, None)
            if services is not None and control not in services:
                services.append(control)
                attached = True
                break
        except Exception:
            pass

    # Android builds on Flet 0.80+ may expose FilePicker in Python while the
    # Flutter client rejects it as an overlay control (red screen:
    # ``Unknown control: FilePicker``).  However Flet 0.28.x is the stable
    # line for this app and requires the legacy overlay path.
    if not attached and _is_mobile_page(page) and not _allow_legacy_filepicker_overlay():
        try:
            setattr(control, "_hawaa_service_attached", False)
        except Exception:
            pass
        return control

    # Legacy desktop/web/mobile fallback.  This is required for the pinned
    # Flet 0.28.x APK so Android opens the native file picker instead of using
    # the internal fallback-only import path.
    if not attached:
        try:
            ov = _overlay(page)
            if ov is not None and control not in ov:
                ov.append(control)
                attached = True
        except Exception:
            pass

    try:
        setattr(control, "_hawaa_service_attached", bool(attached))
    except Exception:
        pass
    if attached:
        try:
            page.update()
        except Exception:
            pass
    return control


def service_control_attached(control) -> bool:
    try:
        return bool(getattr(control, "_hawaa_service_attached", False))
    except Exception:
        return False


def filepicker_unavailable_message() -> str:
    return (
        "منتقي الملفات غير مدعوم في نسخة Flet/Android الحالية أو لم يكتمل تسجيله في الواجهة. "
        "استخدم نسخة APK مبنية بـ Flet يدعم FilePicker، أو استخدم مسار النسخة الاحتياطي داخل تخزين التطبيق كحل مؤقت."
    )

def show_snackbar(page: ft.Page, message: str, is_error: bool = False, duration: int = 3000):
    snack = ft.SnackBar(
        content=ft.Text(message, size=13),
        bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN,
        duration=duration,
    )
    open_control(page, snack)
    return snack


def apply_arabic_ui_defaults(page: ft.Page):
    """Use a common Arabic-capable system font to avoid square/garbled glyphs."""
    try:
        page.theme = ft.Theme(font_family=ARABIC_FONT_FAMILY)
        page.dark_theme = ft.Theme(font_family=ARABIC_FONT_FAMILY)
    except Exception:
        pass
    try:
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("ar"), ft.Locale("en")],
            current_locale=ft.Locale("ar"),
        )
    except Exception:
        pass
