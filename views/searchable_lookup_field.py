# -*- coding: utf-8 -*-
"""Reusable Flet lookup/autocomplete field for Android dialogs.

This component intentionally behaves like a TextField for callers: read/write
`.value`, assign `.on_change`, and place the instance in a layout.  Internally it
shows normalized suggestions and lets users pick an existing item quickly.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

import flet as ft

try:
    from views.ui_kit import PRIMARY, PRIMARY_SOFT, TEXT, MUTED, BORDER
except Exception:  # Static/compile-only environments
    PRIMARY = "#0A3F70"
    PRIMARY_SOFT = "#EAF4FF"
    TEXT = "#172033"
    MUTED = "#667085"
    BORDER = "#D8E4EE"

LookupProvider = Callable[[str, int], List[Dict[str, Any]]]


class SearchableLookupField(ft.Column):
    def __init__(
        self,
        *,
        label: str,
        value: str = "",
        hint_text: str = "",
        width: float | int | None = None,
        provider: LookupProvider | None = None,
        lookup_type: str = "generic",
        allow_create: bool = True,
        create_label: str | None = None,
        max_results: int = 6,
        disabled: bool = False,
        strict_existing: bool = False,
    ):
        super().__init__(spacing=6, tight=True)
        self.lookup_type = lookup_type
        self.provider = provider
        self.allow_create = bool(allow_create)
        self.strict_existing = bool(strict_existing)
        self.max_results = max(1, int(max_results or 6))
        self.create_label = create_label or "استخدام / إنشاء هذا الاسم"
        self.selected_option: Dict[str, Any] | None = None
        self.selected_value = str(value or "").strip()
        self._external_on_change = None
        self._suggestion_buttons: List[Any] = []
        self.field = ft.TextField(
            label=label,
            value=str(value or ""),
            hint_text=hint_text,
            width=width,
            disabled=disabled,
            border_radius=12,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_text_change,
        )
        self.suggestions = ft.Column(spacing=4, visible=False)
        self.controls = [self.field, self.suggestions]

    @property
    def value(self) -> str:
        return str(self.field.value or "").strip()

    @value.setter
    def value(self, new_value: Any) -> None:
        self.field.value = str(new_value or "")
        self.selected_value = self.value

    @property
    def disabled(self) -> bool:
        return bool(getattr(self.field, "disabled", False))

    @disabled.setter
    def disabled(self, value: bool) -> None:
        self.field.disabled = bool(value)

    @property
    def on_change(self):
        return self._external_on_change

    @on_change.setter
    def on_change(self, handler):
        self._external_on_change = handler

    def clear_selection(self) -> None:
        self.selected_option = None
        self.selected_value = ""

    def require_value(self, label: str | None = None) -> str:
        value = self.value
        if not value:
            raise ValueError(f"{label or self.field.label or 'القيمة'} مطلوبة")
        return value

    def _call_external(self, event) -> None:
        if callable(self._external_on_change):
            self._external_on_change(event)

    def _on_text_change(self, event) -> None:
        self.selected_option = None
        self.selected_value = self.value
        self._refresh_suggestions()
        self._call_external(event)

    def _option_button(self, option: Dict[str, Any], label: str, subtitle: str = ""):
        icon = ft.Icons.BUSINESS if self.lookup_type == "company" else (ft.Icons.PERSON if self.lookup_type == "person" else ft.Icons.TRAVEL_EXPLORE)
        return ft.TextButton(
            on_click=lambda e, opt=option: self._select_option(opt),
            style=ft.ButtonStyle(padding=8),
            content=ft.Row([
                ft.Icon(icon, size=16, color=PRIMARY),
                ft.Column([
                    ft.Text(label, size=13, weight=ft.FontWeight.BOLD, color=TEXT, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(subtitle, size=11, color=MUTED, visible=bool(subtitle), overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=1, expand=True),
            ], spacing=8, tight=True),
        )

    def _refresh_suggestions(self) -> None:
        if self.disabled:
            self.suggestions.visible = False
            return
        query = self.value
        options: List[Dict[str, Any]] = []
        if callable(self.provider):
            try:
                options = list(self.provider(query, self.max_results) or [])
            except Exception:
                options = []
        controls = []
        for opt in options[: self.max_results]:
            label = str(opt.get("label") or opt.get("value") or "").strip()
            if not label:
                continue
            controls.append(self._option_button(opt, label, str(opt.get("subtitle") or "")))
        exact = {str(o.get("value") or "").strip() for o in options}
        if self.allow_create and query and query not in exact:
            controls.append(self._option_button({"value": query, "label": query, "kind": self.lookup_type, "is_new": True}, f"+ {self.create_label}: {query}", "سيُستخدم كنص جديد بعد التأكيد بالحفظ"))
        self.suggestions.controls = controls
        self.suggestions.visible = bool(controls and (len(query) >= 2 or options))
        try:
            self.update()
        except Exception:
            pass

    def _select_option(self, option: Dict[str, Any]) -> None:
        self.selected_option = dict(option or {})
        self.selected_value = str(self.selected_option.get("value") or self.selected_option.get("label") or "").strip()
        self.field.value = self.selected_value
        self.suggestions.visible = False
        try:
            self.update()
        except Exception:
            pass
        self._call_external(None)


def company_lookup_field(label: str, value: str = "", width=None, hint_text: str = "", disabled: bool = False) -> SearchableLookupField:
    from services.lookup_service import search_company_options
    return SearchableLookupField(label=label, value=value, width=width, hint_text=hint_text or "اكتب حرفين للبحث في الحسابات", provider=search_company_options, lookup_type="company", allow_create=True, create_label="إنشاء/استخدام حساب شركة", disabled=disabled)


def person_lookup_field(label: str, value: str = "", width=None, hint_text: str = "") -> SearchableLookupField:
    from services.lookup_service import search_person_options
    return SearchableLookupField(label=label, value=value, width=width, hint_text=hint_text or "اكتب اسم المسافر أو الزبون", provider=search_person_options, lookup_type="person", allow_create=True, create_label="استخدام مسافر جديد")


def service_type_lookup_field(label: str, value: str = "", width=None) -> SearchableLookupField:
    from services.lookup_service import search_service_type_options
    return SearchableLookupField(label=label, value=value, width=width, hint_text="ابحث في أنواع الخدمات", provider=search_service_type_options, lookup_type="service_type", allow_create=True, create_label="إضافة نوع خدمة")
