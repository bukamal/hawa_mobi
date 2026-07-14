# -*- coding: utf-8 -*-
"""Unified financial operation date picker for mobile dialogs.

All financial operations must use the same operation-date UX so normal ledger
entries, service cases and third-party payments carry a consistent accounting
date.  The creation timestamp remains internal; this component controls only the
operation date stored on ledger rows.
"""
from __future__ import annotations

import datetime as _dt
from typing import Callable, Optional

import flet as ft

from database.connection import get_setting, set_setting
from views.flet_compat import open_control, close_control
from views.ui_kit import PRIMARY, PRIMARY_SOFT, MUTED, BORDER

LAST_OPERATION_DATE_KEY = "finance/last_operation_date"
_DATE_FORMAT = "%Y-%m-%d"


def today_iso() -> str:
    return _dt.datetime.now().strftime(_DATE_FORMAT)


def yesterday_iso() -> str:
    return (_dt.datetime.now() - _dt.timedelta(days=1)).strftime(_DATE_FORMAT)


def normalize_financial_date(value, *, field_label: str = "تاريخ العملية") -> str:
    """Return a strict YYYY-MM-DD date or raise a user-facing ValueError."""
    if isinstance(value, _dt.datetime):
        return value.strftime(_DATE_FORMAT)
    if isinstance(value, _dt.date):
        return value.strftime(_DATE_FORMAT)
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_label} مطلوب")
    try:
        parsed = _dt.datetime.strptime(text, _DATE_FORMAT)
    except Exception:
        raise ValueError(f"{field_label} يجب أن يكون بصيغة YYYY-MM-DD")
    return parsed.strftime(_DATE_FORMAT)


def _read_last_operation_date(default: Optional[str] = None) -> str:
    fallback = default or today_iso()
    try:
        stored = get_setting(LAST_OPERATION_DATE_KEY, "") or ""
        return normalize_financial_date(stored, field_label="آخر تاريخ مستخدم") if stored else fallback
    except Exception:
        return fallback


def remember_last_operation_date(value) -> None:
    try:
        set_setting(LAST_OPERATION_DATE_KEY, normalize_financial_date(value))
    except Exception:
        # Remembering is a convenience feature; it must never block saving.
        pass


class FinancialDateField(ft.Column):
    """A reusable operation-date control with DatePicker and quick choices."""

    def __init__(
        self,
        page,
        label: str = "تاريخ العملية",
        value: Optional[str] = None,
        width: int | float = 190,
        include_quick_buttons: bool = True,
        on_change: Optional[Callable[[str], None]] = None,
        use_last_date: bool = True,
    ):
        super().__init__(
            controls=[],
            spacing=4,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )
        self._page = page
        self.label = label or "تاريخ العملية"
        self._on_change_callback = on_change
        initial = value or (_read_last_operation_date() if use_last_date else today_iso())
        try:
            initial = normalize_financial_date(initial, field_label=self.label)
        except Exception:
            initial = today_iso()

        self.field = ft.TextField(
            label=self.label,
            value=initial,
            hint_text="YYYY-MM-DD",
            width=width,
            read_only=True,
            text_align=ft.TextAlign.CENTER,
            border_color=BORDER,
            focused_border_color=PRIMARY,
            suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, icon_color=PRIMARY, on_click=self._open_picker),
        )
        self.date_picker = ft.DatePicker(
            on_change=self._on_picker_change,
            first_date=_dt.datetime(2020, 1, 1),
            last_date=_dt.datetime.now() + _dt.timedelta(days=365 * 10),
        )
        try:
            self.date_picker.value = _dt.datetime.strptime(initial, _DATE_FORMAT)
        except Exception:
            pass

        quick_row = ft.Row(
            controls=[
                self._quick_button("اليوم", lambda e: self.set_value(today_iso())),
                self._quick_button("أمس", lambda e: self.set_value(yesterday_iso())),
                self._quick_button("آخر تاريخ", lambda e: self.set_value(_read_last_operation_date(self.value))),
            ],
            spacing=4,
            run_spacing=4,
            wrap=True,
            visible=bool(include_quick_buttons),
        )
        self.controls = [self.field, quick_row]

    def _quick_button(self, label: str, on_click):
        return ft.TextButton(
            content=ft.Row([ft.Icon(ft.Icons.EVENT_AVAILABLE, size=13, color=PRIMARY), ft.Text(label, size=11, color=PRIMARY)], tight=True, spacing=3),
            on_click=on_click,
        )

    @property
    def value(self) -> str:
        return str(self.field.value or "").strip()

    @value.setter
    def value(self, new_value):
        self.set_value(new_value, update=False)

    def _open_picker(self, e=None):
        try:
            self.date_picker.value = _dt.datetime.strptime(self.value, _DATE_FORMAT)
        except Exception:
            self.date_picker.value = _dt.datetime.now()
        open_control(self._page, self.date_picker)

    def _on_picker_change(self, e=None):
        selected = getattr(self.date_picker, "value", None)
        if selected:
            self.set_value(selected)

    def set_value(self, new_value, *, update: bool = True) -> str:
        value = normalize_financial_date(new_value, field_label=self.label)
        self.field.value = value
        try:
            self.date_picker.value = _dt.datetime.strptime(value, _DATE_FORMAT)
        except Exception:
            pass
        if callable(self._on_change_callback):
            try:
                self._on_change_callback(value)
            except TypeError:
                self._on_change_callback(None)
            except Exception:
                pass
        if update:
            try:
                self._page.update()
            except Exception:
                pass
        return value

    def require_value(self, field_label: Optional[str] = None) -> str:
        return normalize_financial_date(self.value, field_label=field_label or self.label)

    def remember(self) -> None:
        remember_last_operation_date(self.value)

    def close(self) -> None:
        try:
            close_control(self._page, self.date_picker)
        except Exception:
            pass
