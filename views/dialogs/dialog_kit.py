# -*- coding: utf-8 -*-
"""Unified presentation helpers for modal dialogs.

Dialogs across the project share the same title hierarchy, spacing, actions and
semantic colors. Business/database/network logic must not be imported here.
"""
from __future__ import annotations

import flet as ft
from views.ui_kit import PRIMARY, PRIMARY_SOFT, DANGER, SUCCESS, MUTED, TEXT, BORDER

ERROR = DANGER


def dialog_title(text: str, icon=None):
    controls = []
    if icon:
        controls.append(
            ft.Container(
                content=ft.Icon(icon, color=PRIMARY, size=21),
                bgcolor=PRIMARY_SOFT,
                border_radius=12,
                padding=8,
            )
        )
    controls.append(ft.Text(str(text), size=18, weight=ft.FontWeight.BOLD, color=TEXT, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS))
    return ft.Row(controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def dialog_body(controls, width=None, height=None, spacing=14):
    return ft.Column(
        controls=list(controls),
        spacing=spacing,
        width=width,
        height=height,
        scroll=ft.ScrollMode.AUTO,
    )


def cancel_button(label: str, on_click):
    return ft.TextButton(
        content=ft.Text(str(label), size=14, color=MUTED, weight=ft.FontWeight.BOLD),
        on_click=on_click,
        height=46,
    )


def save_button(label: str, on_click, ref=None):
    button = ft.FilledButton(
        content=ft.Text(str(label), size=14, weight=ft.FontWeight.BOLD),
        on_click=on_click,
        bgcolor=PRIMARY,
        color=ft.Colors.WHITE,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )
    if ref is not None:
        try:
            ref.current = button
        except Exception:
            pass
    return button


def danger_button(label: str, on_click):
    return ft.FilledButton(
        content=ft.Text(str(label), size=14, weight=ft.FontWeight.BOLD),
        on_click=on_click,
        bgcolor=DANGER,
        color=ft.Colors.WHITE,
        height=46,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )


def form_section(title, controls, icon=None):
    header = dialog_title(title, icon=icon)
    side = ft.BorderSide(1, BORDER)
    return ft.Container(
        content=ft.Column([header, ft.Divider(height=1, color=BORDER), *list(controls)], spacing=12),
        padding=14,
        border_radius=14,
        border=ft.Border(left=side, top=side, right=side, bottom=side),
    )


def set_button_busy(button, busy: bool, label: str | None = None, busy_label: str = "جارٍ الحفظ..."):
    if button is None:
        return
    try:
        button.disabled = bool(busy)
    except Exception:
        pass
    try:
        if hasattr(button, "content") and hasattr(button.content, "value"):
            button.content.value = busy_label if busy else (label or button.content.value)
        elif hasattr(button, "text"):
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
        raw = "0" if value is None or str(value).strip() == "" else str(value).strip()
        amount = float(raw.replace("٬", "").replace("٫", ".").replace(",", "."))
    except Exception as exc:
        raise ValueError("المبلغ غير صالح") from exc
    if amount < 0:
        raise ValueError("المبلغ لا يجوز أن يكون سالباً")
    return amount
