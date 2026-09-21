"""Actionable empty-state card.

Design principle: an empty screen should be an invitation to act, not just
a neutral status message. Icon, a short direct headline, an optional hint
line, and an optional primary action button that does the obvious next
thing.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from hf_offline.core.theme import Colors
from hf_offline.core.typography import Type, type_text


def empty_state(
    title: str,
    *,
    icon=ft.Icons.INBOX_OUTLINED,
    hint: str | None = None,
    action_label: str | None = None,
    on_action: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    """Build a centered empty-state card.

    Args:
        title: Direct headline naming what's missing and what to do.
        icon: Icon shown above the title.
        hint: Optional secondary line (e.g. a tip for narrowing a search).
        action_label: If set (with ``on_action``), renders a primary button.
        on_action: Click handler for the action button.
    """
    controls: list[ft.Control] = [
        ft.Container(
            ft.Icon(icon, size=30, color=Colors.TEXT_FAINT),
            width=66, height=66, alignment=ft.alignment.center,
            bgcolor=Colors.BACKGROUND_ALT, border_radius=22,
        ),
        type_text(title, Type.BODY, color=Colors.TEXT_MUTED_DARK, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
    ]
    if hint:
        controls.append(type_text(hint, Type.CAPTION, text_align=ft.TextAlign.CENTER))
    if action_label and on_action:
        controls.append(
            ft.FilledButton(action_label, icon=ft.Icons.ADD, on_click=on_action)
        )

    return ft.Container(
        ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        alignment=ft.alignment.center,
        padding=ft.padding.symmetric(vertical=38, horizontal=20),
    )


__all__ = ["empty_state"]
