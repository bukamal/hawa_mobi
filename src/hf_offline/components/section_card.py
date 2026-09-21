"""Shared section/card containers — the standard "surface" of HF.

Every screen composes itself from these instead of hand-rolling
Containers with drifting paddings/radii/shadows:

* ``section_card`` — the standard content card (white surface, border, soft
  shadow) with an optional built-in title block.
* ``hero_panel`` — a gradient primary panel for the dashboard's smart
  insights and other "attention" blocks.
* ``row_card`` — a compact tappable list row (device lists, report lists).
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from hf_offline.core.theme import Colors, Radius, Shadow
from hf_offline.core.typography import section_title


def section_card(
    *content: ft.Control,
    title: str | None = None,
    subtitle: str | None = None,
    trailing: ft.Control | None = None,
    padding: Any = 14,
    expand: bool = False,
) -> ft.Container:
    """A standard content card. When ``title`` is given, a header row
    (title block + optional trailing control) is rendered above the
    content with a hairline separator."""
    inner: list[ft.Control] = []
    if title:
        header_controls: list[ft.Control] = [ft.Container(section_title(title, subtitle), expand=True)]
        if trailing is not None:
            header_controls.append(trailing)
        inner.append(
            ft.Container(
                ft.Row(header_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=14, right=14, top=14, bottom=0 if content else 14),
                border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)) if content else None,
            )
        )
    inner.extend(content)
    body_padding = 0 if title else padding
    return ft.Container(
        ft.Column(inner, spacing=12, expand=expand),
        bgcolor=Colors.WHITE,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.LG,
        shadow=Shadow.SM,
        padding=ft.padding.all(body_padding) if body_padding else None,
        expand=expand,
    )


def hero_panel(*content: ft.Control, padding: Any = 16) -> ft.Container:
    """A gradient primary→accent panel for smart-insight / hero blocks."""
    return ft.Container(
        ft.Column(list(content), spacing=10),
        gradient=ft.LinearGradient(
            colors=[Colors.PRIMARY, Colors.ACCENT_DARK],
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
        ),
        border_radius=Radius.LG,
        shadow=Shadow.MD,
        padding=padding,
    )


def row_card(
    leading: ft.Control,
    title: str,
    subtitle: str | None = None,
    trailing: ft.Control | None = None,
    *,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
    selected: bool = False,
) -> ft.Container:
    """A compact tappable list row with a leading icon/badge, a title +
    subtitle column, and an optional trailing control."""
    return ft.Container(
        ft.Row(
            [
                leading,
                ft.Column(
                    [
                        ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=Colors.TEXT_PRIMARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        *([ft.Text(subtitle, size=11, color=Colors.TEXT_SECONDARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)] if subtitle else []),
                    ],
                    spacing=1, expand=True,
                ),
                *(trailing.controls if isinstance(trailing, ft.Column) else ([trailing] if trailing is not None else [])),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=11),
        bgcolor=Colors.PRIMARY_BG if selected else Colors.WHITE,
        border=ft.border.all(1, Colors.PRIMARY_BORDER if selected else Colors.BORDER),
        border_radius=Radius.MD,
        shadow=Shadow.SM,
        ink=bool(on_click),
        on_click=on_click,
    )


__all__ = ["section_card", "hero_panel", "row_card"]
