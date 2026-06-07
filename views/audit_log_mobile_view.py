# -*- coding: utf-8 -*-
import flet as ft
from database import AuditRepository, UserRepository
from i18n.translator import translate
from datetime import datetime, timedelta

class AuditLogMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO

        self.user_filter = ft.Dropdown(label="المستخدم", value="الكل", options=[ft.dropdown.Option("الكل")], width=150)
        self.action_filter = ft.Dropdown(label="العملية", value="الكل",
                                         options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(a) for a in ["إضافة قيد","تعديل قيد","حذف قيد","إضافة مستخدم","تعديل مستخدم","حذف مستخدم","تغيير كلمة المرور"]],
                                         width=150)
        self.start_date = ft.TextField(label="من تاريخ", value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), width=130)
        self.end_date = ft.TextField(label="إلى تاريخ", value=datetime.now().strftime("%Y-%m-%d"), width=130)
        self.apply_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.FILTER_ALT), ft.Text("تطبيق")]), on_click=self._refresh)
        self.delete_old_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.DELETE_SWEEP), ft.Text("حذف القديم")]), bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=self._delete_old)

        self.logs_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
        self.controls = [
            ft.Text(translate('audit_log'), size=20, weight=ft.FontWeight.BOLD),
            ft.Column([
                ft.Row([self.user_filter, self.action_filter], spacing=10),
                ft.Row([self.start_date, self.end_date, self.apply_btn], spacing=10),
                self.delete_old_btn
            ], spacing=10),
            self.logs_list
        ]
        self._load_users()
        self._refresh(None)

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message, size=13), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN, duration=3000)
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
            logs = repo.get_all(limit=500, user_id=user_id, action=action,
                                start_date=self.start_date.value, end_date=self.end_date.value)
            cards = []
            for log in logs:
                action_color = ft.Colors.GREEN if "إضافة" in log.get('action','') else ft.Colors.RED if "حذف" in log.get('action','') else ft.Colors.INDIGO
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(log.get('username',''), size=14, weight=ft.FontWeight.BOLD, expand=True),
                                ft.Container(content=ft.Text(log.get('action',''), size=10, color=ft.Colors.WHITE), bgcolor=action_color, border_radius=10, padding=ft.padding.symmetric(horizontal=8, vertical=3))
                            ]),
                            ft.Row([
                                ft.Text(f"جدول: {log.get('table_name','')}", size=11, color=ft.Colors.GREY_600),
                                ft.Text(f"سجل: {log.get('record_id','')}", size=11, color=ft.Colors.GREY_600)
                            ]),
                            ft.Text(log.get('details','')[:50], size=12, color=ft.Colors.GREY_700, tooltip=log.get('details','')),
                            ft.Row([
                                ft.Text(log.get('ip_address','-'), size=10, color=ft.Colors.GREY_500),
                                ft.Text(log.get('timestamp','')[:19], size=10, color=ft.Colors.GREY_500)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ], spacing=6),
                        padding=12
                    ),
                    elevation=1,
                    margin=ft.margin.symmetric(vertical=5, horizontal=10)
                )
                cards.append(card)
            if not cards:
                cards.append(ft.Container(content=ft.Text("لا توجد سجلات", color=ft.Colors.GREY_400), alignment=ft.Alignment.CENTER, padding=30))
            self.logs_list.controls = cards
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

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
