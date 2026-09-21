"""Shared status pill (colored chip) — one shape for every "state of this
row" indicator in the app (device status, test result, report state)."""

from __future__ import annotations

import flet as ft

from hf_offline.core.theme import Colors


def status_pill(text: str, fg: str, bg: str, *, size: int = 10) -> ft.Container:
    return ft.Container(
        ft.Text(text, size=size, color=fg, weight=ft.FontWeight.BOLD),
        padding=ft.padding.symmetric(horizontal=9, vertical=4),
        bgcolor=bg,
        border_radius=12,
    )


# Device lifecycle pill styles, resolved lazily so they stay mode-aware.
def device_status_pill(status: str) -> ft.Container:
    table = {
        "in_queue": ("قيد الانتظار", Colors.INFO_DARK, Colors.INFO_BG),
        "in_repair": ("قيد الإصلاح", Colors.WARNING_DARKER, Colors.WARNING_BG),
        "diagnosing": ("قيد الفحص", Colors.PRIMARY, Colors.PRIMARY_BG),
        "done": ("مكتمل", Colors.SUCCESS_DARKER, Colors.SUCCESS_BG),
    }
    label, fg, bg = table.get(status, table["in_queue"])
    return status_pill(label, fg, bg)


def test_result_pill(status: str) -> ft.Container:
    table = {
        "passed": ("ناجح", Colors.SUCCESS_DARKER, Colors.SUCCESS_BG),
        "failed": ("فاشل", Colors.DANGER_DARKER, Colors.DANGER_BG),
        "warning": ("تحذير", Colors.WARNING_DARKER, Colors.WARNING_BG),
        "na": ("غير مُفعّل", Colors.TEXT_SECONDARY, Colors.BACKGROUND_ALT),
    }
    label, fg, bg = table.get(status, table["na"])
    return status_pill(label, fg, bg)


__all__ = ["status_pill", "device_status_pill", "test_result_pill"]
