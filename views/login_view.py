# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import flet as ft
from database import UserRepository
from database.connection import DatabaseConnection, get_setting, set_setting
from auth.session import UserSession
from i18n.translator import (
    translate,
    set_language,
    language_code_from_label,
    language_label,
    is_rtl,
)
from views.ui_kit import (
    app_brand,
    brand_background,
    brand_card,
    status_chip,
    PRIMARY,
    MUTED,
    DANGER,
    SUCCESS,
)
from views.flet_compat import ALIGN_CENTER


class LoginView(ft.Container):
    MAX_ATTEMPTS = 5
    LOCK_SECONDS = 60

    def __init__(self, page, on_login_success, on_exit):
        super().__init__()
        self._page = page
        self.on_login_success = on_login_success
        self.on_exit = on_exit
        self._busy = False
        self._navigating_after_login = False
        self._failed_attempts = 0
        self._locked_until = 0.0
        self.expand = True
        self.alignment = ALIGN_CENTER
        self.padding = 0

        self.network_chip = status_chip(
            translate("local_mode"),
            icon=ft.Icons.PHONE_ANDROID,
            color=SUCCESS,
            bgcolor="#E9F7F1",
        )
        self.network_status = ft.Text(
            "", size=11, color=MUTED, text_align=ft.TextAlign.CENTER
        )
        self.username = ft.Dropdown(
            label=translate("username"),
            hint_text=translate("username"),
            options=[],
            editable=True,
            expand=True,
            border_radius=14,
        )
        self.password = ft.TextField(
            label=translate("password"),
            password=True,
            can_reveal_password=True,
            expand=True,
            border_radius=14,
        )
        self.password.on_submit = self._do_login
        self.error_msg = ft.Text(
            "", color=DANGER, size=12, text_align=ft.TextAlign.CENTER
        )
        self.login_btn = ft.FilledButton(
            content=ft.Text(translate("login"), size=16, weight=ft.FontWeight.BOLD),
            width=340,
            height=48,
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._do_login,
        )
        self.lang_dropdown = ft.Dropdown(
            label=translate("language"),
            width=130,
            value=language_label(),
            options=[
                ft.dropdown.Option("العربية"),
                ft.dropdown.Option("English"),
                ft.dropdown.Option("Français"),
            ],
            border_radius=14,
        )
        self.lang_dropdown.on_change = self._change_language
        self.remember = ft.Checkbox(
            label=translate("remember_username"),
            value=(get_setting("login/remember_username", "false") == "true"),
        )
        self.brand = app_brand(
            translate("app_name"), translate("login_subtitle"), size=92, dark=True
        )
        self.form_title = ft.Text(
            translate("login_data"), size=16, weight=ft.FontWeight.BOLD, color="#102033"
        )
        self.clear_saved_btn = ft.TextButton(
            content=ft.Text(translate("clear_saved_user"), size=12, color=PRIMARY),
            on_click=self._switch_account,
        )
        self.qr_pair_btn = ft.OutlinedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.QR_CODE_SCANNER), ft.Text("ربط مع Windows عبر QR")]
            ),
            width=340,
            on_click=self._open_qr_pairing_dialog,
        )
        self.forgot_hint = ft.Text(
            translate("forgot_password_hint"),
            size=10,
            color=MUTED,
            text_align=ft.TextAlign.CENTER,
        )

        form = ft.Column(
            controls=[
                self.brand,
                self.network_chip,
                self.network_status,
                ft.Container(height=8),
                self.form_title,
                self.username,
                self.password,
                self.error_msg,
                ft.Row(
                    [self.remember, self.lang_dropdown],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                self.login_btn,
                self.qr_pair_btn,
                self.clear_saved_btn,
                self.forgot_hint,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
        )
        self.content = brand_background(
            brand_card(form, width=430, padding=24), padding=20, dark=False
        )
        self._populate_users()
        self._update_network_status()

    def _open_qr_pairing_dialog(self, e):
        from views.dialogs.qr_pairing_dialog import open_qr_pairing_dialog

        def on_success(result):
            self._update_network_status()
            self._populate_users()
            self.error_msg.value = "تم الربط. سجّل الدخول بحساب Windows Server."
            self.error_msg.color = SUCCESS
            self._page.update()

        return open_qr_pairing_dialog(self._page, on_success=on_success)

    def _update_network_status(self):
        db = DatabaseConnection()
        if db.is_remote():
            self.network_chip.content.controls[-1].value = translate("network_client")
            self.network_status.value = db.server_url or "لم يتم تحديد عنوان الخادم"
            self.network_status.color = PRIMARY
        else:
            self.network_chip.content.controls[-1].value = translate("local_mode")
            self.network_status.value = translate("local_database")
            self.network_status.color = SUCCESS

    def _populate_users(self):
        db = DatabaseConnection()
        remembered = (
            get_setting("login/last_username", "") if self.remember.value else ""
        )
        if db.is_remote():
            self.username.options = [ft.dropdown.Option(remembered or "")]
            self.username.value = remembered or ""
        else:
            try:
                users = UserRepository().get_all()
                self.username.options = [
                    ft.dropdown.Option(u["username"]) for u in users
                ]
                if remembered:
                    self.username.value = remembered
            except Exception:
                self.username.options = []

    def _apply_language_texts(self):
        self._page.rtl = is_rtl()
        self._page.title = translate("app_title")
        self.username.label = translate("username")
        self.username.hint_text = translate("username")
        self.password.label = translate("password")
        self.login_btn.content.value = translate("login")
        self.lang_dropdown.label = translate("language")
        self.lang_dropdown.value = language_label()
        self.remember.label = translate("remember_username")
        self.form_title.value = translate("login_data")
        self.clear_saved_btn.content.value = translate("clear_saved_user")
        self.forgot_hint.value = translate("forgot_password_hint")
        try:
            self.brand.controls[1].value = translate("app_name")
            self.brand.controls[2].value = translate("login_subtitle")
        except Exception:
            pass
        self._update_network_status()

    def _change_language(self, e):
        new_lang = language_code_from_label(self.lang_dropdown.value)
        set_language(new_lang)
        set_setting("language", new_lang)
        self._apply_language_texts()
        self._page.update()

    def _switch_account(self, e):
        self.username.value = ""
        self.password.value = ""
        self.remember.value = False
        set_setting("login/remember_username", "false")
        set_setting("login/last_username", "")
        self.error_msg.value = "تم مسح اسم المستخدم المحفوظ"
        self.error_msg.color = SUCCESS
        self._populate_users()
        self._page.update()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.login_btn.disabled = busy
        try:
            self.login_btn.content.value = (
                "جاري الدخول..." if busy else translate("login")
            )
        except Exception:
            pass
        self.username.disabled = busy
        self.password.disabled = busy

    def _locked_message(self) -> str | None:
        remaining = int(self._locked_until - time.time())
        if remaining > 0:
            return f"تم قفل تسجيل الدخول مؤقتاً. حاول بعد {remaining} ثانية."
        return None

    def _record_failure(self):
        self._failed_attempts += 1
        if self._failed_attempts >= self.MAX_ATTEMPTS:
            self._locked_until = time.time() + self.LOCK_SECONDS
            self._failed_attempts = 0

    def _do_login(self, e):
        if self._busy:
            return
        locked = self._locked_message()
        if locked:
            self.error_msg.value = locked
            self.error_msg.color = DANGER
            self._page.update()
            return
        username = (self.username.value or "").strip()
        password = self.password.value or ""
        if not username or not password:
            self.error_msg.value = "يرجى إدخال اسم المستخدم وكلمة المرور"
            self.error_msg.color = DANGER
            self._page.update()
            return
        self._set_busy(True)
        self.error_msg.value = "جاري التحقق..."
        self.error_msg.color = PRIMARY
        self._page.update()
        try:
            db = DatabaseConnection()
            db.refresh_mode()
            if db.is_remote():
                rest = db.get_rest_client()
                if rest is None:
                    raise RuntimeError(
                        "وضع عميل الشبكة مفعل لكن عميل الاتصال غير مهيأ. تحقق من عنوان الخادم في الإعدادات."
                    )
                user = rest.login(username, password)
            else:
                user = UserRepository().authenticate(username, password)
            if not user:
                self._record_failure()
                self.error_msg.value = "اسم المستخدم أو كلمة المرور غير صحيحة"
                self.error_msg.color = DANGER
                self.password.value = ""
                return
            UserSession.login(user)
            set_setting(
                "login/remember_username", "true" if self.remember.value else "false"
            )
            set_setting("login/last_username", username if self.remember.value else "")
            self.error_msg.value = "تم تسجيل الدخول. جارٍ فتح الواجهة..."
            self.error_msg.color = SUCCESS
            self._navigating_after_login = True
            self.on_login_success(user)
        except Exception as exc:
            self._navigating_after_login = False
            self._record_failure()
            self.error_msg.value = f"فشل تسجيل الدخول: {exc}"
            self.error_msg.color = DANGER
            self.password.value = ""
        finally:
            if not self._navigating_after_login:
                self._set_busy(False)
                try:
                    self._page.update()
                except Exception:
                    pass
