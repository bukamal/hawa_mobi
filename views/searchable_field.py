# -*- coding: utf-8 -*-
"""Searchable text input for Android forms.

Flet's mobile Dropdown is not comfortable when the list of companies/customers
grows.  This control keeps normal free typing, while showing tappable filtered
suggestions under the field.  It deliberately exposes ``value`` and
``on_change`` like ``ft.TextField`` so existing dialogs can adopt it without
changing their save logic.
"""
from __future__ import annotations

from typing import Callable, Iterable, List

import flet as ft

from services.company_search_service import normalize_search_text
from views.ui_kit import BORDER, CARD_BG, MUTED, PRIMARY, PRIMARY_SOFT, TEXT

SuggestionsProvider = Callable[[], Iterable[str]]


class SearchableTextField(ft.Column):
    def __init__(
        self,
        label: str,
        value: str = "",
        width=None,
        hint_text: str | None = None,
        suggestions_provider: SuggestionsProvider | None = None,
        disabled: bool = False,
        prefix_icon=None,
        max_suggestions: int = 7,
        on_change=None,
        dense: bool = False,
    ):
        self._external_on_change = on_change
        self.suggestions_provider = suggestions_provider or (lambda: [])
        self.max_suggestions = max(1, int(max_suggestions or 7))
        self._suppress_change = False
        self.field = ft.TextField(
            label=label,
            value=value or "",
            width=width,
            hint_text=hint_text,
            disabled=disabled,
            prefix_icon=prefix_icon or ft.Icons.SEARCH,
            border_radius=16,
            filled=True,
            bgcolor=CARD_BG,
            border_color=BORDER,
            focused_border_color=PRIMARY,
            on_change=self._handle_change,
        )
        self.suggestions_column = ft.Column(spacing=0, tight=True)
        self.suggestions_box = ft.Container(
            visible=False,
            content=self.suggestions_column,
            bgcolor=ft.Colors.WHITE,
            border_radius=14,
            border=ft.Border(
                left=ft.BorderSide(1, BORDER),
                top=ft.BorderSide(1, BORDER),
                right=ft.BorderSide(1, BORDER),
                bottom=ft.BorderSide(1, BORDER),
            ),
            padding=ft.Padding(left=4, right=4, top=4, bottom=4),
            margin=ft.Margin(left=0, right=0, top=-8, bottom=0),
            width=width,
        )
        super().__init__(controls=[self.field, self.suggestions_box], spacing=4, tight=True, width=width)

    @property
    def value(self):
        return self.field.value

    @value.setter
    def value(self, new_value):
        self.field.value = new_value or ""

    @property
    def disabled(self):
        return self.field.disabled

    @disabled.setter
    def disabled(self, value):
        self.field.disabled = bool(value)
        if value:
            self._hide_suggestions()

    @property
    def on_change(self):
        return self._external_on_change

    @on_change.setter
    def on_change(self, callback):
        self._external_on_change = callback

    @property
    def label(self):
        return self.field.label

    @label.setter
    def label(self, value):
        self.field.label = value

    @property
    def hint_text(self):
        return self.field.hint_text

    @hint_text.setter
    def hint_text(self, value):
        self.field.hint_text = value

    def focus(self):
        try:
            return self.field.focus()
        except Exception:
            return None

    def _all_suggestions(self) -> List[str]:
        try:
            raw = list(self.suggestions_provider() or [])
        except Exception:
            raw = []
        out: List[str] = []
        seen = set()
        for item in raw:
            text = str(item or "").strip()
            if not text:
                continue
            key = normalize_search_text(text)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(text)
        return out

    def _matches(self, query: str) -> List[str]:
        q = normalize_search_text(query)
        if not q:
            return []
        tokens = [t for t in q.split(" ") if t]
        results = []
        starts = []
        for item in self._all_suggestions():
            norm = normalize_search_text(item)
            if all(t in norm for t in tokens):
                (starts if norm.startswith(q) else results).append(item)
        return (starts + results)[: self.max_suggestions]

    def _handle_change(self, e=None):
        if not self._suppress_change:
            self._render_suggestions()
        if callable(self._external_on_change):
            self._external_on_change(e)

    def _hide_suggestions(self):
        self.suggestions_box.visible = False
        self.suggestions_column.controls = []

    def _choose(self, text: str):
        self._suppress_change = True
        self.field.value = text
        self._hide_suggestions()
        self._suppress_change = False
        if callable(self._external_on_change):
            self._external_on_change(None)
        try:
            self.update()
        except Exception:
            pass

    def _render_suggestions(self):
        if self.field.disabled:
            self._hide_suggestions()
            return
        matches = self._matches(self.field.value or "")
        if not matches:
            self._hide_suggestions()
            return
        controls = []
        for idx, text in enumerate(matches):
            controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.MANAGE_SEARCH, color=PRIMARY, size=16),
                        ft.Text(text, size=13, color=TEXT, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=8),
                    bgcolor=PRIMARY_SOFT if idx == 0 else ft.Colors.WHITE,
                    border_radius=10,
                    padding=ft.Padding(left=10, right=10, top=8, bottom=8),
                    on_click=lambda e, v=text: self._choose(v),
                )
            )
        controls.append(ft.Text("يمكنك اختيار نتيجة أو كتابة اسم جديد", size=10, color=MUTED))
        self.suggestions_column.controls = controls
        self.suggestions_box.visible = True
        try:
            self.update()
        except Exception:
            pass
