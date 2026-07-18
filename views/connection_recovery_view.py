# -*- coding: utf-8 -*-
"""Pre-login recovery screen for an unavailable Windows server.

The former startup flow stopped at a generic fatal error when the saved server
IP changed or Windows was offline.  This screen keeps the user inside the app,
lets them test/save a new endpoint, re-pair by QR, or deliberately switch to the
local database after authenticating a *local administrator*.
"""
from __future__ import annotations

import asyncio
import sqlite3
from urllib.parse import urlparse

import flet as ft

from auth.password import verify_password
from database.connection import DatabaseConnection, get_local_db_path
from i18n.translator import translate
from services.network_service import NetworkService
from views.dialogs.qr_pairing_dialog import open_qr_pairing_dialog
from views.flet_compat import ALIGN_CENTER, run_async_task, show_snackbar
from views.ui_kit import (
    PRIMARY, PRIMARY_SOFT, TEXT, MUTED, BORDER, DANGER, DANGER_SOFT,
    app_brand, brand_background, data_card, modern_field, primary_button,
    secondary_button, danger_button, info_banner, status_chip,
)


def _local_admin_is_valid(username: str, password: str) -> bool:
    """Validate against the local SQLite user table without changing app mode."""
    username = (username or "").strip()
    if not username or not password:
        return False
    conn = sqlite3.connect(get_local_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT username, password_hash, salt, role FROM users WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
        if not row or str(row["role"] or "") != "admin":
            return False
        return bool(verify_password(password, row["password_hash"], row["salt"]))
    except Exception:
        return False
    finally:
        conn.close()


class ConnectionRecoveryView(ft.Container):
    def __init__(self, page, error_message: str, on_retry, on_close=None):
        super().__init__()
        self._page = page
        self._error_message = str(error_message or translate("server_unavailable"))
        self._on_retry = on_retry
        self._on_close = on_close
        self.expand = True
        self.alignment = ALIGN_CENTER

        try:
            saved_url = DatabaseConnection().server_url or ""
        except Exception:
            saved_url = ""

        self.server_field = modern_field(
            translate("server_address"),
            value=saved_url,
            hint_text=translate("server_address_hint"),
            icon=ft.Icons.DNS_OUTLINED,
            on_submit=self._test_and_save,
        )
        try:
            self.server_field.rtl = False
            self.server_field.text_align = ft.TextAlign.LEFT
        except Exception:
            pass

        self.status = ft.Text(
            translate("server_unavailable"),
            size=13,
            color=DANGER,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self.test_button = primary_button(
            translate("test_and_save"), ft.Icons.CLOUD_SYNC_OUTLINED,
            self._test_and_save,
        )
        self.retry_button = secondary_button(
            translate("retry"), ft.Icons.REFRESH, self._retry,
        )
        self.qr_button = secondary_button(
            translate("pair_with_qr"), ft.Icons.QR_CODE_SCANNER, self._open_qr,
        )

        self.local_panel = ft.Container(visible=False)
        self.local_user = modern_field(
            translate("local_admin_username"), icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
        )
        self.local_password = modern_field(
            translate("local_admin_password"), icon=ft.Icons.PASSWORD,
            password=True, can_reveal_password=True, on_submit=self._activate_local,
        )
        self.local_button = danger_button(
            translate("activate_local_mode"), ft.Icons.STORAGE_OUTLINED,
            self._activate_local,
        )
        self.local_panel.content = data_card(
            ft.Column([
                info_banner(
                    translate("local_fallback_hint"),
                    icon=ft.Icons.SECURITY_OUTLINED,
                    color=DANGER,
                    bgcolor=DANGER_SOFT,
                ),
                self.local_user,
                self.local_password,
                self.local_button,
            ], spacing=12),
            elevation=0,
        )

        self.technical_box = ft.Container(
            visible=False,
            bgcolor="#F8FAFC",
            border=ft.Border(
                left=ft.BorderSide(1, BORDER), top=ft.BorderSide(1, BORDER),
                right=ft.BorderSide(1, BORDER), bottom=ft.BorderSide(1, BORDER),
            ),
            border_radius=12,
            padding=12,
            content=ft.Text(
                self._technical_text(saved_url),
                size=11,
                color=MUTED,
                selectable=True,
                rtl=False,
                text_align=ft.TextAlign.LEFT,
            ),
        )
        self.technical_toggle = ft.TextButton(
            translate("open_technical_details"),
            icon=ft.Icons.TERMINAL,
            on_click=self._toggle_technical,
            height=48,
        )
        self.local_toggle = ft.TextButton(
            translate("local_fallback"),
            icon=ft.Icons.SWAP_HORIZ,
            on_click=self._toggle_local,
            height=48,
        )

        card_width = 520
        try:
            page_width = float(getattr(page, "width", 0) or 0)
            if page_width:
                card_width = max(300, min(520, page_width - 32))
        except Exception:
            pass

        content = ft.Container(
            width=card_width,
            padding=20,
            bgcolor="#FFFFFF",
            border_radius=22,
            border=ft.Border(
                left=ft.BorderSide(1, BORDER), top=ft.BorderSide(1, BORDER),
                right=ft.BorderSide(1, BORDER), bottom=ft.BorderSide(1, BORDER),
            ),
            content=ft.Column([
                app_brand(translate("app_name"), translate("app_subtitle"), size=76, dark=True),
                status_chip(translate("connection_recovery"), icon=ft.Icons.WIFI_OFF, color=DANGER, bgcolor=DANGER_SOFT),
                ft.Text(
                    translate("connection_recovery_subtitle"),
                    size=13, color=MUTED, text_align=ft.TextAlign.CENTER,
                ),
                self.status,
                self.server_field,
                info_banner(
                    translate("network_security_warning"),
                    icon=ft.Icons.SHIELD_OUTLINED,
                    color="#B45309", bgcolor="#FFF7E3",
                ),
                ft.Row([self.test_button, self.retry_button], wrap=True, spacing=10, run_spacing=10),
                self.qr_button,
                ft.Divider(height=1, color=BORDER),
                ft.Row([self.technical_toggle, self.local_toggle], wrap=True, spacing=8, run_spacing=8),
                self.technical_box,
                self.local_panel,
                ft.TextButton(
                    translate("close"), icon=ft.Icons.CLOSE,
                    on_click=lambda e: self._on_close() if callable(self._on_close) else None,
                    visible=callable(self._on_close), height=48,
                ),
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, scroll=ft.ScrollMode.AUTO),
        )
        self.content = brand_background(content, padding=16, dark=True)

    def _technical_text(self, server_url: str) -> str:
        scheme = ""
        host = ""
        try:
            parsed = urlparse(server_url or "")
            scheme = parsed.scheme
            host = parsed.netloc
        except Exception:
            pass
        return (
            f"URL: {server_url or '—'}\n"
            f"Scheme: {scheme or '—'}\n"
            f"Host: {host or '—'}\n\n"
            f"{translate('startup_error')}:\n{self._error_message}"
        )

    def _update(self):
        try:
            self._page.update()
        except Exception:
            pass

    def _set_busy(self, busy: bool, message: str = ""):
        for control in (self.test_button, self.retry_button, self.qr_button, self.local_button):
            try:
                control.disabled = bool(busy)
            except Exception:
                pass
        if message:
            self.status.value = message
            self.status.color = PRIMARY if busy else TEXT
        self._update()

    def _retry(self, e=None):
        if callable(self._on_retry):
            self._on_retry()

    def _toggle_technical(self, e=None):
        self.technical_box.visible = not bool(self.technical_box.visible)
        self.technical_toggle.text = translate(
            "hide_technical_details" if self.technical_box.visible else "open_technical_details"
        )
        self._update()

    def _toggle_local(self, e=None):
        self.local_panel.visible = not bool(self.local_panel.visible)
        self._update()

    def _open_qr(self, e=None):
        open_qr_pairing_dialog(
            self._page,
            on_success=lambda result: self._retry(),
        )

    def _test_and_save(self, e=None):
        url = (self.server_field.value or "").strip()

        async def _task():
            self._set_busy(True, translate("testing_connection"))
            try:
                result = await asyncio.to_thread(NetworkService.check_connection, url)
                if not result.ok:
                    self.status.value = result.message
                    self.status.color = DANGER
                    return
                await asyncio.to_thread(NetworkService.save_mode, "client", result.server_url)
                self.status.value = translate("connection_saved")
                self.status.color = "#15803D"
                show_snackbar(self._page, translate("connection_saved"), is_error=False)
                await asyncio.sleep(0.15)
                self._retry()
            except Exception as exc:
                self.status.value = str(exc)
                self.status.color = DANGER
            finally:
                self._set_busy(False)

        run_async_task(self._page, _task)

    def _activate_local(self, e=None):
        username = self.local_user.value or ""
        password = self.local_password.value or ""

        async def _task():
            self._set_busy(True, translate("checking_local_admin"))
            try:
                valid = await asyncio.to_thread(_local_admin_is_valid, username, password)
                if not valid:
                    self.status.value = translate("invalid_local_admin")
                    self.status.color = DANGER
                    return
                await asyncio.to_thread(NetworkService.save_mode, "local", "")
                self.status.value = translate("local_mode_enabled")
                self.status.color = "#15803D"
                self.local_password.value = ""
                show_snackbar(self._page, translate("local_mode_enabled"), is_error=False)
                await asyncio.sleep(0.15)
                self._retry()
            except Exception as exc:
                self.status.value = str(exc)
                self.status.color = DANGER
            finally:
                self._set_busy(False)

        run_async_task(self._page, _task)
