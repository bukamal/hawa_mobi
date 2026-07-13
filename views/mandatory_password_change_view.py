# -*- coding: utf-8 -*-
"""Mandatory first-login password change screen for Android/Flet.

This view intentionally avoids AlertDialog.  Android/Flet 0.28.x can leave a
blank modal surface behind dialog routes; the first-login password change is a
navigation state, not an optional popup.  Cancel must log the user out and
return to Login.
"""

from __future__ import annotations

import flet as ft

from auth.session import UserSession
from auth.password_policy import evaluate_password
from database import UserRepository
from i18n.translator import translate
from views.ui_kit import (
    app_brand,
    brand_background,
    brand_card,
    PRIMARY,
    MUTED,
    DANGER,
    SUCCESS,
)
from views.flet_compat import ALIGN_CENTER
from views.dialogs.dialog_kit import normalize_text


class MandatoryPasswordChangeView(ft.Container):
    def __init__(self, page, on_save, on_cancel):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.on_cancel = on_cancel
        current = UserSession.get_current() or {}
        self.user_id = current.get("id")
        self.username = current.get("username", "")
        self._saving = False

        page_width = page.width or 420
        field_width = min(340, max(260, page_width - 80))

        self.old_password = ft.TextField(
            label=translate("old_password"),
            password=True,
            can_reveal_password=True,
            width=field_width,
            border_radius=14,
        )
        self.new_password = ft.TextField(
            label=translate("new_password"),
            password=True,
            can_reveal_password=True,
            width=field_width,
            border_radius=14,
        )
        self.confirm_password = ft.TextField(
            label=translate("confirm_password"),
            password=True,
            can_reveal_password=True,
            width=field_width,
            border_radius=14,
        )
        self.status = ft.Text(
            "يجب تغيير كلمة المرور الافتراضية قبل الدخول إلى التطبيق.",
            size=12,
            color=MUTED,
            text_align=ft.TextAlign.CENTER,
        )
        self.strength_text = ft.Text(
            "", size=11, color=MUTED, text_align=ft.TextAlign.CENTER
        )
        self.match_text = ft.Text(
            "", size=11, color=MUTED, text_align=ft.TextAlign.CENTER
        )
        self.new_password.on_change = self._validate_live
        self.confirm_password.on_change = self._validate_live

        self.save_btn = ft.FilledButton(
            content=ft.Text(
                "حفظ كلمة المرور والمتابعة", size=15, weight=ft.FontWeight.BOLD
            ),
            width=field_width,
            height=48,
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._save,
        )
        self.cancel_btn = ft.OutlinedButton(
            content=ft.Text("إلغاء والعودة لتسجيل الدخول"),
            width=field_width,
            on_click=self._cancel,
        )

        form = ft.Column(
            controls=[
                app_brand(
                    translate("app_name"),
                    "تغيير كلمة المرور الإلزامي",
                    size=86,
                    dark=True,
                ),
                ft.Text(
                    "تغيير كلمة المرور",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color="#102033",
                ),
                ft.Text(
                    f"المستخدم: {self.username}",
                    size=12,
                    color=MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
                self.status,
                self.old_password,
                self.new_password,
                self.strength_text,
                self.confirm_password,
                self.match_text,
                self.save_btn,
                self.cancel_btn,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
        )
        self.expand = True
        self.alignment = ALIGN_CENTER
        self.padding = 0
        self.content = brand_background(
            brand_card(form, width=430, padding=24), padding=20, dark=False
        )

    def _set_status(self, message: str, is_error: bool = False):
        self.status.value = message
        self.status.color = DANGER if is_error else PRIMARY
        try:
            self._page.update()
        except Exception:
            pass

    def _validate_live(self, e=None):
        new = normalize_text(self.new_password.value)
        confirm = normalize_text(self.confirm_password.value)
        if new:
            policy = evaluate_password(new)
            self.strength_text.value = f"قوة كلمة المرور: {policy['label']}" + (
                " — ينقص: " + "، ".join(policy["problems"][:2])
                if policy["problems"]
                else ""
            )
            self.strength_text.color = SUCCESS if policy["ok"] else ft.Colors.ORANGE
        else:
            self.strength_text.value = ""
        if confirm:
            self.match_text.value = (
                "كلمتا المرور متطابقتان"
                if new == confirm
                else "كلمتا المرور غير متطابقتين"
            )
            self.match_text.color = SUCCESS if new == confirm else DANGER
        else:
            self.match_text.value = ""
        try:
            self._page.update()
        except Exception:
            pass

    def _set_busy(self, busy: bool):
        self._saving = busy
        self.old_password.disabled = busy
        self.new_password.disabled = busy
        self.confirm_password.disabled = busy
        self.save_btn.disabled = busy
        self.cancel_btn.disabled = busy
        try:
            self.save_btn.content.value = (
                "جاري الحفظ..." if busy else "حفظ كلمة المرور والمتابعة"
            )
        except Exception:
            pass

    def _cancel(self, e=None):
        if self._saving:
            return
        try:
            UserSession.logout()
        finally:
            if callable(self.on_cancel):
                self.on_cancel()

    def _save(self, e=None):
        if self._saving:
            return
        old = normalize_text(self.old_password.value)
        new = normalize_text(self.new_password.value)
        confirm = normalize_text(self.confirm_password.value)
        if not old or not new or not confirm:
            self._set_status("جميع الحقول مطلوبة", True)
            return
        policy = evaluate_password(new)
        if not policy["ok"]:
            self._set_status(
                "كلمة المرور ضعيفة: " + "، ".join(policy["problems"][:3]), True
            )
            return
        if old == new:
            self._set_status("كلمة المرور الجديدة يجب أن تختلف عن الحالية", True)
            return
        if new != confirm:
            self._set_status("كلمتا المرور غير متطابقتين", True)
            return
        self._set_busy(True)
        self._set_status("جاري حفظ كلمة المرور...", False)
        try:
            ok = UserRepository().change_password(self.user_id, old, new)
            if not ok:
                self._set_status("كلمة المرور الحالية غير صحيحة", True)
                return
            current = UserSession.get_current() or {}
            if current:
                # get_current() returns the active session dict.  Mutating it
                # preserves any remote auth token while clearing the mandatory
                # password-change flag after a successful save.
                current["force_password_change"] = 0
            self._set_status("تم تغيير كلمة المرور بنجاح", False)
            if callable(self.on_save):
                self.on_save()
        except Exception as exc:
            self._set_status(f"فشل تغيير كلمة المرور: {exc}", True)
        finally:
            self._set_busy(False)
            try:
                self._page.update()
            except Exception:
                pass
