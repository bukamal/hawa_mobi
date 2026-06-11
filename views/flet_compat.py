# -*- coding: utf-8 -*-
"""Compatibility helpers for different Flet versions.

Some Flet releases expose page.open(control), while others require placing
dialogs/date-pickers in page.overlay and setting control.open = True.
These helpers keep the app working in both web and APK builds.
"""
import flet as ft

ARABIC_FONT_FAMILY = "Arial"

def open_control(page: ft.Page, control):
    if hasattr(page, "open") and callable(getattr(page, "open")):
        return page.open(control)
    if control not in page.overlay:
        page.overlay.append(control)
    try:
        if isinstance(control, ft.AlertDialog):
            page.dialog = control
    except Exception:
        pass
    control.open = True
    page.update()
    return None

def close_control(page: ft.Page, control):
    """Close dialogs/date-pickers/snackbars in a way that works across Flet versions.

    Older Flet versions keep AlertDialog either in page.dialog or page.overlay.
    Setting open=False alone is sometimes not enough in web/APK builds, so we
    also clear page.dialog and remove the control from overlay when possible.
    """
    if control is None:
        return
    try:
        if hasattr(page, "close") and callable(getattr(page, "close")):
            page.close(control)
            return
    except Exception:
        pass
    try:
        control.open = False
    except Exception:
        pass
    try:
        if getattr(page, "dialog", None) is control:
            page.dialog = None
    except Exception:
        pass
    try:
        if hasattr(page, "overlay") and control in page.overlay:
            page.overlay.remove(control)
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass

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
