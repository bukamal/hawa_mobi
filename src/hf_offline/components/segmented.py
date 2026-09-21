"""A modern segmented control (pill group) for mutually exclusive choices.

Replaces native dropdowns where the choices are few and always visible
(theme light/dark/system, device-status filters, report ranges). The whole
group is a rounded pill; the active segment carries the brand fill.
"""

from __future__ import annotations

from typing import Callable, Sequence

import flet as ft

from hf_offline.core.theme import Colors


class SegmentedToggle:
    """Builds a ``ft.Container`` holding a row of segment buttons.

    Usage:
        seg = SegmentedToggle([("all", "الكل"), ("in_repair", "قيد الإصلاح")],
                              value="all", on_change=fn)
        view.controls.append(seg.control)
        seg.set_value("in_repair")
    """

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        *,
        value: str | None = None,
        on_change: Callable[[str], None] | None = None,
        width: float | None = None,
    ):
        self._on_change = on_change
        self._value = value
        self._buttons: dict[str, ft.Container] = {}
        self._icons: dict[str, ft.Icon] = {}
        self._labels: dict[str, ft.Text] = {}

        def make(item: tuple[str, str]) -> ft.Container:
            key, label = item
            icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, size=0, color=Colors.WHITE)
            icon_txt = ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY, no_wrap=True)
            box = ft.Container(
                icon_txt,
                padding=ft.padding.symmetric(horizontal=13, vertical=8),
                border_radius=11,
                on_click=lambda e, k=key: self.set_value(k),
                ink=True,
                expand=True,
            )
            self._buttons[key] = box
            self._labels[key] = icon_txt
            return box

        self.control = ft.Container(
            ft.Row([make(opt) for opt in options], spacing=0, tight=True),
            bgcolor=Colors.BACKGROUND_ALT,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=14,
            padding=3,
            width=width,
            expand=width is None,
        )
        if value is not None:
            self._paint()

    def set_value(self, value: str) -> None:
        if value not in self._buttons:
            return
        self._value = value
        self._paint()
        if self._on_change is not None:
            self._on_change(value)

    def get_value(self) -> str | None:
        return self._value

    def _paint(self) -> None:
        for key, box in self._buttons.items():
            active = key == self._value
            box.bgcolor = Colors.PRIMARY if active else None
            self._labels[key].color = Colors.WHITE if active else Colors.TEXT_SECONDARY

    def update(self) -> None:
        self.control.update()


__all__ = ["SegmentedToggle"]
