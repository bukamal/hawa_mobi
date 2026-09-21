"""A modern, app-aware toast notification — floating pill in page.overlay.

Placed *above* whichever bottom chrome is currently visible (the mobile
bottom bar on phones, just off the page edge on desktop where the bar is
hidden). A single reusable overlay slot lives on the page object itself,
so calling this twice in quick succession slides the old toast out instead
of stacking duplicates.

Usage:
    from hf_offline.core.toast import toast
    toast(page, "تم الحفظ")
    toast(page, "تعذّر الاتصال", kind="error")
"""

from __future__ import annotations

import asyncio
from typing import Literal

import flet as ft

from hf_offline.core.theme import Colors, Shadow

ToastKind = Literal["success", "error", "warning", "info"]

_STYLE: dict[ToastKind, tuple[str, str, str]] = {
    "success": (ft.Icons.CHECK_CIRCLE_ROUNDED, Colors.SUCCESS, Colors.SUCCESS_BG),
    "error": (ft.Icons.ERROR_ROUNDED, Colors.DANGER, Colors.DANGER_BG),
    "warning": (ft.Icons.WARNING_ROUNDED, Colors.WARNING, Colors.WARNING_BG),
    "info": (ft.Icons.INFO_ROUNDED, Colors.PRIMARY, Colors.PRIMARY_BG),
}

_HIDDEN_BOTTOM = -120.0
_MOBILE_BAR_HEIGHT = 82
_EDGE_MARGIN = 18
_ANIM = ft.Animation(260, ft.AnimationCurve.EASE_OUT)

_SUCCESS_MARKERS = ("تم ", "تمت ", "✔", "بنجاح")
_ERROR_MARKERS = ("خطأ", "تعذر", "فشل", "غير مهيأ", "غير موجود", "غير مطابق", "لا توجد", "لا يمكن")
_WARNING_MARKERS = ("يجب", "اختر", "أولاً", "أولًا", "الرجاء", "فارغ")


def _infer_kind(text: str) -> ToastKind:
    t = text.strip()
    if t.startswith(_SUCCESS_MARKERS) or any(m in t for m in _SUCCESS_MARKERS):
        return "success"
    if any(m in t for m in _ERROR_MARKERS):
        return "error"
    if any(m in t for m in _WARNING_MARKERS):
        return "warning"
    return "info"


def _visible_bottom(page: ft.Page) -> float:
    """Sit above the mobile bottom bar on phones; hug the page edge on desktop."""
    is_desktop = bool(page.width and page.width >= 900)
    return _EDGE_MARGIN if is_desktop else _MOBILE_BAR_HEIGHT + _EDGE_MARGIN


def toast(page: ft.Page, text: str, kind: ToastKind | None = None, duration: int = 2600) -> None:
    """Show a floating toast that never covers the app's own navigation."""
    resolved_kind: ToastKind = kind or _infer_kind(text)
    icon_name, accent, tint = _STYLE[resolved_kind]

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
                ft.Text(text, size=12.5, weight=ft.FontWeight.W_600, color=Colors.TEXT_PRIMARY, max_lines=3),
            ],
            spacing=10,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=Colors.WHITE,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=999,
        padding=ft.padding.only(left=14, right=16, top=8, bottom=8),
        shadow=Shadow.LG,
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

    previous = getattr(page, "_hf_toast", None)
    if previous is not None and previous in page.overlay:
        page.overlay.remove(previous)
    page._hf_toast = wrapper
    page.overlay.append(wrapper)
    page.update()

    wrapper.bottom = _visible_bottom(page)
    wrapper.opacity = 1
    page.update()

    async def _auto_dismiss() -> None:
        await asyncio.sleep(duration / 1000)
        if getattr(page, "_hf_toast", None) is not wrapper:
            return
        wrapper.bottom = _HIDDEN_BOTTOM
        wrapper.opacity = 0
        page.update()
        await asyncio.sleep(_ANIM.duration / 1000)
        if wrapper in page.overlay:
            page.overlay.remove(wrapper)
            page.update()
        if getattr(page, "_hf_toast", None) is wrapper:
            page._hf_toast = None

    page.run_task(_auto_dismiss)


__all__ = ["toast", "ToastKind"]
