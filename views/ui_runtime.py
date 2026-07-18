# -*- coding: utf-8 -*-
"""Runtime UI helpers for navigation, loading, connection and screen states."""
from __future__ import annotations

import flet as ft

from i18n.translator import translate
from views import ui_kit
from views.flet_compat import ALIGN_CENTER


def safe_update(page) -> None:
    try:
        if page is not None:
            page.update()
    except Exception as exc:
        print(f"[WARN] page.update failed: {exc}")


def loading_view(message: str | None = None):
    message = message or translate("loading")
    # A compact skeleton communicates page structure better than a spinner alone
    # and remains compatible with Flet 0.28 Android.
    skeletons = [
        ft.Container(height=14, width=220, bgcolor="#E2E8F0", border_radius=7),
        ft.Container(height=74, width=310, bgcolor="#EEF2F6", border_radius=14),
        ft.Container(height=74, width=310, bgcolor="#EEF2F6", border_radius=14),
    ]
    return ft.Container(
        content=ft.Column(
            [
                ft.ProgressRing(width=28, height=28),
                ft.Text(message, size=14, color=ui_kit.MUTED, text_align=ft.TextAlign.CENTER),
                *skeletons,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=30,
    )


def empty_view(title: str, subtitle: str = "", *, icon=ft.Icons.INBOX_OUTLINED, action=None):
    return ui_kit.empty_state(title, subtitle, icon=icon, action=action)


def error_view(message: str, on_retry=None, *, technical_details: str | None = None):
    details = ft.Text(
        str(technical_details or ""), size=11, color=ui_kit.MUTED,
        selectable=True, visible=bool(technical_details), rtl=False,
        text_align=ft.TextAlign.LEFT,
    )
    controls = [
        ft.Container(
            content=ft.Icon(ft.Icons.ERROR_OUTLINE, color=ui_kit.DANGER, size=38),
            bgcolor=ui_kit.DANGER_SOFT,
            border_radius=18,
            padding=16,
        ),
        ft.Text(translate("screen_load_failed"), size=18, weight=ft.FontWeight.BOLD, color=ui_kit.TEXT),
        ft.Text(str(message), size=13, color=ui_kit.MUTED, text_align=ft.TextAlign.CENTER),
        details,
    ]
    if on_retry:
        controls.append(
            ft.FilledButton(
                translate("retry"), icon=ft.Icons.REFRESH,
                on_click=on_retry, height=48, bgcolor=ui_kit.PRIMARY,
                color=ft.Colors.WHITE,
            )
        )
    return ft.Container(
        content=ft.Column(
            controls,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ALIGN_CENTER,
        expand=True,
        padding=30,
    )


def offline_banner(message: str | None = None, on_retry=None):
    actions = []
    if on_retry:
        actions.append(
            ft.TextButton(
                translate("retry"), icon=ft.Icons.REFRESH,
                on_click=on_retry, height=44,
            )
        )
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.WIFI_OFF, color="#B45309", size=20),
            ft.Text(
                message or translate("server_unavailable"),
                size=12, color=ui_kit.TEXT, expand=True,
            ),
            *actions,
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=ui_kit.WARNING_SOFT,
        border=ft.Border(
            left=ft.BorderSide(1, ui_kit.WARNING), top=ft.BorderSide(1, ui_kit.WARNING),
            right=ft.BorderSide(1, ui_kit.WARNING), bottom=ft.BorderSide(1, ui_kit.WARNING),
        ),
        border_radius=12,
        padding=10,
    )


def network_status_chip():
    try:
        from database.connection import DatabaseConnection
        db = DatabaseConnection()
        if db.is_remote():
            label = translate("network_client_short")
            subtitle = db.server_url.replace("http://", "").replace("https://", "")
            insecure = str(db.server_url or "").lower().startswith("http://")
            return ui_kit.pill(
                f"{label} • {subtitle}",
                color="#B45309" if insecure else ft.Colors.BLUE,
                bgcolor=ui_kit.WARNING_SOFT if insecure else ft.Colors.BLUE_50,
                icon=ft.Icons.GPP_MAYBE_OUTLINED if insecure else ft.Icons.LAN,
            )
        return ui_kit.pill(
            translate("local"), color=ft.Colors.GREEN,
            bgcolor=ft.Colors.GREEN_50, icon=ft.Icons.STORAGE,
        )
    except Exception:
        return ui_kit.pill(
            translate("network_unknown"), color=ft.Colors.ORANGE,
            bgcolor=ft.Colors.ORANGE_50, icon=ft.Icons.WARNING_AMBER,
        )


def make_status_bar(user_label: str = ""):
    left = ft.Row([
        ft.Icon(ft.Icons.VERIFIED_USER, size=16, color=ui_kit.PRIMARY),
        ft.Text(
            user_label or translate("active_session"), size=12,
            color=ui_kit.MUTED, overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ], spacing=5, tight=True)
    return ft.Container(
        content=ft.Row([left, network_status_chip()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=ft.Colors.WHITE,
        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        border=ft.Border(bottom=ft.BorderSide(1, ui_kit.BORDER)),
    )
