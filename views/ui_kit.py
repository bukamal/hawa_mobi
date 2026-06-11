# -*- coding: utf-8 -*-
"""Small UI helpers shared by mobile views.

The module is intentionally dependency-light and contains no database/network logic.
It is safe for APK builds and keeps visual behavior consistent across screens.
"""
import flet as ft

PRIMARY = ft.Colors.INDIGO
PAGE_BG = ft.Colors.GREY_50
CARD_BG = ft.Colors.WHITE
MUTED = ft.Colors.GREY_600


def show_snackbar(page, message, is_error=False, duration=3000):
    snack = ft.SnackBar(
        content=ft.Text(str(message), size=13),
        bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN,
        duration=duration,
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()
    return snack


def page_header(title, icon=None, trailing=None, subtitle=None):
    title_row = ft.Row(
        controls=[
            ft.Icon(icon, color=PRIMARY, size=24) if icon else ft.Container(width=0, height=0),
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
    return ft.Container(content=title_row, padding=ft.Padding(left=10, right=10, top=10, bottom=6))


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


def summary_bar(items, visible=True, bgcolor=ft.Colors.INDIGO_50):
    controls = []
    for idx, item in enumerate(items):
        if idx:
            controls.append(ft.VerticalDivider(width=1, color=ft.Colors.GREY_300))
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
                ft.Text(subtitle or "", size=12, color=ft.Colors.GREY_400, visible=bool(subtitle)),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
        padding=padding,
    )


def action_text_button(label, icon, on_click, color=None, visible=True):
    return ft.TextButton(
        content=ft.Row([
            ft.Icon(icon, size=18 if label != "حذف" else 16, color=color),
            ft.Text(label, size=12 if label != "حذف" else 11, color=color),
        ]),
        on_click=on_click,
        visible=visible,
    )


def data_card(content, padding=15, elevation=2, margin=None):
    return ft.Card(
        content=ft.Container(content=content, padding=padding, bgcolor=CARD_BG),
        elevation=elevation,
        margin=margin or ft.Margin(left=10, right=10, top=5, bottom=5),
    )
