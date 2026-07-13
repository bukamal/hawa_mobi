# -*- coding: utf-8 -*-
"""Small UI helpers shared by mobile views.

The module is intentionally dependency-light and contains no database/network logic.
It is safe for APK builds and keeps visual behavior consistent across screens.
"""

from __future__ import annotations

import flet as ft
from views.flet_compat import (
    ALIGN_CENTER,
    ALIGN_TOP_LEFT,
    ALIGN_BOTTOM_RIGHT,
    show_snackbar as compat_show_snackbar,
)

# Windows-compatible Hawaa brand tokens.  Keep these centralized so Android
# does not drift visually from the desktop product.
PRIMARY = "#118276"
PRIMARY_DARK = "#0B5F57"
PRIMARY_SOFT = "#E7F5F2"
ACCENT = "#F5B51B"
ACCENT_DARK = "#D77A00"
PAGE_BG = "#F6FAF9"
CARD_BG = ft.Colors.WHITE
MUTED = "#64748B"
TEXT = "#102033"
BORDER = "#DCE7E5"
DANGER = "#D64545"
SUCCESS = "#12805C"
WARNING = "#B7791F"

ASSET_APP_SYMBOL = "/app_logo.png"
ASSET_APP_WORDMARK = "/brand/app_wordmark.png"
ASSET_APP_ICON = "/icon_android.png"


def image_fit(name: str) -> str:
    """Return an image fit value compatible across Flet versions.

    Some APK builds use a Flet runtime that does not expose the Flet image-fit enum.
    Flet's Image control accepts the lower-case string values used by Flutter
    BoxFit, so keeping this helper string-based prevents startup crashes such as
    the Android startup image-fit enum crash on Android.
    """
    normalized = str(name or "contain").strip().lower()
    allowed = {
        "contain",
        "cover",
        "fill",
        "fit_width",
        "fit_height",
        "none",
        "scale_down",
    }
    return normalized if normalized in allowed else "contain"


def app_mark(size=86, color=PRIMARY, dark=False):
    """Real application mark loaded from the shared Hawaa brand assets.

    The old Android branch drew an H + airplane at runtime.  That made the APK
    look like a different product than Windows.  This helper now uses the same
    accounting/ledger symbol shipped with the desktop application.
    """
    bg = ft.Colors.WHITE if dark else "#F8FAFC"
    border_color = BORDER if dark else "#E7F5F2"
    return ft.Container(
        width=size,
        height=size,
        border_radius=max(18, size // 5),
        bgcolor=bg,
        border=ft.Border(
            left=ft.BorderSide(1, border_color),
            top=ft.BorderSide(1, border_color),
            right=ft.BorderSide(1, border_color),
            bottom=ft.BorderSide(1, border_color),
        ),
        shadow=ft.BoxShadow(blur_radius=18, spread_radius=1, color=ft.Colors.BLACK26),
        padding=max(4, size // 18),
        content=ft.Image(
            src=ASSET_APP_SYMBOL, width=size, height=size, fit=image_fit("contain")
        ),
    )


def brand_wordmark(width=260, height=92, dark=True):
    """Wordmark image used in splash/login/drawer where enough space exists."""
    return ft.Image(
        src=ASSET_APP_WORDMARK, width=width, height=height, fit=image_fit("contain")
    )


def app_brand(
    title="هوى الشام",
    subtitle="نظام الحسابات الداخلية",
    size=86,
    color=PRIMARY,
    dark=False,
    wordmark=False,
):
    text_color = ft.Colors.WHITE if not dark else TEXT
    sub_color = "#DDEDEA" if not dark else MUTED
    controls = [app_mark(size=size, color=color, dark=dark)]
    if wordmark:
        controls.append(
            brand_wordmark(
                width=max(220, int(size * 3.4)),
                height=max(70, int(size * 1.1)),
                dark=dark,
            )
        )
    else:
        controls.extend(
            [
                ft.Text(
                    title,
                    size=23 if size < 90 else 30,
                    weight=ft.FontWeight.BOLD,
                    color=text_color,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    subtitle,
                    size=12 if size < 90 else 14,
                    color=sub_color,
                    text_align=ft.TextAlign.CENTER,
                ),
            ]
        )
    return ft.Column(
        controls=controls,
        spacing=7,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )


def brand_background(content, padding=24, dark=True):
    """Reusable branded background for splash/login/activation."""
    colors = (
        ["#082040", PRIMARY_DARK, "#0E8276", ACCENT_DARK]
        if dark
        else [PAGE_BG, "#EBF7F4", "#FFF8E7"]
    )
    return ft.Container(
        expand=True,
        padding=padding,
        alignment=ALIGN_CENTER,
        gradient=ft.LinearGradient(
            begin=ALIGN_TOP_LEFT, end=ALIGN_BOTTOM_RIGHT, colors=colors
        ),
        content=content,
    )


def brand_card(content, width=420, padding=24):
    return ft.Card(
        content=ft.Container(
            content=content,
            padding=padding,
            width=width,
            bgcolor=ft.Colors.WHITE,
            border_radius=24,
        ),
        elevation=8,
    )


def status_chip(text, icon=None, color=PRIMARY, bgcolor=PRIMARY_SOFT):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=15, color=color))
    controls.append(ft.Text(str(text), size=11, color=color, weight=ft.FontWeight.BOLD))
    return ft.Container(
        content=ft.Row(
            controls, spacing=5, tight=True, alignment=ft.MainAxisAlignment.CENTER
        ),
        bgcolor=bgcolor,
        border_radius=999,
        border=ft.Border(
            left=ft.BorderSide(1, color),
            top=ft.BorderSide(1, color),
            right=ft.BorderSide(1, color),
            bottom=ft.BorderSide(1, color),
        ),
        padding=ft.Padding(left=10, right=10, top=5, bottom=5),
    )


def show_snackbar(page, message, is_error=False, duration=3000):
    return compat_show_snackbar(page, message, is_error=is_error, duration=duration)


def page_header(title, icon=None, trailing=None, subtitle=None):
    title_row = ft.Row(
        controls=[
            ft.Icon(icon, color=PRIMARY, size=24)
            if icon
            else ft.Container(width=0, height=0),
            ft.Column(
                controls=[
                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(subtitle, size=12, color=MUTED, visible=bool(subtitle)),
                ],
                spacing=2,
                expand=True,
            ),
            trailing if trailing is not None else ft.Container(width=0, height=0),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Container(
        content=title_row, padding=ft.Padding(left=10, right=10, top=10, bottom=6)
    )


def search_field(label, on_change):
    return ft.TextField(
        label=label,
        prefix_icon=ft.Icons.SEARCH,
        on_change=on_change,
        border_radius=30,
        filled=True,
        bgcolor=CARD_BG,
        text_size=14,
    )


def metric_tile(label, value_control, expand=True):
    return ft.Column(
        [ft.Text(label, size=11, color=MUTED), value_control],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=expand,
    )


def summary_bar(items, visible=True, bgcolor=PRIMARY_SOFT):
    controls = []
    for idx, item in enumerate(items):
        if idx:
            controls.append(ft.VerticalDivider(width=1, color=BORDER))
        controls.append(item)
    return ft.Container(
        content=ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        bgcolor=bgcolor,
        border_radius=15,
        padding=15,
        margin=ft.Margin(left=10, right=10, top=0, bottom=10),
        visible=visible,
    )


def empty_state(title, subtitle=None, icon=ft.Icons.INFO_OUTLINE, padding=50):
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(icon, size=64, color=ft.Colors.GREY_400),
                ft.Text(title, size=16, color=MUTED),
                ft.Text(
                    subtitle or "",
                    size=12,
                    color=ft.Colors.GREY_400,
                    visible=bool(subtitle),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=padding,
    )


def action_text_button(label, icon, on_click, color=None, visible=True):
    return ft.TextButton(
        content=ft.Row(
            [
                ft.Icon(icon, size=18 if label != "حذف" else 16, color=color),
                ft.Text(label, size=12 if label != "حذف" else 11, color=color),
            ]
        ),
        on_click=on_click,
        visible=visible,
    )


def data_card(content, padding=15, elevation=2, margin=None):
    return ft.Card(
        content=ft.Container(content=content, padding=padding, bgcolor=CARD_BG),
        elevation=elevation,
        margin=margin or ft.Margin(left=10, right=10, top=5, bottom=5),
    )


def pill(text, color=PRIMARY, bgcolor=None, icon=None, size=12, padding=None):
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=14, color=color))
    controls.append(
        ft.Text(str(text), size=size, weight=ft.FontWeight.BOLD, color=color)
    )
    return ft.Container(
        content=ft.Row(controls, spacing=4, tight=True),
        bgcolor=bgcolor or PRIMARY_SOFT,
        border_radius=20,
        padding=padding or ft.Padding(left=10, right=10, top=5, bottom=5),
    )


def amount_pill(text, color, light_bg=None):
    return pill(
        text,
        color=ft.Colors.WHITE,
        bgcolor=light_bg or color,
        size=12,
        padding=ft.Padding(left=12, right=12, top=6, bottom=6),
    )


def stat_card(title, value, color=PRIMARY, icon=None, subtitle=None):
    return data_card(
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(title, size=11, color=MUTED),
                        ft.Text(
                            str(value),
                            size=17,
                            weight=ft.FontWeight.BOLD,
                            color=color,
                            max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            subtitle or "",
                            size=11,
                            color=ft.Colors.GREY_500,
                            visible=bool(subtitle),
                        ),
                    ],
                    expand=True,
                    spacing=3,
                ),
                ft.Container(
                    content=ft.Icon(icon or ft.Icons.INSIGHTS, color=color, size=24),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=14,
                    padding=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=14,
        elevation=1,
        margin=ft.Margin(left=10, right=10, top=3, bottom=3),
    )


def section_label(text, icon=None):
    return ft.Row(
        [
            ft.Icon(icon, size=16, color=PRIMARY)
            if icon
            else ft.Container(width=0, height=0),
            ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
        ],
        spacing=6,
    )


def key_value_tile(label, value, color=None, expand=True):
    return ft.Column(
        [
            ft.Text(label, size=11, color=MUTED),
            ft.Text(
                str(value),
                size=13,
                color=color,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=expand,
        spacing=2,
    )


def responsive_wrap(controls, spacing=10, run_spacing=10):
    """Wrap controls for narrow APK screens without horizontal overflow."""
    return ft.Row(
        controls=list(controls),
        spacing=spacing,
        run_spacing=run_spacing,
        wrap=True,
        alignment=ft.MainAxisAlignment.START,
    )


def set_control_busy(control, busy=True, label=None):
    """Disable a button/control while an action is running. Returns the control."""
    if control is None:
        return None
    try:
        control.disabled = bool(busy)
        if label is not None and hasattr(control, "text"):
            control.text = label
    except Exception:
        pass
    return control


def info_banner(
    message, icon=ft.Icons.INFO_OUTLINE, color=PRIMARY, bgcolor=PRIMARY_SOFT
):
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=color, size=18),
                ft.Text(str(message), size=12, color=ft.Colors.GREY_700, expand=True),
            ]
        ),
        bgcolor=bgcolor,
        border_radius=12,
        padding=12,
        margin=ft.Margin(left=10, right=10, top=4, bottom=4),
    )
