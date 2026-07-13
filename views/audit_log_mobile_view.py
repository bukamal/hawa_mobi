# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control
from views.ui_kit import page_header, data_card, pill, empty_state, show_snackbar
from database import AuditRepository, UserRepository
from i18n.translator import translate
from datetime import datetime, timedelta


class AuditLogMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 8
        self.scroll = ft.ScrollMode.AUTO

        self.user_filter = ft.Dropdown(
            label="المستخدم",
            value="الكل",
            options=[ft.dropdown.Option("الكل")],
            expand=True,
        )
        self.action_filter = ft.Dropdown(
            label="العملية",
            value="الكل",
            options=[ft.dropdown.Option("الكل")]
            + [
                ft.dropdown.Option(a)
                for a in [
                    "إضافة قيد",
                    "تعديل قيد",
                    "حذف قيد",
                    "إضافة مستخدم",
                    "تعديل مستخدم",
                    "حذف مستخدم",
                    "تغيير كلمة المرور",
                ]
            ],
            expand=True,
        )
        self.start_date = ft.TextField(
            label="من تاريخ",
            value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            expand=True,
        )
        self.end_date = ft.TextField(
            label="إلى تاريخ", value=datetime.now().strftime("%Y-%m-%d"), expand=True
        )
        self.apply_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.FILTER_ALT), ft.Text("تطبيق")]),
            on_click=self._refresh,
        )
        self.delete_old_btn = ft.OutlinedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.DELETE_SWEEP, color=ft.Colors.RED),
                    ft.Text("حذف القديم", color=ft.Colors.RED),
                ]
            ),
            on_click=self._delete_old,
        )

        self.logs_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.controls = [
            page_header(
                translate("audit_log"),
                ft.Icons.HISTORY,
                subtitle="تتبع العمليات الحساسة داخل النظام",
            ),
            data_card(
                ft.Column(
                    [
                        ft.Row([self.user_filter, self.action_filter], spacing=10),
                        ft.Row([self.start_date, self.end_date], spacing=10),
                        ft.Row(
                            [self.apply_btn, self.delete_old_btn],
                            spacing=10,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=10,
                ),
                elevation=1,
            ),
            self.logs_list,
        ]
        self._load_users()
        self._refresh(None)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _load_users(self):
        try:
            users = UserRepository().get_all()
            self.user_filter.options = [ft.dropdown.Option("الكل")] + [
                ft.dropdown.Option(u["username"]) for u in users
            ]
        except Exception:
            pass

    def _action_color(self, action):
        if "إضافة" in action:
            return ft.Colors.GREEN
        if "حذف" in action:
            return ft.Colors.RED
        if "تعديل" in action or "تغيير" in action:
            return ft.Colors.INDIGO
        return ft.Colors.GREY

    def _refresh(self, e):
        try:
            repo = AuditRepository()
            user_id = None
            if self.user_filter.value != "الكل":
                for u in UserRepository().get_all():
                    if u["username"] == self.user_filter.value:
                        user_id = u["id"]
                        break
            action = (
                self.action_filter.value if self.action_filter.value != "الكل" else None
            )
            logs = repo.get_all(
                limit=500,
                user_id=user_id,
                action=action,
                start_date=self.start_date.value,
                end_date=self.end_date.value,
            )
            cards = []
            for log in logs:
                action_name = log.get("action", "")
                action_color = self._action_color(action_name)
                details = log.get("details", "") or ""
                card = data_card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                log.get("username", "") or "النظام",
                                                size=14,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                log.get("timestamp", "")[:19],
                                                size=10,
                                                color=ft.Colors.GREY_500,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=2,
                                    ),
                                    pill(
                                        action_name or "عملية",
                                        color=ft.Colors.WHITE,
                                        bgcolor=action_color,
                                        size=10,
                                    ),
                                ]
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        f"جدول: {log.get('table_name', '-')}",
                                        size=11,
                                        color=ft.Colors.GREY_600,
                                    ),
                                    ft.Text(
                                        f"سجل: {log.get('record_id', '-')}",
                                        size=11,
                                        color=ft.Colors.GREY_600,
                                    ),
                                    ft.Text(
                                        log.get("ip_address", "-") or "-",
                                        size=11,
                                        color=ft.Colors.GREY_500,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                details[:140] if details else "بدون تفاصيل",
                                size=12,
                                color=ft.Colors.GREY_700,
                                tooltip=details,
                            ),
                        ],
                        spacing=7,
                    ),
                    elevation=1,
                )
                cards.append(card)
            self.logs_list.controls = cards or [
                empty_state(
                    "لا توجد سجلات",
                    "غيّر المرشحات أو وسّع الفترة الزمنية",
                    ft.Icons.FACT_CHECK_OUTLINED,
                    padding=35,
                )
            ]
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _delete_old(self, e):
        def confirm(e):
            try:
                AuditRepository().delete_old_logs(90)
                self._show_snackbar("تم حذف السجلات القديمة", is_error=False)
                self._refresh(None)
            except Exception as ex:
                self._show_snackbar(f"خطأ: {str(ex)}", True)
            self._close_dialog(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text("هل أنت متأكد من حذف السجلات الأقدم من 90 يوماً؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg)),
            ],
        )
        open_control(self._page, dlg)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
