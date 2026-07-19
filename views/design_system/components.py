# -*- coding: utf-8 -*-
"""Reusable modern components used by every Hawaa screen."""
from __future__ import annotations

import re
import flet as ft
from .tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_LIGHT, BRAND_PRIMARY_TINT,
    LIGHT_SURFACE, LIGHT_BORDER, LIGHT_TEXT_PRIMARY, LIGHT_TEXT_SECONDARY,
    STATE_DANGER, STATE_DANGER_SOFT, STATE_SUCCESS, STATE_SUCCESS_SOFT,
    STATE_WARNING, STATE_WARNING_SOFT,
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
