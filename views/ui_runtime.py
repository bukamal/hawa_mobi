# -*- coding: utf-8 -*-
"""Runtime UI helpers for navigation, loading and connection status.

No database writes happen here.  Helpers are defensive because they are used by
APK/mobile views where a failed update must not crash the whole page.
"""

from __future__ import annotations

import flet as ft

from views import ui_kit
from views.flet_compat import ALIGN_CENTER


def safe_update(page) -> None:
    try:
        if page is not None:
            page.update()
    except Exception as exc:
        print(f"[WARN] page.update failed: {exc}")


def loading_view(message: str = "جاري التحميل..."):
    return ft.Container(
        content=ft.Column(
            [
                ft.ProgressRing(width=26, height=26),
                ft.Text(message, size=13, color=ui_kit.MUTED),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=30,
    )


def error_view(message: str, on_retry=None):
    controls = [
        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=52),
        ft.Text("تعذر تحميل الشاشة", size=16, weight=ft.FontWeight.BOLD),
        ft.Text(
            str(message), size=12, color=ui_kit.MUTED, text_align=ft.TextAlign.CENTER
        ),
    ]
    if on_retry:
        controls.append(
            ft.FilledButton("إعادة المحاولة", icon=ft.Icons.REFRESH, on_click=on_retry)
        )
    return ft.Container(
        content=ft.Column(
            controls,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=30,
    )


def network_status_chip():
    try:
        from database.connection import DatabaseConnection

        db = DatabaseConnection()
        if db.is_remote():
            label = "عميل شبكة"
            subtitle = db.server_url.replace("http://", "").replace("https://", "")
            return ui_kit.pill(
                f"{label} • {subtitle}",
                color=ft.Colors.BLUE,
                bgcolor=ft.Colors.BLUE_50,
                icon=ft.Icons.LAN,
            )
        return ui_kit.pill(
            "محلي",
            color=ft.Colors.GREEN,
            bgcolor=ft.Colors.GREEN_50,
            icon=ft.Icons.STORAGE,
        )
    except Exception:
        return ui_kit.pill(
            "حالة الشبكة غير معروفة",
            color=ft.Colors.ORANGE,
            bgcolor=ft.Colors.ORANGE_50,
            icon=ft.Icons.WARNING_AMBER,
        )


def make_status_bar(user_label: str = ""):
    left = ft.Row(
        [
            ft.Icon(ft.Icons.VERIFIED_USER, size=16, color=ui_kit.PRIMARY),
            ft.Text(
                user_label or "جلسة نشطة",
                size=12,
                color=ui_kit.MUTED,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
        spacing=5,
        tight=True,
    )
    return ft.Container(
        content=ft.Row(
            [left, network_status_chip()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        bgcolor=ft.Colors.WHITE,
        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        border=ft.Border(bottom=ft.BorderSide(1, ui_kit.BORDER)),
    )
