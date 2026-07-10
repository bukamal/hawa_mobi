# -*- coding: utf-8 -*-
"""Reusable helpers for modal dialogs.

Keep this module presentation-only.  It must not import database/network code.
The helpers are intentionally small so APK builds do not pull extra runtime
requirements into the client package.
"""
from __future__ import annotations

import flet as ft

PRIMARY = ft.Colors.INDIGO
ERROR = ft.Colors.RED
SUCCESS = ft.Colors.GREEN
MUTED = ft.Colors.GREY_600


def dialog_title(text: str, icon=None):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, color=PRIMARY, size=22))
    controls.append(ft.Text(str(text), size=18, weight=ft.FontWeight.BOLD))
    return ft.Row(controls, spacing=8, tight=True)


def dialog_body(controls, width=None, height=None, spacing=14):
    return ft.Column(
        controls=list(controls),
        spacing=spacing,
        width=width,
        height=height,
        scroll=ft.ScrollMode.AUTO,
    )


def cancel_button(label: str, on_click):
    return ft.TextButton(str(label), on_click=on_click)


def save_button(label: str, on_click, ref=None):
    button = ft.FilledButton(
        str(label),
        on_click=on_click,
        bgcolor=PRIMARY,
        color=ft.Colors.WHITE,
    )
    if ref is not None:
        try:
            ref.current = button
        except Exception:
            pass
    return button


def set_button_busy(button, busy: bool, label: str | None = None, busy_label: str = "جارٍ الحفظ..."):
    if button is None:
        return
    try:
        button.disabled = bool(busy)
    except Exception:
        pass
    try:
        button.text = busy_label if busy else (label or button.text)
    except Exception:
        pass


def show_snackbar(page, message, is_error=False, duration=3000):
    from views.flet_compat import show_snackbar as compat_show_snackbar
    return compat_show_snackbar(page, message, is_error=is_error, duration=duration)

def normalize_text(value) -> str:
    return str(value or "").strip()


def parse_non_negative_amount(value):
    try:
        amount = float(str(value or "").replace(",", "."))
    except Exception as exc:
        raise ValueError("المبلغ غير صالح") from exc
    if amount < 0:
        raise ValueError("المبلغ لا يجوز أن يكون سالباً")
    return amount
