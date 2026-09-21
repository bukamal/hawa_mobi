# -*- coding: utf-8 -*-
"""Floating toast notification (ported from the Nano design language).

Flet's built-in SnackBar sits at the true bottom edge of the viewport and
covers the app's own bottom navigation bar on phones.  This helper instead
floats a pill in ``page.overlay`` above whichever bottom chrome is visible,
slides it in/out, and reuses a single overlay slot so quick successive calls
replace the previous toast instead of stacking duplicates.

Usage:
    from views.design_system.toast import toast
    toast(page, "تم الحفظ")
    toast(page, "تعذّر الحفظ", kind="error")
"""
from __future__ import annotations

import asyncio

import flet as ft

from .tokens import (
    LIGHT_SURFACE, LIGHT_BORDER, LIGHT_TEXT_PRIMARY,
    DARK_SURFACE, DARK_BORDER, DARK_TEXT_PRIMARY,
    STATE_SUCCESS, STATE_SUCCESS_SOFT,
    STATE_DANGER, STATE_DANGER_SOFT,
    STATE_WARNING, STATE_WARNING_SOFT,
    STATE_INFO, STATE_INFO_SOFT,
    SHADOW_LIGHT, SHADOW_DARK,
)

ToastKind = str  # "success" | "error" | "warning" | "info"

_LIGHT_STYLE = {
    "success": (ft.Icons.CHECK_CIRCLE_ROUNDED, STATE_SUCCESS, STATE_SUCCESS_SOFT),
    "error": (ft.Icons.ERROR_ROUNDED, STATE_DANGER, STATE_DANGER_SOFT),
    "warning": (ft.Icons.WARNING_ROUNDED, STATE_WARNING, STATE_WARNING_SOFT),
    "info": (ft.Icons.INFO_ROUNDED, STATE_INFO, STATE_INFO_SOFT),
}
_DARK_STYLE = {
    "success": (ft.Icons.CHECK_CIRCLE_ROUNDED, STATE_SUCCESS, "#0F2E1A"),
    "error": (ft.Icons.ERROR_ROUNDED, STATE_DANGER, "#3A1214"),
    "warning": (ft.Icons.WARNING_ROUNDED, STATE_WARNING, "#3A2A0A"),
    "info": (ft.Icons.INFO_ROUNDED, STATE_INFO, "#12312E"),
}

_HIDDEN_BOTTOM = -120.0
_MOBILE_BAR_HEIGHT = 76
_EDGE_MARGIN = 18
_ANIM = ft.Animation(260, ft.AnimationCurve.EASE_OUT)

_SUCCESS_MARKERS = ("تم ", "تمت ", "✔", "بنجاح")
_ERROR_MARKERS = ("خطأ", "تعذر", "فشل", "غير مهيأ", "غير موجود", "غير مطابق", "لا توجد", "لا يمكن")
_WARNING_MARKERS = ("يجب", "اختر", "لا تملك", "أولاً", "أولًا", "الرجاء", "فارغ")


def _infer_kind(text: str) -> str:
    t = str(text or "").strip()
    if t.startswith(_SUCCESS_MARKERS) or any(m in t for m in _SUCCESS_MARKERS):
        return "success"
    if any(m in t for m in _ERROR_MARKERS):
        return "error"
    if any(m in t for m in _WARNING_MARKERS):
        return "warning"
    return "info"


def _is_dark(page: ft.Page) -> bool:
    try:
        return getattr(page, "_hawaa_design_mode", "light") == "dark"
    except Exception:
        return False


def _visible_bottom(page: ft.Page) -> float:
    try:
        is_desktop = bool(page.width and page.width >= 900)
    except Exception:
        is_desktop = False
    return _EDGE_MARGIN if is_desktop else _MOBILE_BAR_HEIGHT + _EDGE_MARGIN


def toast(page: ft.Page, text: str, kind: str | None = None, duration: int = 2600) -> None:
    """Show a floating toast that never covers the app's own navigation."""
    if page is None:
        return
    resolved = kind or _infer_kind(text)
    style_table = _DARK_STYLE if _is_dark(page) else _LIGHT_STYLE
    icon_name, accent, tint = style_table.get(resolved, style_table["info"])
    surface = DARK_SURFACE if _is_dark(page) else LIGHT_SURFACE
    border_color = DARK_BORDER if _is_dark(page) else LIGHT_BORDER
    text_color = DARK_TEXT_PRIMARY if _is_dark(page) else LIGHT_TEXT_PRIMARY
    shadow_color = SHADOW_DARK if _is_dark(page) else SHADOW_LIGHT

    pill = ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    ft.Icon(icon_name, color=accent, size=18),
                    width=30,
                    height=30,
                    border_radius=15,
                    bgcolor=tint,
                    alignment=ft.alignment.center,
                ),
                ft.Text(str(text), size=12.5, weight=ft.FontWeight.W_600, color=text_color, max_lines=3),
            ],
            spacing=10,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=surface,
        border=ft.border.all(1, border_color),
        border_radius=999,
        padding=ft.padding.only(left=14, right=16, top=8, bottom=8),
        shadow=ft.BoxShadow(blur_radius=26, spread_radius=0, color=shadow_color, offset=ft.Offset(0, 9)),
    )

    wrapper = ft.Container(
        content=ft.Row([pill], alignment=ft.MainAxisAlignment.CENTER),
        left=0,
        right=0,
        bottom=_HIDDEN_BOTTOM,
        opacity=0,
        animate_position=_ANIM,
        animate_opacity=_ANIM,
    )

    previous = getattr(page, "_hawaa_toast", None)
    if previous is not None:
        try:
            if previous in page.overlay:
                page.overlay.remove(previous)
        except Exception:
            pass
    try:
        page._hawaa_toast = wrapper
    except Exception:
        pass
    page.overlay.append(wrapper)
    page.update()

    wrapper.bottom = _visible_bottom(page)
    wrapper.opacity = 1
    page.update()

    async def _auto_dismiss() -> None:
        await asyncio.sleep(duration / 1000)
        try:
            if getattr(page, "_hawaa_toast", None) is not wrapper:
                return
            wrapper.bottom = _HIDDEN_BOTTOM
            wrapper.opacity = 0
            page.update()
            await asyncio.sleep(_ANIM.duration / 1000)
            if wrapper in page.overlay:
                page.overlay.remove(wrapper)
                page.update()
            if getattr(page, "_hawaa_toast", None) is wrapper:
                page._hawaa_toast = None
        except Exception:
            pass

    try:
        from views.flet_compat import run_async_task

        run_async_task(page, _auto_dismiss)
    except Exception:
        try:
            page.run_task(_auto_dismiss())
        except Exception:
            pass


__all__ = ["toast"]
