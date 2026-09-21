# -*- coding: utf-8 -*-
"""Reusable modern components used by every Hawaa screen."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

import flet as ft
from .tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_LIGHT, BRAND_PRIMARY_TINT, BRAND_PRIMARY_BORDER,
    LIGHT_BACKGROUND, LIGHT_SURFACE, LIGHT_SURFACE_ALT, LIGHT_BORDER, LIGHT_TEXT_PRIMARY, LIGHT_TEXT_SECONDARY,
    LIGHT_TEXT_MUTED, LIGHT_TEXT_FAINT, SHADOW_LIGHT,
    STATE_DANGER, STATE_DANGER_SOFT, STATE_SUCCESS, STATE_SUCCESS_SOFT,
    STATE_WARNING, STATE_WARNING_SOFT, STATE_INFO, STATE_INFO_SOFT,
    TEXT_BODY, TEXT_BUTTON, TEXT_CARD_TITLE, TEXT_PAGE_TITLE, TEXT_SECONDARY,
    SPACE_2, SPACE_3, SPACE_4, SPACE_5,
    RADIUS_BUTTON, RADIUS_CARD, RADIUS_FIELD, TOUCH_TARGET,
)


def _border(color=LIGHT_BORDER, width=1):
    side = ft.BorderSide(width, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def app_surface(content, *, padding=SPACE_4, margin=None, on_click=None, bgcolor=LIGHT_SURFACE, border_color=LIGHT_BORDER, radius=RADIUS_CARD, elevation=0):
    kwargs = dict(
        content=content,
        padding=padding,
        margin=margin,
        bgcolor=bgcolor,
        border_radius=radius,
        border=_border(border_color),
    )
    if on_click is not None:
        kwargs.update(on_click=on_click, ink=True)
    container = ft.Container(**kwargs)
    if elevation:
        return ft.Card(content=container, elevation=elevation, margin=0)
    return container


def icon_badge(icon, *, color=BRAND_PRIMARY, bgcolor=BRAND_PRIMARY_LIGHT, size=22, padding=10):
    return ft.Container(
        content=ft.Icon(icon, color=color, size=size),
        bgcolor=bgcolor,
        border_radius=RADIUS_CARD,
        padding=padding,
    )


def screen_header(title, *, subtitle=None, icon=None, trailing=None, compact=False):
    return ft.Container(
        content=ft.Row(
            [
                icon_badge(icon, size=20, padding=9) if icon else ft.Container(width=0, height=0),
                ft.Column(
                    [
                        ft.Text(title, size=20 if compact else TEXT_PAGE_TITLE, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(subtitle or "", size=TEXT_SECONDARY, color=LIGHT_TEXT_SECONDARY, visible=bool(subtitle), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=2,
                    expand=True,
                ),
                trailing or ft.Container(width=0, height=0),
            ],
            spacing=SPACE_3,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(SPACE_2, SPACE_3, SPACE_2, SPACE_2),
    )


def modern_text_field(*, label, value=None, hint_text=None, icon=None, password=False, can_reveal_password=False, on_change=None, on_submit=None, read_only=False, expand=False, width=None, suffix=None, keyboard_type=None):
    return ft.TextField(
        label=label,
        value=value,
        hint_text=hint_text,
        prefix_icon=icon,
        password=password,
        can_reveal_password=can_reveal_password,
        on_change=on_change,
        on_submit=on_submit,
        read_only=read_only,
        expand=expand,
        width=width,
        suffix=suffix,
        keyboard_type=keyboard_type,
        border_radius=RADIUS_FIELD,
        filled=True,
        bgcolor=LIGHT_SURFACE,
        border_color=LIGHT_BORDER,
        focused_border_color=BRAND_PRIMARY,
        text_size=TEXT_BODY,
        content_padding=ft.Padding(SPACE_4, SPACE_4, SPACE_4, SPACE_4),
    )


def modern_dropdown(*, label, value=None, options=None, on_change=None, editable=False, expand=False, width=None, icon=None):
    return ft.Dropdown(
        label=label,
        value=value,
        options=options or [],
        on_change=on_change,
        editable=editable,
        expand=expand,
        width=width,
        border_radius=RADIUS_FIELD,
        filled=True,
        bgcolor=LIGHT_SURFACE,
        border_color=LIGHT_BORDER,
        focused_border_color=BRAND_PRIMARY,
        text_size=TEXT_BODY,
        content_padding=ft.Padding(SPACE_4, SPACE_4, SPACE_4, SPACE_4),
    )


def button_content(label, icon=None, *, color=None):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=19, color=color))
    controls.append(ft.Text(label, size=TEXT_BUTTON, weight=ft.FontWeight.BOLD, color=color))
    return ft.Row(controls, spacing=SPACE_2, tight=True, alignment=ft.MainAxisAlignment.CENTER)


def primary_action(label, *, icon=None, on_click=None, width=None, expand=False, disabled=False):
    return ft.FilledButton(
        content=button_content(label, icon, color=ft.Colors.WHITE),
        on_click=on_click,
        bgcolor=BRAND_PRIMARY,
        color=ft.Colors.WHITE,
        height=TOUCH_TARGET,
        width=width,
        expand=expand,
        disabled=disabled,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON)),
    )


def secondary_action(label, *, icon=None, on_click=None, width=None, expand=False):
    return ft.OutlinedButton(
        content=button_content(label, icon, color=BRAND_PRIMARY),
        on_click=on_click,
        height=TOUCH_TARGET,
        width=width,
        expand=expand,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON), side=ft.BorderSide(1, LIGHT_BORDER)),
    )


def danger_action(label, *, icon=None, on_click=None, width=None, expand=False):
    return ft.FilledButton(
        content=button_content(label, icon, color=ft.Colors.WHITE),
        on_click=on_click,
        bgcolor=STATE_DANGER,
        color=ft.Colors.WHITE,
        height=TOUCH_TARGET,
        width=width,
        expand=expand,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON)),
    )


def semantic_chip(text, *, icon=None, tone="info"):
    palette = {
        "success": (STATE_SUCCESS, STATE_SUCCESS_SOFT),
        "danger": (STATE_DANGER, STATE_DANGER_SOFT),
        "warning": (STATE_WARNING, STATE_WARNING_SOFT),
        "info": (BRAND_PRIMARY, BRAND_PRIMARY_LIGHT),
        "neutral": (LIGHT_TEXT_SECONDARY, BRAND_PRIMARY_TINT),
    }
    color, bgcolor = palette.get(tone, palette["info"])
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=15, color=color))
    controls.append(ft.Text(str(text), size=11, color=color, weight=ft.FontWeight.BOLD))
    return ft.Container(
        content=ft.Row(controls, spacing=5, tight=True),
        bgcolor=bgcolor,
        border_radius=999,
        border=_border(color),
        padding=ft.Padding(10, 5, 10, 5),
    )


def _financial_value(value):
    raw = str(value or "").replace("\u2066", "").replace("\u2069", "").strip()
    markers = ("USD", "EUR", "SYP", "SAR", "AED", "QAR", "KWD", "OMR", "$", "€", "£", "ل.س", "﷼", "د.إ", "ر.ق", "د.ك", "ر.ع")
    if not any(marker in raw for marker in markers) or not any(ch.isdigit() for ch in raw):
        return raw, False
    remainder = raw
    for marker in markers:
        remainder = remainder.replace(marker, "")
    remainder = re.sub(r"[0-9٠-٩,،.٫\-+()\sKMBTkmbt]", "", remainder)
    if remainder:
        return raw, False
    return "\u2066" + raw + "\u2069", True


def metric_card(label, value, *, icon=None, color=BRAND_PRIMARY, subtitle=None, on_click=None, prominent=False):
    display_value, financial = _financial_value(value)
    return app_surface(
        ft.Column(
            [
                ft.Row([
                    icon_badge(icon or ft.Icons.INSIGHTS, color=color, bgcolor=BRAND_PRIMARY_TINT, size=22),
                    ft.Text(label, size=TEXT_SECONDARY, color=LIGHT_TEXT_SECONDARY, expand=True),
                ], spacing=SPACE_3),
                ft.Text(
                    display_value, size=26 if prominent else 20, weight=ft.FontWeight.BOLD, color=color,
                    max_lines=1 if financial else 3, no_wrap=True if financial else None,
                    overflow=ft.TextOverflow.VISIBLE if financial else ft.TextOverflow.ELLIPSIS,
                    rtl=False if financial else None,
                ),
                ft.Text(subtitle or "", size=11, color=LIGHT_TEXT_SECONDARY, visible=bool(subtitle), max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=SPACE_2,
        ),
        padding=SPACE_4,
        on_click=on_click,
    )


def section_title(text, *, icon=None, action=None):
    return ft.Row([
        ft.Icon(icon, size=18, color=BRAND_PRIMARY) if icon else ft.Container(width=0, height=0),
        ft.Text(text, size=TEXT_CARD_TITLE, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY, expand=True),
        action or ft.Container(width=0, height=0),
    ], spacing=SPACE_2, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def divider():
    return ft.Divider(height=1, thickness=1, color=LIGHT_BORDER)


# ---------------------------------------------------------------------------
# Nano-style components
# ---------------------------------------------------------------------------

def soft_shadow(blur=18, y=5, spread=0):
    return ft.BoxShadow(blur_radius=blur, spread_radius=spread, color=SHADOW_LIGHT, offset=ft.Offset(0, y))


def status_pill(text, fg, bg, *, size=9):
    """Small filled state chip (payment/stock status rows)."""
    return ft.Container(
        ft.Text(str(text), size=size, color=fg, weight=ft.FontWeight.BOLD),
        padding=ft.Padding(left=8, right=8, top=4, bottom=4),
        bgcolor=bg,
        border_radius=12,
    )


def kpi_card(label, value, icon, accent, *, on_tap=None):
    """Compact KPI card: badge + caption + bold value.

    ``on_tap`` turns the whole card into a tappable filter shortcut with a
    trailing chevron.
    """
    return ft.Container(
        ft.Row(
            [
                ft.Container(
                    ft.Icon(icon, color=accent, size=20),
                    width=40, height=40, alignment=ft.alignment.center,
                    bgcolor=LIGHT_BACKGROUND, border_radius=13,
                ),
                ft.Column(
                    [
                        ft.Text(label, size=10, color=LIGHT_TEXT_SECONDARY),
                        ft.Text(str(value), size=16, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=2, expand=True,
                ),
                *([ft.Icon(ft.Icons.CHEVRON_LEFT_ROUNDED, size=16, color=LIGHT_TEXT_FAINT)] if on_tap else []),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=11, bgcolor=LIGHT_SURFACE, border=_border(LIGHT_BORDER),
        border_radius=16, shadow=soft_shadow(blur=10, y=2),
        ink=bool(on_tap), on_click=on_tap,
    )


def pulse_metric_chip(label, value, color):
    return ft.Container(
        ft.Column(
            [
                ft.Text(label, size=9, color=LIGHT_TEXT_MUTED),
                ft.Text(str(value), size=12, weight=ft.FontWeight.BOLD, color=color),
            ],
            spacing=1, tight=True,
        ),
        padding=ft.Padding(left=10, right=10, top=6, bottom=6),
        bgcolor=LIGHT_SURFACE,
        border_radius=10,
        border=_border(LIGHT_BORDER),
    )


def pulse_card(*, icon, headline, body, severity="info", chips=(), crisis=None,
               action_label=None, on_action=None, on_crisis_tap=None):
    """Rich 15-second business summary card (Nano owner-pulse pattern).

    ``chips`` is an iterable of ``(label, value, color)`` tuples; ``crisis``
    is an optional banner text shown when a critical condition is active.
    """
    palette = {
        "urgent": (STATE_DANGER, STATE_DANGER_SOFT, ft.Icons.PRIORITY_HIGH_ROUNDED),
        "warning": (STATE_WARNING, STATE_WARNING_SOFT, ft.Icons.WARNING_AMBER_ROUNDED),
        "info": (BRAND_PRIMARY, STATE_INFO_SOFT, ft.Icons.INFO_OUTLINE_ROUNDED),
    }
    color, bg, icon_name = palette.get(severity, palette["info"])
    icon = icon or icon_name

    chip_controls = [pulse_metric_chip(label, value, c) for label, value, c in chips]
    crisis_banner = ft.Container(height=0)
    if crisis:
        crisis_banner = ft.Container(
            ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=16, color=STATE_DANGER),
                    ft.Text(str(crisis), size=11, weight=ft.FontWeight.W_600, color=STATE_DANGER),
                ],
                spacing=6,
            ),
            padding=ft.Padding(left=10, right=10, top=6, bottom=6),
            bgcolor=STATE_DANGER_SOFT,
            border_radius=10,
            on_click=(lambda e: on_crisis_tap()) if on_crisis_tap else None,
            ink=bool(on_crisis_tap),
        )

    action_row = ft.Container(height=0)
    if action_label:
        def _tap(_e=None):
            if on_action:
                on_action(_e)

        action_row = ft.Container(
            ft.Row(
                [
                    ft.Text(action_label, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ft.Icon(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, size=12, color=ft.Colors.WHITE),
                ],
                spacing=4,
                tight=True,
            ),
            padding=ft.Padding(left=14, right=14, top=8, bottom=8),
            bgcolor=color,
            border_radius=12,
            on_click=_tap,
            ink=True,
        )

    return ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            ft.Icon(icon, size=22, color=color),
                            width=44, height=44, alignment=ft.alignment.center,
                            bgcolor=LIGHT_SURFACE, border_radius=14,
                        ),
                        ft.Column(
                            [
                                ft.Text("نبض المالك", size=10, color=LIGHT_TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                                ft.Text(str(headline), size=15, weight=ft.FontWeight.BOLD, color=LIGHT_TEXT_PRIMARY),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(str(body), size=12, color=LIGHT_TEXT_SECONDARY),
                crisis_banner,
                ft.Row(list(chip_controls), spacing=8, wrap=True) if chip_controls else ft.Container(height=0),
                action_row,
            ],
            spacing=10,
        ),
        padding=14,
        bgcolor=bg,
        border=_border(color),
        border_radius=18,
        shadow=soft_shadow(blur=10, y=2),
    )


@dataclass(frozen=True)
class SegmentOption:
    key: str
    label: str
    icon: str | None = None


class SegmentedToggle(ft.Row):
    """Pill-style segmented control for a small, fixed set of choices."""

    def __init__(self, *, options, value=None, on_change=None, label=None):
        self._options = [o if isinstance(o, SegmentOption) else SegmentOption(*o) for o in options]
        self._value = value
        self._on_change = on_change
        self._label = label
        self._chips = {}
        super().__init__(controls=list(self._build_chips()), spacing=8)

    def _build_chips(self):
        for option in self._options:
            chip = self._chip(option)
            self._chips[option.key] = chip
            yield chip

    def _chip(self, option):
        active = option.key == self._value
        items = []
        if option.icon:
            items.append(ft.Icon(option.icon, size=16, color=ft.Colors.WHITE if active else LIGHT_TEXT_MUTED))
        items.append(ft.Text(
            option.label,
            size=13,
            color=ft.Colors.WHITE if active else LIGHT_TEXT_MUTED,
            weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_500,
        ))
        return ft.Container(
            content=ft.Row(items, spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.Padding(left=16, right=16, top=11, bottom=11),
            bgcolor=BRAND_PRIMARY if active else LIGHT_SURFACE,
            border=ft.border.all(1, BRAND_PRIMARY if active else LIGHT_BORDER),
            border_radius=14,
            ink=True,
            expand=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _, k=option.key: self._select(k),
        )

    def _select(self, key):
        if key == self._value:
            return
        self._value = key
        self._refresh_styles()
        self._safe_update()
        if self._on_change:
            self._on_change(None)

    def _refresh_styles(self):
        for option in self._options:
            active = option.key == self._value
            chip = self._chips[option.key]
            row = chip.content
            row.controls[-1].color = ft.Colors.WHITE if active else LIGHT_TEXT_MUTED
            row.controls[-1].weight = ft.FontWeight.BOLD if active else ft.FontWeight.W_500
            if option.icon:
                row.controls[0].color = ft.Colors.WHITE if active else LIGHT_TEXT_MUTED
            chip.bgcolor = BRAND_PRIMARY if active else LIGHT_SURFACE
            chip.border = ft.border.all(1, BRAND_PRIMARY if active else LIGHT_BORDER)

    def _safe_update(self):
        try:
            self.update()
        except Exception:
            pass

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, key):
        self._value = key
        self._refresh_styles()

    @property
    def on_change(self):
        return self._on_change

    @on_change.setter
    def on_change(self, callback):
        self._on_change = callback


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


class SmartAmountField(ft.TextField):
    """Money/price field that accepts only digits and one decimal point.

    Filters Arabic-Indic digits, a second decimal separator, letters and
    symbols on every keystroke so downstream ``float(field.value or 0)``
    reads never raise.
    """

    def __init__(self, *args, on_change: Callable | None = None, allow_negative: bool = False, **kwargs):
        self._user_on_change = on_change
        self._allow_negative = allow_negative
        kwargs.setdefault("keyboard_type", ft.KeyboardType.NUMBER)
        kwargs.setdefault("border_radius", RADIUS_FIELD)
        kwargs.setdefault("filled", True)
        kwargs.setdefault("bgcolor", LIGHT_SURFACE)
        kwargs.setdefault("border_color", LIGHT_BORDER)
        kwargs.setdefault("focused_border_color", BRAND_PRIMARY)
        kwargs.setdefault("text_size", TEXT_BODY)
        super().__init__(*args, on_change=self._sanitize_and_forward, **kwargs)

    def _sanitize(self, text):
        text = str(text or "").translate(_AR_DIGITS)
        out = []
        seen_dot = False
        for i, ch in enumerate(text):
            if ch.isdigit():
                out.append(ch)
            elif ch == "." and not seen_dot:
                seen_dot = True
                out.append(ch)
            elif ch == "-" and self._allow_negative and i == 0 and "-" not in out:
                out.append(ch)
        return "".join(out)

    def _sanitize_and_forward(self, e):
        cleaned = self._sanitize(self.value or "")
        if cleaned != (self.value or ""):
            self.value = cleaned
            try:
                self.update()
            except Exception:
                pass
        if self._user_on_change:
            self._user_on_change(e)
