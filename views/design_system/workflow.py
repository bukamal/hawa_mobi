# -*- coding: utf-8 -*-
"""Adaptive multi-step workflow primitives for long accounting forms.

The project is pinned to Flet 0.28, so this module intentionally uses only
stable controls and mutates existing controls instead of replacing routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import flet as ft

from .components import primary_action, secondary_action
from .tokens import (
    BRAND_PRIMARY,
    BRAND_PRIMARY_LIGHT,
    LIGHT_BORDER,
    LIGHT_SURFACE,
    LIGHT_SURFACE_ALT,
    LIGHT_TEXT_PRIMARY,
    LIGHT_TEXT_SECONDARY,
    RADIUS_CARD,
    RADIUS_DIALOG,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    TEXT_BODY,
    TEXT_CARD_TITLE,
)
from .responsive import form_factor, page_width


@dataclass(frozen=True)
class WorkflowStep:
    title: str
    subtitle: str
    icon: str
    controls: Sequence[ft.Control]


def adaptive_dialog_metrics(page, *, max_width: int = 720, max_height: int = 760):
    """Return width, height, inset and radius for a long-form modal.

    On phones the modal occupies almost the complete safe viewport. Tablet and
    desktop keep a capped centered surface so the form remains readable.
    """
    width = page_width(page)
    try:
        height = float(getattr(page, "height", 0) or 0) or 720.0
    except Exception:
        height = 720.0
    factor = form_factor(page)
    if factor == "phone":
        return max(304, width - 16), max(430, height - 48), 8, 20
    if factor == "tablet":
        return min(max_width, width - 48), min(max_height, height - 72), 24, RADIUS_DIALOG
    return min(max_width, width - 80), min(max_height, height - 96), 36, RADIUS_DIALOG


def section_card(title: str, controls: Iterable[ft.Control], *, icon=None, subtitle: str | None = None):
    heading = [
        ft.Icon(icon or ft.Icons.TUNE, size=19, color=BRAND_PRIMARY),
        ft.Column(
            [
                ft.Text(title, size=TEXT_CARD_TITLE, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY),
                ft.Text(
                    subtitle or "",
                    size=11,
                    color=LIGHT_TEXT_SECONDARY,
                    visible=bool(subtitle),
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=1,
            expand=True,
        ),
    ]
    return ft.Container(
        content=ft.Column(
            [ft.Row(heading, spacing=SPACE_2)] + list(controls),
            spacing=SPACE_3,
        ),
        bgcolor=LIGHT_SURFACE,
        border=ft.Border(
            left=ft.BorderSide(1, LIGHT_BORDER),
            top=ft.BorderSide(1, LIGHT_BORDER),
            right=ft.BorderSide(1, LIGHT_BORDER),
            bottom=ft.BorderSide(1, LIGHT_BORDER),
        ),
        border_radius=RADIUS_CARD,
        padding=SPACE_4,
    )


def review_row(label: str, value, *, icon=None, value_color=LIGHT_TEXT_PRIMARY):
    return ft.Row(
        [
            ft.Icon(icon or ft.Icons.CHEVRON_LEFT, size=17, color=LIGHT_TEXT_SECONDARY),
            ft.Text(label, size=12, color=LIGHT_TEXT_SECONDARY, expand=True),
            ft.Text(
                str(value if value not in (None, "") else "—"),
                size=TEXT_BODY,
                weight=ft.FontWeight.BOLD,
                color=value_color,
                text_align=ft.TextAlign.LEFT,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
        spacing=SPACE_2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def financial_summary(title: str, rows: Sequence[tuple[str, str, str | None]], *, tone_color=BRAND_PRIMARY):
    controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, color=tone_color, size=20),
                ft.Text(title, size=TEXT_CARD_TITLE, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY),
            ],
            spacing=SPACE_2,
        )
    ]
    for label, value, color in rows:
        controls.append(review_row(label, value, value_color=color or LIGHT_TEXT_PRIMARY))
    return ft.Container(
        content=ft.Column(controls, spacing=SPACE_2),
        bgcolor=LIGHT_SURFACE_ALT,
        border=ft.Border(
            left=ft.BorderSide(1, LIGHT_BORDER),
            top=ft.BorderSide(1, LIGHT_BORDER),
            right=ft.BorderSide(1, LIGHT_BORDER),
            bottom=ft.BorderSide(1, LIGHT_BORDER),
        ),
        border_radius=RADIUS_CARD,
        padding=SPACE_4,
    )


class WorkflowController:
    """Controller and control tree for a deterministic step-by-step form."""

    def __init__(
        self,
        page,
        steps: Sequence[WorkflowStep],
        *,
        validate_step: Callable[[int], bool] | None = None,
        before_step: Callable[[int], None] | None = None,
        on_cancel=None,
        on_submit=None,
        submit_label: str = "حفظ",
        width: float | None = None,
        height: float | None = None,
    ):
        if not steps:
            raise ValueError("WorkflowController requires at least one step")
        self.page = page
        self.steps = list(steps)
        self.validate_step = validate_step
        self.before_step = before_step
        self.step_index = 0
        self.width = width
        self.height = height
        self.submit_label = submit_label

        self.step_counter = ft.Text("", size=11, color=LIGHT_TEXT_SECONDARY)
        self.step_title = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY)
        self.step_subtitle = ft.Text("", size=12, color=LIGHT_TEXT_SECONDARY, max_lines=2)
        self.step_icon = ft.Icon(ft.Icons.CIRCLE_OUTLINED, color=BRAND_PRIMARY, size=21)
        self.progress = ft.ProgressBar(value=0, color=BRAND_PRIMARY, bgcolor=BRAND_PRIMARY_LIGHT, height=5)
        self.content_host = ft.Column([], spacing=SPACE_3, scroll=ft.ScrollMode.AUTO, expand=True)

        self.cancel_button = secondary_action("إلغاء", icon=ft.Icons.CLOSE, on_click=on_cancel)
        self.back_button = secondary_action("السابق", icon=ft.Icons.ARROW_FORWARD, on_click=self._go_back)
        self.next_button = primary_action("التالي", icon=ft.Icons.ARROW_BACK, on_click=self._go_next)
        self.submit_button = primary_action(submit_label, icon=ft.Icons.CHECK_CIRCLE_OUTLINE, on_click=on_submit)
        self.actions = ft.Row(
            [self.cancel_button, self.back_button, self.next_button, self.submit_button],
            spacing=SPACE_2,
            run_spacing=SPACE_2,
            wrap=True,
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.control = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=self.step_icon,
                                            bgcolor=BRAND_PRIMARY_LIGHT,
                                            border_radius=12,
                                            padding=9,
                                        ),
                                        ft.Column(
                                            [self.step_counter, self.step_title, self.step_subtitle],
                                            spacing=1,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=SPACE_3,
                                ),
                                self.progress,
                            ],
                            spacing=SPACE_3,
                        ),
                        padding=ft.Padding(SPACE_2, 0, SPACE_2, 0),
                    ),
                    ft.Container(content=self.content_host, expand=True, padding=ft.Padding(SPACE_2, 0, SPACE_2, 0)),
                    ft.Divider(height=1, color=LIGHT_BORDER),
                    self.actions,
                ],
                spacing=SPACE_3,
                expand=True,
            ),
            width=width,
            height=height,
            bgcolor=LIGHT_SURFACE,
            padding=ft.Padding(SPACE_2, SPACE_3, SPACE_2, SPACE_2),
        )
        self.show_step(0, update=False)

    def show_step(self, index: int, *, update: bool = True):
        index = max(0, min(int(index), len(self.steps) - 1))
        self.step_index = index
        if self.before_step:
            self.before_step(index)
        step = self.steps[index]
        self.step_counter.value = f"الخطوة {index + 1} من {len(self.steps)}"
        self.step_title.value = step.title
        self.step_subtitle.value = step.subtitle
        self.step_icon.name = step.icon
        self.progress.value = (index + 1) / len(self.steps)
        self.content_host.controls = list(step.controls)
        self.back_button.visible = index > 0
        self.next_button.visible = index < len(self.steps) - 1
        self.submit_button.visible = index == len(self.steps) - 1
        if update:
            try:
                self.page.update()
            except Exception:
                pass

    def _go_next(self, e=None):
        if self.validate_step and not self.validate_step(self.step_index):
            return
        self.show_step(self.step_index + 1)

    def _go_back(self, e=None):
        self.show_step(self.step_index - 1)

    def set_busy(self, busy: bool, *, busy_label: str = "جارٍ الحفظ..."):
        busy = bool(busy)
        self.cancel_button.disabled = busy
        self.back_button.disabled = busy
        self.next_button.disabled = busy
        self.submit_button.disabled = busy
        if busy:
            self.submit_button.content = ft.Row(
                [ft.ProgressRing(width=18, height=18, stroke_width=2, color=ft.Colors.WHITE), ft.Text(busy_label, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
                spacing=SPACE_2,
                tight=True,
            )
        else:
            self.submit_button.content = ft.Row(
                [ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=19, color=ft.Colors.WHITE), ft.Text(self.submit_label, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
                spacing=SPACE_2,
                tight=True,
            )
        try:
            self.page.update()
        except Exception:
            pass
