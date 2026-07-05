# -*- coding: utf-8 -*-
"""Flet compatibility helpers for dialogs and transient controls.

The project targets Flet 0.85.x.  In that line the documented imperative dialog
API is ``page.show_dialog(control)`` and ``page.pop_dialog()``.  Older builds and
some examples still use ``page.overlay.append(control); control.open=True``.

Do not mix those APIs casually: opening with raw overlay and closing with a
newer stack API can leave modal barriers or stale controls above the app, which
makes buttons look dead or keeps dialogs visible after Save/Cancel.
"""
from __future__ import annotations

import flet as ft

ARABIC_FONT_FAMILY = "Arial"
_STACK_ATTR = "_hawaa_dialog_stack"


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
    """Open a dialog/transient control using the native Flet 0.85 stack first.

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

    For Flet 0.85 dialogs opened with ``show_dialog`` the correct close operation
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


def attach_service_control(page: ft.Page, control):
    """Attach service controls such as FilePicker/PermissionHandler safely."""
    if page is None or control is None:
        return control
    try:
        ov = _overlay(page)
        if ov is not None and control not in ov:
            ov.append(control)
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass
    return control

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
