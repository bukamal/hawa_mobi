# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta
import flet as ft

from auth.permissions import access_denied_message
from auth.session import UserSession
from database import AuditRepository, UserRepository
from i18n.translator import translate
from views.flet_compat import open_control, close_control
from views.design_system.responsive import bottom_safe_spacer
from views.ui_kit import (
    page_header, data_card, pill, empty_state, show_snackbar, search_field,
    info_banner, PRIMARY, SUCCESS, DANGER, WARNING, MUTED, TEXT, BORDER,
)


class AuditLogMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 8
        self.scroll = ft.ScrollMode.AUTO
        self._logs = []

        if not UserSession.is_admin():
            self.controls = [
                page_header(translate('audit_log'), ft.Icons.HISTORY_TOGGLE_OFF),
                empty_state("وصول غير مسموح", access_denied_message(), ft.Icons.LOCK_OUTLINE),
            ]
            return

        self.search = search_field("بحث في العملية أو التفاصيل أو المرجع", self._apply_local_filters)
        self.user_filter = ft.Dropdown(label="المستخدم", value="الكل", options=[ft.dropdown.Option("الكل")], expand=True, border_radius=12, filled=True, border_color=BORDER, focused_border_color=PRIMARY)
        self.action_filter = ft.Dropdown(label="العملية", value="الكل", options=[ft.dropdown.Option("الكل")], expand=True, border_radius=12, filled=True, border_color=BORDER, focused_border_color=PRIMARY)
        self.start_date = ft.TextField(label="من تاريخ", value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), expand=True, border_radius=12, filled=True, border_color=BORDER, focused_border_color=PRIMARY)
        self.end_date = ft.TextField(label="إلى تاريخ", value=datetime.now().strftime("%Y-%m-%d"), expand=True, border_radius=12, filled=True, border_color=BORDER, focused_border_color=PRIMARY)
        self.apply_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.FILTER_ALT_OUTLINED), ft.Text("تطبيق", weight=ft.FontWeight.BOLD)]), on_click=self._refresh, bgcolor=PRIMARY, color=ft.Colors.WHITE, height=46)
        self.logs_list = ft.Column(spacing=8)
        self.controls = [
            page_header(translate('audit_log'), ft.Icons.HISTORY_TOGGLE_OFF, subtitle="تتبّع العمليات الحساسة دون حذف السجل"),
            info_banner("سجل التدقيق غير قابل للحذف من تطبيق Android. يمكن تطبيق سياسة أرشفة إدارية منفصلة على الخادم.", icon=ft.Icons.VERIFIED_USER_OUTLINED),
            self.search,
            data_card(ft.Column([
                ft.Row([self.user_filter, self.action_filter], spacing=10, run_spacing=10, wrap=True),
                ft.Row([self.start_date, self.end_date], spacing=10, run_spacing=10, wrap=True),
                ft.Row([self.apply_btn], alignment=ft.MainAxisAlignment.END),
            ], spacing=10), elevation=0),
            self.logs_list,
            bottom_safe_spacer(self._page),
        ]
        self._load_users()
        self._refresh(None)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _load_users(self):
        try:
            users = UserRepository().get_all()
            self.user_filter.options = [ft.dropdown.Option("الكل")] + [ft.dropdown.Option(u['username']) for u in users]
        except Exception:
            pass

    @staticmethod
    def _action_color(action):
        if "إضافة" in action or "استعادة" in action:
            return SUCCESS
        if "حذف" in action or "عكس" in action or "فشل" in action:
            return DANGER
        if "تعديل" in action or "تغيير" in action:
            return PRIMARY
        if "دخول" in action:
            return WARNING
        return MUTED

    def _refresh(self, e):
        try:
            user_id = None
            if self.user_filter.value != "الكل":
                for user in UserRepository().get_all():
                    if user['username'] == self.user_filter.value:
                        user_id = user['id']
                        break
            action = self.action_filter.value if self.action_filter.value != "الكل" else None
            self._logs = AuditRepository().get_all(limit=1000, user_id=user_id, action=action, start_date=self.start_date.value, end_date=self.end_date.value)
            actions = sorted({str(log.get('action') or '').strip() for log in self._logs if str(log.get('action') or '').strip()})
            current_action = self.action_filter.value
            self.action_filter.options = [ft.dropdown.Option("الكل")] + [ft.dropdown.Option(a) for a in actions]
            if current_action not in {"الكل", *actions}:
                self.action_filter.value = "الكل"
            self._render_logs(self._logs)
        except Exception as ex:
            self._show_snackbar(f"خطأ: {ex}", True)

    def _apply_local_filters(self, e):
        query = str(getattr(e.control, 'value', '') or '').strip().lower()
        if not query:
            self._render_logs(self._logs)
            return
        filtered = []
        for log in self._logs:
            haystack = " ".join(str(log.get(key) or '') for key in ('username', 'action', 'table_name', 'record_id', 'details', 'ip_address')).lower()
            if query in haystack:
                filtered.append(log)
        self._render_logs(filtered)

    def _render_logs(self, logs):
        cards = []
        for log in logs:
            action_name = str(log.get('action') or 'عملية')
            details = str(log.get('details') or '')
            cards.append(data_card(
                ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(log.get('username') or "النظام", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(str(log.get('timestamp') or '')[:19], size=10, color=MUTED),
                        ], expand=True, spacing=2),
                        pill(action_name, color=ft.Colors.WHITE, bgcolor=self._action_color(action_name), size=10),
                    ]),
                    ft.Row([
                        ft.Text(f"جدول: {log.get('table_name', '-')}", size=11, color=MUTED),
                        ft.Text(f"سجل: {log.get('record_id', '-')}", size=11, color=MUTED),
                        ft.Text(log.get('ip_address') or '-', size=11, color=MUTED),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(details[:160] if details else "بدون تفاصيل", size=12, color=TEXT, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=7),
                on_click=lambda e, item=dict(log): self._show_details(item), elevation=0,
            ))
        self.logs_list.controls = cards or [empty_state("لا توجد سجلات", "غيّر المرشحات أو وسّع الفترة الزمنية", ft.Icons.FACT_CHECK_OUTLINED, padding=35)]
        try:
            self._page.update()
        except Exception:
            pass

    def _show_details(self, log):
        rows = [
            ("المستخدم", log.get('username') or "النظام"),
            ("العملية", log.get('action') or "-"),
            ("الوقت", log.get('timestamp') or "-"),
            ("الجدول", log.get('table_name') or "-"),
            ("رقم السجل", log.get('record_id') or "-"),
            ("IP", log.get('ip_address') or "-"),
            ("التفاصيل", log.get('details') or "بدون تفاصيل"),
        ]
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("تفاصيل حدث التدقيق", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=520, content=ft.Column([
                data_card(ft.Row([ft.Text(label, width=105, color=MUTED), ft.Text(str(value), selectable=True, expand=True, color=TEXT)], vertical_alignment=ft.CrossAxisAlignment.START), elevation=0)
                for label, value in rows
            ], spacing=5, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: close_control(self._page, dlg))],
        )
        open_control(self._page, dlg)
