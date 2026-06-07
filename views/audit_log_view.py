# -*- coding: utf-8 -*-
import flet as ft
from database import AuditRepository, UserRepository
from i18n.translator import translate
from datetime import datetime, timedelta

class AuditLogView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15
        self.user_filter = ft.Dropdown(label="المستخدم", value="الكل", options=[ft.dropdown.Option("الكل")], width=150)
        self.action_filter = ft.Dropdown(label="العملية", value="الكل",
                                         options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(a) for a in [
                                             "إضافة قيد","تعديل قيد","حذف قيد",
                                             "إضافة مستخدم","تعديل مستخدم","حذف مستخدم","تغيير كلمة المرور"]],
                                         width=150)
        self.table_filter = ft.Dropdown(label="الجدول", value="الكل",
                                        options=[ft.dropdown.Option("الكل"), ft.dropdown.Option("expenses"),
                                                 ft.dropdown.Option("users"), ft.dropdown.Option("settings")],
                                        width=150)
        self.start_date = ft.TextField(label="من تاريخ", value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), width=130)
        self.end_date = ft.TextField(label="إلى تاريخ", value=datetime.now().strftime("%Y-%m-%d"), width=130)
        self.apply_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.FILTER_ALT), ft.Text("تطبيق")]), on_click=self._refresh)
        self.export_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD), ft.Text("تصدير Excel")]), on_click=self._export)
        self.delete_old_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.DELETE_SWEEP), ft.Text("حذف القديم")]),
                                              bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=self._delete_old)

        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.audit_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("المستخدم")), ft.DataColumn(ft.Text("الإجراء")), ft.DataColumn(ft.Text("الجدول")),
                     ft.DataColumn(ft.Text("رقم السجل")), ft.DataColumn(ft.Text("التفاصيل")), ft.DataColumn(ft.Text("IP")), ft.DataColumn(ft.Text("التاريخ والوقت"))],
            rows=[], border=table_border, border_radius=10,
            heading_row_color=ft.Colors.INDIGO_50, data_row_min_height=45, expand=True
        )
        self.controls = [ft.Text(translate('audit_log'), size=24, weight=ft.FontWeight.BOLD),
                         ft.Row([self.user_filter, self.action_filter, self.table_filter, self.start_date, self.end_date, self.apply_btn], spacing=10, wrap=True),
                         ft.Row([self.export_btn, self.delete_old_btn], spacing=10),
                         ft.Container(content=self.audit_table, expand=True, border_radius=10, padding=10)]
        self._load_users()
        self._refresh(None)

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _load_users(self):
        try:
            repo = UserRepository()
            users = repo.get_all()
            self.user_filter.options = [ft.dropdown.Option("الكل")] + [ft.dropdown.Option(u['username']) for u in users]
        except: pass

    def _refresh(self, e):
        try:
            repo = AuditRepository()
            user_id = None
            if self.user_filter.value != "الكل":
                user_repo = UserRepository()
                for u in user_repo.get_all():
                    if u['username'] == self.user_filter.value:
                        user_id = u['id']; break
            action = self.action_filter.value if self.action_filter.value != "الكل" else None
            table = self.table_filter.value if self.table_filter.value != "الكل" else None
            logs = repo.get_all(limit=2000, user_id=user_id, action=action, table_name=table,
                                start_date=self.start_date.value, end_date=self.end_date.value)
            rows = []
            for log in logs:
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(log.get('username',''))), ft.DataCell(ft.Text(log.get('action',''))),
                    ft.DataCell(ft.Text(log.get('table_name',''))), ft.DataCell(ft.Text(str(log.get('record_id','')))),
                    ft.DataCell(ft.Text(log.get('details','')[:50], tooltip=log.get('details',''))),
                    ft.DataCell(ft.Text(log.get('ip_address','-'))), ft.DataCell(ft.Text(log.get('timestamp','')[:19]))
                ]))
            self.audit_table.rows = rows
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _export(self, e): self._show_snackbar("قريباً...")
    def _delete_old(self, e):
        def confirm(e):
            if e.control.text == "نعم":
                try:
                    AuditRepository().delete_old_logs(90)
                    self._show_snackbar("تم حذف السجلات القديمة", is_error=False)
                    self._refresh(None)
                except Exception as ex:
                    self._show_snackbar(f"خطأ: {str(ex)}", True)
            self._page.close_dialog()
        dlg = ft.AlertDialog(title=ft.Text("تأكيد الحذف"), content=ft.Text("هل أنت متأكد من حذف السجلات الأقدم من 90 يوماً؟"),
                             actions=[ft.TextButton("نعم", on_click=confirm), ft.TextButton("لا", on_click=lambda e: self._page.close_dialog())])
        self._page.show_dialog(dlg)
