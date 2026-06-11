# -*- coding: utf-8 -*-
import flet as ft
from database import UserRepository
from auth.session import UserSession
from i18n.translator import translate

class ChangePasswordDialog(ft.AlertDialog):
    def __init__(self, page, on_save=None, user_id=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.user_id = user_id or (UserSession.get_current()['id'] if UserSession.get_current() else None)

        page_width = page.width or 400
        dialog_width = min(350, page_width - 40)

        self.old_password = ft.TextField(
            label=translate('old_password'),
            password=True,
            can_reveal_password=True,
            width=dialog_width
        )
        self.new_password = ft.TextField(
            label=translate('new_password'),
            password=True,
            can_reveal_password=True,
            width=dialog_width
        )
        self.confirm_password = ft.TextField(
            label=translate('confirm_password'),
            password=True,
            can_reveal_password=True,
            width=dialog_width
        )

        self.title = ft.Text(translate('change_password'), size=18, weight=ft.FontWeight.BOLD)
        self.content = ft.Column(
            controls=[self.old_password, self.new_password, self.confirm_password],
            spacing=15,
            width=dialog_width + 20,
            scroll=ft.ScrollMode.AUTO
        )
        self.actions = [
            ft.TextButton(translate('cancel'), on_click=lambda e: self._close()),
            ft.FilledButton(translate('save'), on_click=self._save, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE)
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 20
        self.shape = ft.RoundedRectangleBorder(radius=15)

    def _close(self):
        self.open = False
        self._page.update()

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message, size=13), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN, duration=3000)
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _save(self, e):
        old = self.old_password.value
        new = self.new_password.value
        confirm = self.confirm_password.value

        if not old or not new:
            self._show_snackbar("جميع الحقول مطلوبة")
            return
        if new != confirm:
            self._show_snackbar("كلمتا المرور غير متطابقتين")
            return
        repo = UserRepository()
        if repo.change_password(self.user_id, old, new):
            self._show_snackbar("تم تغيير كلمة المرور بنجاح", is_error=False)
            self._close()
            if self.on_save:
                self.on_save()
        else:
            self._show_snackbar("كلمة المرور الحالية غير صحيحة", True)
