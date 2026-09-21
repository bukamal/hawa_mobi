"""Shared KPI/summary card.

One "icon badge + caption + value" shape for every summary row in the app
(dashboard KPIs, device-screen filter chips' totals, report summaries).
If an ``on_tap`` is given the whole card becomes a tappable filter shortcut
with a trailing chevron hinting at it.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from hf_offline.core.theme import Colors, Shadow
from hf_offline.core.typography import Type, type_text


def kpi_card(
    label: str,
    value: str,
    icon,
    accent: str,
    *,
    on_tap: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    """Build one KPI card for a summary row.

    Args:
        label: Small caption above the value (e.g. "أجهزة قيد الإصلاح").
        value: The headline number/text.
        icon: Icon shown in the leading badge.
        accent: Icon color — also implies the metric's meaning.
        on_tap: If given, the card becomes a tappable filter shortcut.
    """
    return ft.Container(
        ft.Row(
            [
                ft.Container(
                    ft.Icon(icon, color=accent, size=20),
                    width=42, height=42, alignment=ft.alignment.center,
                    bgcolor=Colors.BACKGROUND, border_radius=14,
                ),
                ft.Column(
                    [
                        type_text(label, Type.CAPTION),
                        type_text(value, Type.DISPLAY, size=20),
                    ],
                    spacing=2, expand=True,
                ),
                *([ft.Icon(ft.Icons.CHEVRON_LEFT_ROUNDED, size=16, color=Colors.TEXT_FAINT)] if on_tap else []),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=13,
        bgcolor=Colors.WHITE,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=18,
        shadow=Shadow.SM,
        ink=bool(on_tap),
        on_click=on_tap,
    )


__all__ = ["kpi_card"]
