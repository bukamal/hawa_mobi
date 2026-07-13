# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control
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
from i18n.translator import translate


class UserDialog(ft.AlertDialog):
    def __init__(self, page, on_save=None, user_id=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.user_id = user_id

        page_width = page.width or 400
        dialog_width = min(380, page_width - 40)

        self.username = ft.TextField(
            label=translate("username"), width=dialog_width - 20, disabled=bool(user_id)
        )
        self.fullname = ft.TextField(
            label=translate("full_name"), width=dialog_width - 20
        )
        self.role = ft.Dropdown(
            label=translate("role"),
            value=translate("user"),
            options=[
                ft.dropdown.Option(translate("admin")),
                ft.dropdown.Option(translate("user")),
                ft.dropdown.Option(translate("viewer")),
            ],
            width=dialog_width - 20,
        )
        self.password = ft.TextField(
            label=translate("password"),
            password=True,
            can_reveal_password=True,
            width=dialog_width - 20,
            visible=not user_id,
        )
        self.confirm_password = ft.TextField(
            label="تأكيد " + translate("password"),
            password=True,
            can_reveal_password=True,
            width=dialog_width - 20,
            visible=not user_id,
        )
        self.change_pwd_btn = ft.TextButton(
            content=ft.Text(translate("change_password")),
            on_click=self._change_password,
            visible=bool(user_id),
        )

        self._saving = False
        self.save_btn = save_button(translate("save"), self._save)
        self.title = dialog_title(
            translate("add") if not user_id else translate("edit"), ft.Icons.PERSON
        )
        self.content = dialog_body(
            controls=[
                self.username,
                self.fullname,
                self.role,
                self.password,
                self.confirm_password,
                self.change_pwd_btn,
            ],
            spacing=15,
            width=dialog_width,
        )
        self.actions = [
            cancel_button(translate("cancel"), lambda e: self._close()),
            self.save_btn,
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 20
        self.shape = ft.RoundedRectangleBorder(radius=15)

        if user_id:
            self._load_user()

    def _close(self):
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _load_user(self):
        try:
            repo = UserRepository()
            user = repo.get_by_id(self.user_id)
            if user:
                self.username.value = user["username"]
                self.fullname.value = user["full_name"] or ""
                role_map = {
                    "admin": translate("admin"),
                    "user": translate("user"),
                    "viewer": translate("viewer"),
                }
                self.role.value = role_map.get(user["role"], translate("user"))
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل البيانات: {str(ex)}", True)

    def _save(self, e):
        if self._saving:
            return
        username = normalize_text(self.username.value)
        full_name = normalize_text(self.fullname.value)
        role_map = {
            translate("admin"): "admin",
            translate("user"): "user",
            translate("viewer"): "viewer",
        }
        role = role_map.get(self.role.value, "user")
        if not username:
            self._show_snackbar("اسم المستخدم مطلوب")
            return
        repo = UserRepository()
        self._saving = True
        set_button_busy(self.save_btn, True, translate("save"))
        try:
            self._page.update()
        except Exception:
            pass
        try:
            if not self.user_id:
                password = self.password.value
                confirm = self.confirm_password.value
                if not password:
                    self._show_snackbar("كلمة المرور مطلوبة")
                    return
                if password != confirm:
                    self._show_snackbar("كلمتا المرور غير متطابقتين")
                    return
                repo.create(username, password, full_name, role)
                self._show_snackbar("تمت الإضافة بنجاح", is_error=False)
            else:
                repo.update(self.user_id, full_name, role)
                self._show_snackbar("تم التحديث بنجاح", is_error=False)
            self._close()
            if self.on_save:
                self.on_save()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, translate("save"))
            try:
                self._page.update()
            except Exception:
                pass

    def _change_password(self, e):
        from views.dialogs.change_password_dialog import ChangePasswordDialog

        dialog = ChangePasswordDialog(
            page=self._page, user_id=self.user_id, on_save=lambda: None
        )
        open_control(self._page, dialog)
