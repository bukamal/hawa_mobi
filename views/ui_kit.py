# -*- coding: utf-8 -*-
"""Unified, dependency-light UI facade for all Android views.

Phase 100 keeps the public helper names used by previous phases, while routing
all presentation through one visual system.  This module must stay free of
business/database/network imports so it is safe for APK builds.
"""
from __future__ import annotations

import flet as ft
from views.flet_compat import (
    ALIGN_CENTER, ALIGN_TOP_LEFT, ALIGN_BOTTOM_RIGHT,
    show_snackbar as compat_show_snackbar,
)
from views.design_system.tokens import (
    BRAND_PRIMARY_DARK, BRAND_PRIMARY_LIGHT, BRAND_PRIMARY_TINT, BRAND_ACCENT,
    BRAND_GOLD, LIGHT_BACKGROUND, LIGHT_SURFACE, LIGHT_TEXT_SECONDARY,
    LIGHT_TEXT_PRIMARY, LIGHT_BORDER, STATE_DANGER_SOFT, STATE_SUCCESS_SOFT,
    STATE_WARNING_SOFT, TEXT_BODY, TEXT_SECONDARY, TEXT_CARD_TITLE,
    TEXT_PAGE_TITLE, RADIUS_CARD, RADIUS_FIELD, TOUCH_TARGET,
)
from views.design_system.components import (
    app_surface, icon_badge, screen_header, modern_text_field,
    primary_action, secondary_action, danger_action, semantic_chip,
    metric_card, section_title,
)
from views.design_system.responsive import responsive_container, responsive_grid

# Backwards-compatible public tokens.  The exact brand constants are retained
# because reports, launcher assets and smoke tests share the supplied identity.
PRIMARY = "#0A3F70"
PRIMARY_DARK = "#062B4D"
PRIMARY_SOFT = "#EAF4FF"
PRIMARY_TINT = "#F4F8FC"
ACCENT = "#168AAD"
ACCENT_DARK = "#0E6985"
PAGE_BG = "#F5F7FA"
CARD_BG = ft.Colors.WHITE
MUTED = "#64748B"
TEXT = "#17212B"
BORDER = "#E2E8F0"
DANGER = "#E54848"
DANGER_SOFT = "#FDECEC"
SUCCESS = "#1FA56A"
SUCCESS_SOFT = "#E9F8F0"
WARNING = "#D9A441"
WARNING_SOFT = "#FFF7E3"
INFO = "#0369A1"
INFO_SOFT = "#E8F4FA"
SHADOW = "#CBD5E1"
RECEIVABLE = "#2563EB"
PAYABLE = "#D97706"

ASSET_APP_SYMBOL = "/app_logo.png"
ASSET_APP_WORDMARK = "/brand/app_wordmark.png"
ASSET_APP_ICON = "/icon_android.png"


def _full_border(color=BORDER, width=1):
    side = ft.BorderSide(width, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def image_fit(name: str) -> str:
    """Return an APK-safe BoxFit string across old/new Flet runtimes."""
    normalized = str(name or "contain").strip().lower()
    allowed = {"contain", "cover", "fill", "fit_width", "fit_height", "none", "scale_down"}
    return normalized if normalized in allowed else "contain"


def app_mark(size=86, color=PRIMARY, dark=False):
    return ft.Container(
        width=size,
        height=size,
        border_radius=max(18, size // 5),
        bgcolor=ft.Colors.WHITE,
        border=_full_border("#E2EBF5"),
        shadow=ft.BoxShadow(blur_radius=18, spread_radius=0, color=ft.Colors.BLACK12),
        padding=max(5, size // 16),
        content=ft.Image(src=ASSET_APP_SYMBOL, width=size, height=size, fit=image_fit("contain")),
    )


def brand_wordmark(width=260, height=92, dark=True):
    return ft.Image(src=ASSET_APP_WORDMARK, width=width, height=height, fit=image_fit("contain"))


def app_brand(title='هوى الشام', subtitle='نظام الحسابات الداخلية', size=86, color=PRIMARY, dark=False, wordmark=False):
    text_color = ft.Colors.WHITE if not dark else TEXT
    sub_color = "#DCE9F5" if not dark else MUTED
    controls = [app_mark(size=size, color=color, dark=dark)]
    if wordmark:
        controls.append(brand_wordmark(width=max(220, int(size * 3.4)), height=max(70, int(size * 1.1)), dark=dark))
    else:
        controls.extend([
            ft.Text(title, size=23 if size < 90 else 30, weight=ft.FontWeight.BOLD, color=text_color, text_align=ft.TextAlign.CENTER),
            ft.Text(subtitle, size=12 if size < 90 else 14, color=sub_color, text_align=ft.TextAlign.CENTER),
        ])
    return ft.Column(
        controls=controls,
        spacing=7,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )


def brand_background(content, padding=24, dark=True):
    colors = ["#061B33", PRIMARY_DARK, PRIMARY, "#0E5B95"] if dark else ["#EEF5FB", PAGE_BG, "#FFFFFF"]
    return ft.Container(
        expand=True,
        padding=padding,
        alignment=ALIGN_CENTER,
        gradient=ft.LinearGradient(begin=ALIGN_TOP_LEFT, end=ALIGN_BOTTOM_RIGHT, colors=colors),
        content=content,
    )


def brand_card(content, width=420, padding=24):
    return ft.Container(
        content=content,
        padding=padding,
        width=width,
        bgcolor=CARD_BG,
        border_radius=22,
        border=_full_border(BORDER),
        shadow=ft.BoxShadow(blur_radius=24, spread_radius=0, color=ft.Colors.BLACK12),
    )


def status_chip(text, icon=None, color=PRIMARY, bgcolor=PRIMARY_SOFT):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=15, color=color))
    controls.append(ft.Text(str(text), size=11, color=color, weight=ft.FontWeight.BOLD))
    return ft.Container(
        content=ft.Row(controls, spacing=5, tight=True, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=bgcolor,
        border_radius=999,
        border=_full_border(color),
        padding=ft.Padding(left=10, right=10, top=5, bottom=5),
    )


def show_snackbar(page, message, is_error=False, duration=3000):
    return compat_show_snackbar(page, message, is_error=is_error, duration=duration)


def page_header(title, icon=None, trailing=None, subtitle=None):
    return screen_header(title, icon=icon, trailing=trailing, subtitle=subtitle)


def search_field(label, on_change):
    field = modern_text_field(label=label, icon=ft.Icons.SEARCH, on_change=on_change)
    try:
        field.suffix = ft.Icon(ft.Icons.TUNE, color=MUTED, size=18)
    except Exception:
        pass
    return field


def metric_tile(label, value_control, expand=True):
    return ft.Column(
        [ft.Text(label, size=11, color=MUTED), value_control],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=expand,
        spacing=3,
    )


def summary_bar(items, visible=True, bgcolor=PRIMARY_TINT):
    controls = []
    for idx, item in enumerate(items):
        if idx:
            controls.append(ft.VerticalDivider(width=1, color=BORDER))
        controls.append(item)
    return ft.Container(
        content=ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        bgcolor=bgcolor,
        border_radius=RADIUS_CARD,
        border=_full_border(BORDER),
        padding=16,
        margin=ft.Margin(left=8, right=8, top=0, bottom=8),
        visible=visible,
    )


def empty_state(title, subtitle=None, icon=ft.Icons.INFO_OUTLINE, padding=50, action=None):
    controls = [
        icon_badge(icon, color=MUTED, bgcolor=PRIMARY_TINT, size=34, padding=16),
        ft.Text(title, size=17, weight=ft.FontWeight.BOLD, color=TEXT, text_align=ft.TextAlign.CENTER),
        ft.Text(subtitle or "", size=12, color=MUTED, visible=bool(subtitle), text_align=ft.TextAlign.CENTER),
    ]
    if action is not None:
        controls.append(action)
    return ft.Container(
        content=ft.Column(controls, spacing=10, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=padding,
    )


def action_text_button(label, icon, on_click, color=None, visible=True):
    color = color or PRIMARY
    return ft.TextButton(
        content=ft.Row([
            ft.Icon(icon, size=18, color=color),
            ft.Text(label, size=12, color=color, weight=ft.FontWeight.BOLD),
        ], spacing=5, tight=True),
        on_click=on_click,
        visible=visible,
        height=TOUCH_TARGET,
    )


def data_card(content, padding=15, elevation=2, margin=None, on_click=None):
    container_kwargs = {
        "content": content,
        "padding": padding,
        "bgcolor": CARD_BG,
        "border_radius": RADIUS_CARD,
        "border": _full_border(BORDER),
    }
    if on_click is not None:
        container_kwargs["on_click"] = on_click
        container_kwargs["ink"] = True
    container = ft.Container(**container_kwargs)
    if elevation and elevation > 0:
        return ft.Card(
            content=container,
            elevation=1,
            margin=margin or ft.Margin(left=8, right=8, top=4, bottom=4),
        )
    container.margin = margin or ft.Margin(left=8, right=8, top=4, bottom=4)
    return container


def pill(text, color=PRIMARY, bgcolor=None, icon=None, size=12, padding=None):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=14, color=color))
    controls.append(ft.Text(str(text), size=size, weight=ft.FontWeight.BOLD, color=color))
    return ft.Container(
        content=ft.Row(controls, spacing=4, tight=True),
        bgcolor=bgcolor or PRIMARY_SOFT,
        border_radius=999,
        padding=padding or ft.Padding(left=10, right=10, top=5, bottom=5),
    )


def amount_pill(text, color, light_bg=None):
    return pill(text, color=ft.Colors.WHITE, bgcolor=light_bg or color, size=12, padding=ft.Padding(left=12, right=12, top=6, bottom=6))


def stat_card(title, value, color=PRIMARY, icon=None, subtitle=None):
    return metric_card(title, value, color=color, icon=icon, subtitle=subtitle)


def section_label(text, icon=None):
    return section_title(text, icon=icon)


def key_value_tile(label, value, color=None, expand=True):
    raw = str(value)
    if '$' in raw or '€' in raw or 'SYP' in raw or 'USD' in raw:
        raw = '\u2066' + raw + '\u2069'
    return ft.Column([
        ft.Text(label, size=11, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ft.Text(raw, size=13, color=color or TEXT, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=expand, spacing=3)


def responsive_wrap(controls, spacing=10, run_spacing=10):
    """Wrap controls for narrow APK screens without horizontal overflow."""
    return ft.Row(controls=list(controls), spacing=spacing, run_spacing=run_spacing, wrap=True, alignment=ft.MainAxisAlignment.START)


def set_control_busy(control, busy=True, label=None):
    if control is None:
        return None
    try:
        control.disabled = bool(busy)
        if label is not None and hasattr(control, "text"):
            control.text = label
    except Exception:
        pass
    return control


def info_banner(message, icon=ft.Icons.INFO_OUTLINE, color=PRIMARY, bgcolor=PRIMARY_SOFT):
    return ft.Container(
        content=ft.Row([ft.Icon(icon, color=color, size=19), ft.Text(str(message), size=12, color=TEXT, expand=True)]),
        bgcolor=bgcolor,
        border_radius=RADIUS_CARD,
        border=_full_border(BORDER),
        padding=12,
        margin=ft.Margin(left=8, right=8, top=4, bottom=4),
    )


def financial_color(value: float) -> str:
    try:
        return SUCCESS if float(value) >= 0 else DANGER
    except Exception:
        return TEXT


def money_text(value, color=None, size=18, weight=None, align=None):
    """Keep currency and amount visually together in RTL layouts."""
    return ft.Text(
        str(value),
        size=size,
        weight=weight or ft.FontWeight.BOLD,
        color=color or TEXT,
        text_align=align,
        no_wrap=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def primary_button(label, icon=None, on_click=None, width=None):
    return primary_action(label, icon=icon, on_click=on_click, width=width)


def secondary_button(label, icon=None, on_click=None, width=None):
    return secondary_action(label, icon=icon, on_click=on_click, width=width)


def danger_button(label, icon=None, on_click=None, width=None):
    return danger_action(label, icon=icon, on_click=on_click, width=width)


def modern_action_button(label, icon, on_click=None, color=None, bgcolor=None):
    color = color or PRIMARY
    bgcolor = bgcolor or PRIMARY_SOFT
    return ft.Container(
        content=ft.TextButton(
            content=ft.Row([ft.Icon(icon, size=18, color=color), ft.Text(label, size=12, color=color, weight=ft.FontWeight.BOLD)], tight=True, spacing=5),
            on_click=on_click,
            height=TOUCH_TARGET,
        ),
        bgcolor=bgcolor,
        border_radius=RADIUS_FIELD,
        border=_full_border(BORDER),
        padding=0,
    )


def modern_field(label, *, value=None, hint_text=None, icon=None, password=False, can_reveal_password=False, on_change=None, on_submit=None, read_only=False, expand=False, width=None, suffix=None, keyboard_type=None):
    return modern_text_field(
        label=label, value=value, hint_text=hint_text, icon=icon,
        password=password, can_reveal_password=can_reveal_password,
        on_change=on_change, on_submit=on_submit, read_only=read_only,
        expand=expand, width=width, suffix=suffix, keyboard_type=keyboard_type,
    )


def operation_menu_button(on_click, tooltip="إجراءات"):
    return ft.IconButton(
        icon=ft.Icons.MORE_VERT, tooltip=tooltip, on_click=on_click,
        icon_color=MUTED, width=TOUCH_TARGET, height=TOUCH_TARGET,
    )


def modern_section_card(title, controls, *, icon=None, action=None, padding=16):
    return data_card(
        ft.Column([
            section_label(title, icon),
            ft.Divider(height=1, color=BORDER),
            *list(controls),
        ], spacing=12),
        padding=padding,
        elevation=0,
    )
