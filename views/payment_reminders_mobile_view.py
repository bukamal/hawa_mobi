# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import flet as ft

from auth.session import UserSession
from currency import currency
from database import ExpenseRepository
from views.dialogs.batch_payment_dialog import BatchPaymentDialog, BatchPaymentHistoryDialog
from views.dialogs.payment_dialog import PaymentDialog
from views.flet_compat import open_control, run_async_task, show_snackbar
from views.ui_kit import (
    page_header, data_card, empty_state, PRIMARY, PRIMARY_SOFT, TEXT, MUTED,
    SUCCESS, WARNING, DANGER,
)


class PaymentRemindersMobileView(ft.Column):
    """Actionable list of outstanding receivables and payables."""

    def __init__(self, page, on_open_company=None, focus_expense_id=None, notification_action=None):
        super().__init__()
        self._page = page
        self.on_open_company = on_open_company
        self.focus_expense_id = int(focus_expense_id or 0)
        self.notification_action = str(notification_action or "")
        self._focused_record = None
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.repo = ExpenseRepository()
        self.list_host = ft.Column(spacing=10)
        role = (UserSession.get_current() or {}).get("role") or "user"
        header_actions = ft.Row([
            ft.IconButton(
                icon=ft.Icons.HISTORY_OUTLINED,
                tooltip="سجل الدفعات المجمعة",
                on_click=lambda e: self._open_batch_history(),
            ),
            ft.FilledButton(
                "دفعة مجمعة",
                icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                on_click=lambda e: self._open_batch_payment(),
                visible=role != "viewer",
                height=42,
            ),
        ], spacing=4, tight=True)
        self.controls = [
            page_header(
                "متابعة الدفعات",
                icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED,
                subtitle="المبالغ الجزئية والمتأخرة محسوبة من سجل الدفعات الفعلي",
                trailing=header_actions,
            ),
            self.list_host,
            ft.Container(height=24),
        ]
        self.reload()
        if self.focus_expense_id:
            run_async_task(self._page, self._handle_notification_focus)

    async def _handle_notification_focus(self):
        import asyncio
        await asyncio.sleep(0.20)
        record = self._focused_record
        if not record:
            return
        try:
            setattr(self._page, "_hawaa_notification_focus_expense_id", None)
            setattr(self._page, "_hawaa_notification_action", None)
        except Exception:
            pass
        if self.notification_action == "pay":
            self._open_payment(record)
        else:
            show_snackbar(self._page, "تم فتح المطالبة المرتبطة بالتنبيه", is_error=False)

    def reload(self, *_):
        try:
            rows = self.repo.get_pending_payment_reminders()
        except Exception as ex:
            self.list_host.controls = [empty_state("تعذر تحميل التذكيرات", str(ex), ft.Icons.ERROR_OUTLINE)]
            return
        if not rows:
            self.list_host.controls = [empty_state("لا توجد دفعات معلقة", "كل المطالبات المسجلة مكتملة حاليًا", ft.Icons.CHECK_CIRCLE_OUTLINE)]
            return
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        records = [dict(row) for row in rows]
        if self.focus_expense_id:
            records.sort(key=lambda row: 0 if int(row.get("expense_id") or 0) == self.focus_expense_id else 1)
            self._focused_record = next((row for row in records if int(row.get("expense_id") or 0) == self.focus_expense_id), None)
        self.list_host.controls = [self._card(row, today) for row in records]

    def _card(self, row, today):
        code = row.get("currency_original") or "USD"
        total = float(row.get("amount_original") or 0)
        paid = float(row.get("paid_amount_original") or 0)
        remaining = float(row.get("remaining_amount_original") or max(0, total - paid))
        due = str(row.get("reminder_date") or "")[:10]
        overdue = bool(due and due < today)
        tone = DANGER if overdue else WARNING
        role = (UserSession.get_current() or {}).get("role") or "user"
        can_pay = role != "viewer" and total > 0.005 and remaining > 0.005
        direction = "مطلوب تحصيله" if row.get("type") == "incoming" else "مطلوب دفعه"

        actions = []
        if can_pay:
            actions.append(ft.FilledButton(
                "تسجيل دفعة",
                icon=ft.Icons.PAYMENTS_OUTLINED,
                on_click=lambda e, record=dict(row): self._open_payment(record),
                bgcolor=SUCCESS,
                color=ft.Colors.WHITE,
                height=42,
            ))
            actions.append(ft.OutlinedButton(
                "توزيع دفعة",
                icon=ft.Icons.ACCOUNT_TREE_OUTLINED,
                on_click=lambda e, record=dict(row): self._open_batch_payment(record),
                height=42,
            ))
        if callable(self.on_open_company):
            actions.append(ft.OutlinedButton(
                "فتح الحساب",
                icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED,
                on_click=lambda e, company=row.get("company_name"): self.on_open_company(company),
                height=42,
            ))

        title = row.get("person_name") or row.get("company_name") or "طرف غير محدد"
        subtitle = row.get("company_name") if row.get("person_name") else direction
        status_text = "متأخر" if overdue else ("مستحق" if due else "دون تاريخ استحقاق")
        if total <= 0.005:
            status_text = "بانتظار تحديد الإجمالي"

        return data_card(
            ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.SCHEDULE_OUTLINED if overdue else ft.Icons.RECEIPT_LONG_OUTLINED, color=tone, size=23),
                        bgcolor="#FDECEC" if overdue else "#FFF7E6",
                        border_radius=14,
                        padding=10,
                    ),
                    ft.Column([
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text(subtitle or direction, size=12, color=MUTED),
                    ], spacing=2, expand=True),
                    ft.Container(
                        content=ft.Text(status_text, size=11, weight=ft.FontWeight.BOLD, color=tone),
                        bgcolor="#FDECEC" if overdue else "#FFF7E6",
                        border_radius=12,
                        padding=ft.Padding(9, 5, 9, 5),
                    ),
                ], spacing=10),
                ft.Divider(height=12),
                ft.Row([
                    self._metric("الإجمالي", currency.format_amount_ui(total, code), PRIMARY),
                    self._metric("المدفوع", currency.format_amount_ui(paid, code), SUCCESS),
                    self._metric("المتبقي", currency.format_amount_ui(remaining, code), tone),
                ], spacing=8, wrap=True),
                ft.Text(f"الاستحقاق: {due or '—'} · {direction}", size=11, color=MUTED),
                ft.Text(str(row.get("note") or ""), size=11, color=MUTED, visible=bool(row.get("note"))),
                ft.Row(actions, spacing=8, wrap=True) if actions else ft.Container(),
            ], spacing=8),
            elevation=0,
        )

    @staticmethod
    def _metric(label, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=10, color=MUTED),
                ft.Text(value, size=13, weight=ft.FontWeight.BOLD, color=color),
            ], spacing=2),
            bgcolor=PRIMARY_SOFT,
            border_radius=10,
            padding=8,
        )

    def _open_payment(self, record):
        dialog = PaymentDialog(self._page, record, on_save=lambda result: self._after_payment())
        open_control(self._page, dialog)

    def _after_payment(self):
        self.reload()
        try:
            from services.local_notification_manager import request_local_notification_resync
            request_local_notification_resync(self._page)
        except Exception:
            pass
        try:
            self._page.update()
        except Exception:
            pass

    def _open_batch_payment(self, initial_record=None):
        dialog = BatchPaymentDialog(
            self._page,
            initial_record=initial_record,
            on_save=lambda result: self._after_payment(),
        )
        open_control(self._page, dialog)

    def _open_batch_history(self):
        dialog = BatchPaymentHistoryDialog(self._page, on_change=lambda: self._after_payment())
        open_control(self._page, dialog)
