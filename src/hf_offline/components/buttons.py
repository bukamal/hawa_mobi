"""Shared button widgets for roles that recur across many views.

Each *role* has one look, defined once: primary CTA, destructive action,
row-level inline icons, dialog/sheet header close, and the hero gradient
button used by the central action. Colors are read from ``core.theme`` at
call time (never cached at import time) so these stay dark-mode-aware the
same way the rest of the app is.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from hf_offline.core.theme import Colors, IconSize, Radius


def primary_button(text: str, *, icon: str | None = None, on_click: Callable | None = None, **kwargs) -> ft.FilledButton:
    """The primary action button (indigo fill)."""
    return ft.FilledButton(
        text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(bgcolor=Colors.PRIMARY, color=Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=Radius.MD)),
        **kwargs,
    )


def danger_button(text: str, *, icon: str | None = None, on_click: Callable | None = None, **kwargs) -> ft.FilledButton:
    """A destructive-action filled button (delete/discard), recolored to the
    danger token so "حذف" looks the same everywhere it appears."""
    return ft.FilledButton(
        text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(bgcolor=Colors.DANGER, color=Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=Radius.MD)),
        **kwargs,
    )


def outlined_button(text: str, *, icon: str | None = None, on_click: Callable | None = None, **kwargs) -> ft.OutlinedButton:
    """A secondary action with visible weight but no fill."""
    return ft.OutlinedButton(
        text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(color=Colors.PRIMARY, side=ft.BorderSide(1, Colors.PRIMARY_BORDER), shape=ft.RoundedRectangleBorder(radius=Radius.MD)),
        **kwargs,
    )


def hero_button(text: str, *, icon: str | None = None, on_click: Callable | None = None, **kwargs) -> ft.FilledButton:
    """The single prominent, full-height gradient CTA at the bottom of a
    flow (start diagnosis / finish test)."""
    kwargs.setdefault("height", 52)
    return ft.FilledButton(
        text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor=Colors.PRIMARY,
            color=Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=Radius.MD),
        ),
        **kwargs,
    )


def inline_icon_button(icon: str, on_click: Callable, *, tooltip: str | None = None, color: str | None = None) -> ft.IconButton:
    """A small row-level action icon (edit, diagnose, print...)."""
    return ft.IconButton(icon, icon_size=IconSize.INLINE, icon_color=color or Colors.TEXT_SECONDARY, tooltip=tooltip, on_click=on_click)


def header_close_button(on_click: Callable, *, tooltip: str | None = None) -> ft.IconButton:
    """The small "X" icon button in a dialog/sheet/panel header."""
    return ft.IconButton(ft.Icons.CLOSE, icon_size=IconSize.HEADER, icon_color=Colors.TEXT_SECONDARY, tooltip=tooltip, on_click=on_click)


__all__ = [
    "primary_button", "danger_button", "outlined_button", "hero_button",
    "inline_icon_button", "header_close_button",
]
