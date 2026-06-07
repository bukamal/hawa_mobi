# -*- coding: utf-8 -*-
import flet as ft
from database import UserRepository
from auth.session import UserSession
from i18n.translator import translate

class UsersView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15
        self.add_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD), ft.Text(translate('add'))]),
                                       bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._add_user)
        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.users_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(translate('username'))), ft.DataColumn(ft.Text(translate('full_name'))),
                     ft.DataColumn(ft.Text(translate('role'))), ft.DataColumn(ft.Text("تاريخ التسجيل")),
                     ft.DataColumn(ft.Text("آخر دخول")), ft.DataColumn(ft.Text("إجراءات"))],
            rows=[], border=table_border, border_radius=10,
            heading_row_color=ft.Colors.INDIGO_50, data_row_min_height=50, expand=True
        )
        self.controls = [ft.Row([ft.Text(translate('users'), size=24, weight=ft.FontWeight.BOLD), self.add_btn],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                         ft.Container(content=self.users_table, expand=True, border_radius=10, padding=10)]
        self._load_users()

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _load_users(self):
        try:
            repo = UserRepository()
            users = repo.get_all()
            rows = []
            for u in users:
                role_text = translate('admin') if u['role'] == 'admin' else translate('user') if u['role'] == 'user' else translate('viewer')
                role_color = ft.Colors.RED if u['role'] == 'admin' else ft.Colors.BLUE if u['role'] == 'user' else ft.Colors.GREY
                actions = ft.Row([
                    ft.IconButton(icon=ft.Icons.EDIT, tooltip=translate('edit'),
                                  on_click=lambda e, uid=u['id']: self._edit_user(uid)),
                    ft.IconButton(icon=ft.Icons.DELETE, tooltip=translate('delete'), icon_color=ft.Colors.RED,
                                  on_click=lambda e, uid=u['id']: self._delete_user(uid), disabled=(u['id'] == 1))
                ], spacing=5)
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(u['username'], weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(u['full_name'] or '')),
                    ft.DataCell(ft.Text(role_text, color=role_color)),
                    ft.DataCell(ft.Text(u['created_at'][:10] if u['created_at'] else '')),
                    ft.DataCell(ft.Text(u['last_login'][:10] if u['last_login'] else '')),
                    ft.DataCell(actions)
                ]))
            self.users_table.rows = rows
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل المستخدمين: {str(ex)}", True)

    def _add_user(self, e):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, on_save=lambda: self._load_users())
        self._page.show_dialog(dialog)

    def _edit_user(self, user_id):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, user_id=user_id, on_save=lambda: self._load_users())
        self._page.show_dialog(dialog)

    def _delete_user(self, user_id):
        def confirm_delete(e):
            if e.control.text == "نعم":
                repo = UserRepository()
                if repo.delete(user_id):
                    self._show_snackbar("تم حذف المستخدم", is_error=False)
                    self._load_users()
                else:
                    self._show_snackbar("فشل الحذف", True)
            self._page.close_dialog()
        dlg = ft.AlertDialog(title=ft.Text(translate('confirm_delete')), content=ft.Text("هل أنت متأكد من حذف هذا المستخدم؟"),
                             actions=[ft.TextButton("نعم", on_click=confirm_delete), ft.TextButton("لا", on_click=lambda e: self._page.close_dialog())])
        self._page.show_dialog(dlg)
