# -*- coding: utf-8 -*-
import flet as ft
from database import UserRepository
from auth.session import UserSession
from i18n.translator import translate

class UsersMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO

        self.add_btn = ft.FloatingActionButton(
            icon=ft.Icons.PERSON_ADD,
            bgcolor=ft.Colors.INDIGO,
            foreground_color=ft.Colors.WHITE,
            on_click=self._add_user,
            tooltip=translate('add'),
            mini=False,
            elevation=6,
            shape=ft.CircleBorder(),
            margin=ft.Margin(left=0, right=16, top=0, bottom=80)
        )
        self._page.floating_action_button = self.add_btn

        self.users_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
        self.controls = [self.users_list]
        self._load_users()

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message, size=13), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN, duration=3000)
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _load_users(self):
        try:
            repo = UserRepository()
            users = repo.get_all()
            cards = []
            for u in users:
                role_text = translate('admin') if u['role'] == 'admin' else translate('user') if u['role'] == 'user' else translate('viewer')
                role_color = ft.Colors.RED if u['role'] == 'admin' else ft.Colors.BLUE if u['role'] == 'user' else ft.Colors.GREY

                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.PERSON, color=ft.Colors.INDIGO, size=24),
                                ft.Text(u['username'], size=16, weight=ft.FontWeight.BOLD, expand=True),
                                ft.Container(
                                    content=ft.Text(role_text, size=11, color=ft.Colors.WHITE),
                                    bgcolor=role_color,
                                    border_radius=15,
                                    padding=10
                                )
                            ]),
                            ft.Text(u['full_name'] or '', size=13, color=ft.Colors.GREY_600),
                            ft.Row([
                                ft.Text(f"تسجيل: {u['created_at'][:10] if u['created_at'] else ''}", size=11, color=ft.Colors.GREY_500),
                                ft.Text(f"دخول: {u['last_login'][:10] if u['last_login'] else ''}", size=11, color=ft.Colors.GREY_500)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.EDIT, size=16), ft.Text("تعديل", size=11)]),
                                    on_click=lambda e, uid=u['id']: self._edit_user(uid)
                                ),
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.DELETE, size=16, color=ft.Colors.RED), ft.Text("حذف", size=11, color=ft.Colors.RED)]),
                                    on_click=lambda e, uid=u['id']: self._delete_user(uid),
                                    disabled=(u['id'] == 1)
                                )
                            ], alignment=ft.MainAxisAlignment.END)
                        ], spacing=8),
                        padding=15
                    ),
                    elevation=1,
                    margin=ft.Margin(left=10, right=10, top=5, bottom=5)
                )
                cards.append(card)
            self.users_list.controls = cards
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل المستخدمين: {str(ex)}", True)

    def _add_user(self, e):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, on_save=lambda: self._load_users())
        self._page.dialog = dialog
        dialog.open = True
        self._page.update()

    def _edit_user(self, user_id):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, user_id=user_id, on_save=lambda: self._load_users())
        self._page.dialog = dialog
        dialog.open = True
        self._page.update()

    def _delete_user(self, user_id):
        def confirm_delete(e):
            repo = UserRepository()
            if repo.delete(user_id):
                self._show_snackbar("تم حذف المستخدم", is_error=False)
                self._load_users()
            else:
                self._show_snackbar("فشل الحذف", True)
            self._close_dialog(dlg)
        dlg = ft.AlertDialog(
            title=ft.Text(translate('confirm_delete')),
            content=ft.Text("هل أنت متأكد من حذف هذا المستخدم؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm_delete),
                ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))
            ]
        )
        self._page.dialog = dlg
        dlg.open = True
        self._page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        self._page.update()
