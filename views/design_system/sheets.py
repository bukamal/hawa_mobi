# -*- coding: utf-8 -*-
"""Bottom-sheet UI system (Nano style) for dialogs in the hawaa app.

Nano's app (src/hf_offline) uses a single ``form_sheet`` bottom-sheet
component for every form/selector instead of centered modal dialogs.  This
module ports that pattern onto the hawaa dialog classes so screens open
sheets instead of AlertDialogs, while keeping the Android-safe overlay
host from views/flet_compat.py.

The bridge: a sheet control is *shown* by mounting its content inside a
barrier + bottom-anchored host Stack appended to page.overlay — exactly how
flet_compat renders AlertDialogs (no native modal route, so Android Back and
navigation can never leave a blank screen behind).  ``close_control``/``close_all_dialogs``
work unchanged because the host tracks the logical control on the dialog stack.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

import flet as ft

from views.flet_compat import (
    _ensure_overlay_contains,
    _get_stack,
    _remove_from_overlay,
    _remove_from_stack,
    ALIGN_CENTER,
)

_STACK_ATTR = "_hawaa_dialog_stack"


def _as_controls(value) -> list:
    if value is None:
        return []
    if isinstance(value, ft.Control):
        return [value]
    return [item for item in (value or []) if item is not None]


class BottomSheetDialog:
    """A Nano-style form sheet: title bar + close button + scrollable body +
    sticky action row, rendered as a bottom-anchored overlay host.

    Works on Flet 0.28.x (pinned APK runtime) where ``page.open``/``page.close``
    helpers do not exist; the sheet content is mounted into a plain overlay
    Stack like every other dialog in this app.
    """

    def __init__(
        self,
        page: ft.Page,
        title: str,
        *,
        subtitle: str = "",
        body: ft.Control | Sequence[ft.Control] | None = None,
        actions: ft.Control | Sequence[ft.Control] | None = None,
        on_dismiss: Callable | None = None,
        dismissible: bool = True,
    ):
        self.page = page
        self.title = title
        self.subtitle = subtitle
        self.on_dismiss = on_dismiss
        self.dismissible = dismissible
        self.body = body
        self.actions = actions
        self.host: Optional[ft.Control] = None
        self.sheet: Optional[ft.Control] = None
        self._closed = False
        # When mounted by views/flet_compat.open_control() for an AlertDialog,
        # this hook closes through the logical dialog control so the dialog
        # stack, page.dialog pointer and on_dismiss all stay consistent.
        self._on_request_close: Optional[Callable] = None
        self._build()

    # -- construction ----------------------------------------------------

    def _title_bar(self) -> ft.Control:
        close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            tooltip="إغلاق",
            on_click=lambda _: self.request_close(),
        )
        header_controls = [
            ft.Column(
                [
                    ft.Text(self.title, size=18, weight=ft.FontWeight.BOLD),
                    *([ft.Text(self.subtitle, size=12, color="#64748B")] if self.subtitle else []),
                ],
                spacing=2,
                expand=True,
            ),
            close_btn,
        ]
        return ft.Container(
            ft.Row(header_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=16, right=8, top=14, bottom=12),
            border=ft.border.only(bottom=ft.BorderSide(1, "#E3E8F0")),
        )

    def _build(self) -> None:
        content: list = [self._title_bar()]
        body_controls = _as_controls(self.body)
        if body_controls:
            content.append(
                ft.Container(
                    ft.Column(body_controls, spacing=12, scroll=ft.ScrollMode.AUTO),
                    padding=ft.padding.symmetric(horizontal=16, vertical=14),
                    expand=True,
                )
            )
        action_controls = _as_controls(self.actions)
        if action_controls:
            content.append(
                ft.Container(
                    ft.Row(action_controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.only(left=16, right=16, top=10, bottom=16),
                    border=ft.border.only(top=ft.BorderSide(1, "#E3E8F0")),
                )
            )

        sheet = ft.Container(
            ft.Column(content, spacing=0),
            bgcolor="#FFFFFF",
            border_radius=ft.border_radius.only(top_left=24, top_right=24),
        )
        self.sheet = sheet

    # -- host (bottom-anchored overlay, Nano style) -----------------------

    def _build_host(self) -> ft.Control:
        width = 390.0
        height = 760.0
        try:
            width = float(getattr(self.page, "width", 0) or width)
        except Exception:
            pass
        try:
            height = float(getattr(self.page, "height", 0) or height)
        except Exception:
            pass
        # Phone sheets span the full width; desktop gets a centered column.
        sheet_width = width if width <= 600 else min(560.0, width - 32.0)
        max_body_height = max(240.0, min(640.0, height - 160.0))
        if self.sheet is not None:
            self.sheet.width = sheet_width
            try:
                self.sheet.height = max_body_height
            except Exception:
                pass

        def _outside_tap(event=None):
            if not self.dismissible:
                return
            self.request_close(event)

        barrier = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            bgcolor=ft.Colors.with_opacity(0.42, ft.Colors.BLACK),
            on_click=_outside_tap if self.dismissible else None,
        )
        bottom_row = ft.Container(
            left=0,
            right=0,
            bottom=0,
            alignment=ALIGN_CENTER,
            content=self.sheet,
        )
        return ft.Stack([barrier, bottom_row], expand=True, clip_behavior=ft.ClipBehavior.NONE)

    # -- open/close -------------------------------------------------------

    def request_close(self, event=None) -> None:
        """Close from the UI (X button / barrier), honoring the owner's hook."""
        hook = self._on_request_close
        if callable(hook):
            try:
                hook(event)
            except Exception:
                self.close()
            return
        original = self.on_dismiss
        self.close()
        if callable(original):
            try:
                original(event)
            except Exception:
                pass

    def open(self) -> None:
        """Show the sheet (idempotent)."""
        if self._closed or self.host is not None:
            return
        page = self.page
        if page is None:
            return
        self.host = self._build_host()
        _ensure_overlay_contains(page, self.host)
        stack = _get_stack(page)
        if self not in stack:
            stack.append(self)
        try:
            page.update()
        except Exception:
            pass

    def close(self) -> None:
        """Remove the sheet and its host from the overlay."""
        if self._closed:
            return
        self._closed = True
        page = self.page
        if page is None:
            return
        _remove_from_stack(page, self)
        if self.host is not None:
            _remove_from_overlay(page, self.host)
            self.host = None
        try:
            page.update()
        except Exception:
            pass

    # -- content mutation helpers ----------------------------------------

    def set_body(self, body) -> None:
        """Replace the scrollable body controls."""
        self.body = body
        column = getattr(self.sheet, "content", None) if self.sheet is not None else None
        controls = getattr(column, "controls", None) if column is not None else None
        if controls is not None and len(controls) >= 2:
            controls[1] = ft.Container(
                ft.Column(_as_controls(body), spacing=12, scroll=ft.ScrollMode.AUTO),
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                expand=True,
            )
            try:
                self.page.update()
            except Exception:
                pass


def open_form_sheet(
    page: ft.Page,
    title: str,
    *,
    subtitle: str = "",
    body=None,
    actions=None,
    on_dismiss=None,
    dismissible: bool = True,
) -> BottomSheetDialog:
    """Build, open and return a Nano-style bottom sheet in one call."""
    sheet = BottomSheetDialog(
        page, title, subtitle=subtitle, body=body, actions=actions,
        on_dismiss=on_dismiss, dismissible=dismissible,
    )
    sheet.open()
    return sheet


def confirm_sheet(
    page: ft.Page,
    title: str,
    message: str,
    confirm_text: str = "تأكيد",
    cancel_text: str = "إلغاء",
    *,
    on_confirm: Callable | None = None,
    on_cancel: Callable | None = None,
    danger: bool = False,
) -> BottomSheetDialog:
    """A confirmation sheet replacing centered confirm AlertDialogs."""
    holder: dict = {}

    def _fire(callback):
        def handler(_=None):
            opened = holder.get("sheet")
            if opened is not None:
                opened.close()
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass
        return handler

    confirm_color = "#EF4444" if danger else "#0A3F70"
    body = ft.Text(message, size=14)
    actions = ft.Row(
        [
            ft.TextButton(cancel_text, on_click=_fire(on_cancel)),
            ft.FilledButton(
                confirm_text,
                bgcolor=confirm_color,
                on_click=_fire(on_confirm),
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
        spacing=10,
    )
    opened = open_form_sheet(page, title, body=body, actions=actions, dismissible=True)
    holder["sheet"] = opened
    return opened


# ---------------------------------------------------------------------------
# AlertDialog-compatible adapter
# ---------------------------------------------------------------------------
#
# Existing dialog classes subclass ft.AlertDialog and are opened through
# views.flet_compat.open_control().  The adapter below lets those same
# classes render as bottom sheets without rewriting their constructors.


def _attach_sheet_behavior(cls):
    """Class decorator: make an AlertDialog subclass render as a bottom sheet."""

    def _build_sheet(self):
        return BottomSheetDialog(
            self._hawaa_sheet_page,
            getattr(self, "sheet_title", None) or getattr(self.title, "value", None) or "",
            subtitle=getattr(self, "sheet_subtitle", "") or "",
            body=getattr(self, "content", None),
            actions=getattr(self, "actions", None),
            on_dismiss=getattr(self, "on_dismiss", None),
            dismissible=bool(getattr(self, "dismissible", True)),
        )

    cls._build_sheet = _build_sheet
    return cls


__all__ = [
    "BottomSheetDialog",
    "open_form_sheet",
    "confirm_sheet",
]
