# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import close_control
from views.dialogs.dialog_kit import (
    dialog_title,
    dialog_body,
    cancel_button,
    save_button,
    show_snackbar,
    set_button_busy,
    normalize_text,
)
from database import UserRepository
from auth.session import UserSession
from auth.password_policy import evaluate_password
from i18n.translator import translate


class ChangePasswordDialog(ft.AlertDialog):
    def __init__(self, page, on_save=None, user_id=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.user_id = user_id or (
            UserSession.get_current()["id"] if UserSession.get_current() else None
        )

        page_width = page.width or 400
        dialog_width = min(350, page_width - 40)

        self.old_password = ft.TextField(
            label=translate("old_password"),
            password=True,
            can_reveal_password=True,
            width=dialog_width,
        )
        self.new_password = ft.TextField(
            label=translate("new_password"),
            password=True,
            can_reveal_password=True,
            width=dialog_width,
        )
        self.confirm_password = ft.TextField(
            label=translate("confirm_password"),
            password=True,
            can_reveal_password=True,
            width=dialog_width,
        )
        self.strength_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        self.match_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        self.new_password.on_change = self._validate_live
        self.confirm_password.on_change = self._validate_live

        self._saving = False
        self.save_btn = save_button(translate("save"), self._save)
        self.title = dialog_title(translate("change_password"), ft.Icons.LOCK)
        self.content = dialog_body(
            controls=[
                self.old_password,
                self.new_password,
                self.strength_text,
                self.confirm_password,
                self.match_text,
            ],
            spacing=15,
            width=dialog_width + 20,
        )
        self.actions = [
            cancel_button(translate("cancel"), lambda e: self._close()),
            self.save_btn,
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 20
        self.shape = ft.RoundedRectangleBorder(radius=15)

    def _close(self):
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

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
            self.strength_text.color = (
                ft.Colors.GREEN if policy["ok"] else ft.Colors.ORANGE
            )
        else:
            self.strength_text.value = ""
        if confirm:
            self.match_text.value = (
                "كلمتا المرور متطابقتان"
                if new == confirm
                else "كلمتا المرور غير متطابقتين"
            )
            self.match_text.color = ft.Colors.GREEN if new == confirm else ft.Colors.RED
        else:
            self.match_text.value = ""
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        old = normalize_text(self.old_password.value)
        new = normalize_text(self.new_password.value)
        confirm = normalize_text(self.confirm_password.value)

        if not old or not new:
            self._show_snackbar("جميع الحقول مطلوبة")
            return
        policy = evaluate_password(new)
        if not policy["ok"]:
            self._show_snackbar(
                "كلمة المرور ضعيفة: " + "، ".join(policy["problems"][:3]), True
            )
            return
        if old == new:
            self._show_snackbar("كلمة المرور الجديدة يجب أن تختلف عن الحالية", True)
            return
        if new != confirm:
            self._show_snackbar("كلمتا المرور غير متطابقتين")
            return
        self._saving = True
        set_button_busy(self.save_btn, True, translate("save"))
        try:
            self._page.update()
        except Exception:
            pass
        repo = UserRepository()
        try:
            ok = repo.change_password(self.user_id, old, new)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, translate("save"))
            try:
                self._page.update()
            except Exception:
                pass
        if ok:
            self._show_snackbar("تم تغيير كلمة المرور بنجاح", is_error=False)
            self._close()
            if self.on_save:
                self.on_save()
        else:
            self._show_snackbar("كلمة المرور الحالية غير صحيحة", True)
