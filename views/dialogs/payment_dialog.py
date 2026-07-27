# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import datetime
import flet as ft

from auth.session import UserSession
from currency import currency
from database import PaymentRepository
from views.dialogs.dialog_kit import cancel_button, dialog_body, dialog_title, parse_non_negative_amount, save_button, set_button_busy, show_snackbar
from views.financial_date_field import FinancialDateField
from views.flet_compat import close_control, open_control, run_async_task
from views.ui_kit import PRIMARY, PRIMARY_SOFT, SUCCESS, DANGER, WARNING, MUTED, BORDER


_PAYMENT_METHODS = [
    ("cash", "نقدي"),
    ("bank_transfer", "تحويل بنكي"),
    ("card", "بطاقة"),
    ("cheque", "شيك"),
    ("other", "أخرى"),
]


class PaymentDialog(ft.AlertDialog):
    """Register and review partial payments for one ledger claim."""

    def __init__(self, page, expense, on_save=None):
        super().__init__()
        self._page = page
        self.expense = dict(expense or {})
        self.expense_id = int(self.expense.get("id") or 0)
        self.on_save = on_save
        self.repo = PaymentRepository()
        self._saving = False
        self._summary = self.repo.get_summary(self.expense_id)

        width = min(max(float(getattr(page, "width", 420) or 420) - 36, 320), 620)
        remaining = float(self._summary.get("remaining_amount_original") or 0)
        code = self._summary.get("currency_original") or "USD"
        direction_label = "استلام من العميل / المسافر" if self.expense.get("type") == "incoming" else "دفع للمورد"

        self.summary_text = ft.Text(self._summary_line(), size=13, weight=ft.FontWeight.BOLD, color=PRIMARY)
        self.amount_field = ft.TextField(
            label="مبلغ الدفعة",
            value=(f"{remaining:.2f}" if remaining > 0 else ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text=code,
            width=220,
            autofocus=remaining > 0,
        )
        self.method_field = ft.Dropdown(
            label="طريقة الدفع",
            value="cash",
            options=[ft.dropdown.Option(key, label) for key, label in _PAYMENT_METHODS],
            width=210,
            filled=True,
        )
        self.payment_date = FinancialDateField(page, label="تاريخ الدفعة", value=datetime.datetime.now().strftime("%Y-%m-%d"), width=210)
        self.reference_field = ft.TextField(label="رقم المرجع / الحوالة", width=210)
        self.notes_field = ft.TextField(label="ملاحظات", multiline=True, min_lines=2, max_lines=3, width=width - 24)
        self.history = ft.Column(spacing=7)
        self._load_history()

        self.save_btn = save_button("تسجيل الدفعة", self._save)
        self.title = dialog_title(direction_label, ft.Icons.PAYMENTS_OUTLINED)
        self.content = dialog_body(
            [
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{self.expense.get('company_name') or '—'} · {self.expense.get('person_name') or self.expense.get('service_type') or ''}", weight=ft.FontWeight.BOLD),
                        self.summary_text,
                    ], spacing=5),
                    bgcolor=PRIMARY_SOFT,
                    border_radius=12,
                    padding=12,
                ),
                ft.Row([self.amount_field, self.method_field], spacing=10, wrap=True),
                ft.Row([self.payment_date, self.reference_field], spacing=10, wrap=True),
                self.notes_field,
                ft.Divider(),
                ft.Text("سجل الدفعات", size=14, weight=ft.FontWeight.BOLD),
                self.history,
            ],
            width=width,
            height=min(max(float(getattr(page, "height", 760) or 760) - 150, 430), 650),
            spacing=12,
        )
        self.actions = [cancel_button("إغلاق", lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=16)
        if remaining <= 0:
            self.save_btn.disabled = True
            self.amount_field.disabled = True

    def _summary_line(self):
        code = self._summary.get("currency_original") or "USD"
        total = currency.format_amount_ui(float(self._summary.get("total_amount_original") or 0), code)
        paid = currency.format_amount_ui(float(self._summary.get("paid_amount_original") or 0), code)
        remaining = currency.format_amount_ui(float(self._summary.get("remaining_amount_original") or 0), code)
        return f"الإجمالي {total} · المدفوع {paid} · المتبقي {remaining} · {self._summary.get('payment_status_label') or ''}"

    def _load_history(self):
        try:
            rows = self.repo.list_for_expense(self.expense_id)
        except Exception as ex:
            self.history.controls = [ft.Text(f"تعذر تحميل الدفعات: {ex}", color=DANGER, size=12)]
            return
        if not rows:
            self.history.controls = [ft.Text("لا توجد دفعات مسجلة", color=MUTED, size=12)]
            return
        is_admin = (UserSession.get_current() or {}).get("role") in {"admin", "manager", "accountant"}
        controls = []
        for row in rows:
            amount = currency.format_amount_ui(float(row.get("amount_original") or 0), row.get("currency_original") or "USD")
            method = dict(_PAYMENT_METHODS).get(row.get("payment_method"), row.get("payment_method") or "—")
            trailing = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=DANGER,
                tooltip="حذف الدفعة",
                on_click=lambda e, payment=dict(row): self._confirm_delete(payment),
                visible=is_admin,
            )
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=SUCCESS, size=19),
                    ft.Column([
                        ft.Text(amount, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{row.get('date') or '—'} · {method} · {row.get('reference_number') or row.get('reference') or ''}", size=10, color=MUTED),
                    ], spacing=2, expand=True),
                    trailing,
                ], spacing=8),
                border=ft.border.all(1, BORDER), border_radius=10, padding=8,
            ))
        self.history.controls = controls

    def _show(self, message, error=False):
        show_snackbar(self._page, message, error)

    def _close(self):
        try:
            self.payment_date.close()
        except Exception:
            pass
        close_control(self._page, self)

    def _save(self, e=None):
        if self._saving:
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
            if amount <= 0:
                raise ValueError("مبلغ الدفعة يجب أن يكون أكبر من صفر")
            if amount > float(self._summary.get("remaining_amount_original") or 0) + 0.005:
                raise ValueError("مبلغ الدفعة أكبر من المتبقي")
            date = self.payment_date.require_value("تاريخ الدفعة")
        except Exception as ex:
            self._show(str(ex), True)
            return
        self._saving = True
        set_button_busy(self.save_btn, True, "تسجيل الدفعة", "جارٍ تسجيل الدفعة...")
        try:
            self._page.update()
        except Exception:
            pass
        run_async_task(self._page, self._save_async, amount, date)

    async def _save_async(self, amount, date):
        try:
            result = await asyncio.to_thread(
                lambda: self.repo.add(
                    self.expense_id,
                    amount,
                    date=date,
                    payment_method=self.method_field.value or "cash",
                    reference_number=self.reference_field.value or "",
                    notes=self.notes_field.value or "",
                )
            )
            self._summary = result
            self._show("تم تسجيل الدفعة وتحديث المتبقي", False)
            self._close()
            if self.on_save:
                self.on_save(result)
        except Exception as ex:
            self._show(f"فشل تسجيل الدفعة: {ex}", True)
            self._saving = False
            set_button_busy(self.save_btn, False, "تسجيل الدفعة")
            try:
                self._page.update()
            except Exception:
                pass

    def _confirm_delete(self, payment):
        reason = ft.TextField(label="سبب حذف الدفعة", multiline=True, min_lines=2, max_lines=3)
        dlg = None

        def confirm(e=None):
            clean = str(reason.value or "").strip()
            if not clean:
                self._show("سبب حذف الدفعة مطلوب", True)
                return
            try:
                self.repo.delete(int(payment["id"]), reason=clean)
                close_control(self._page, dlg)
                self._summary = self.repo.get_summary(self.expense_id)
                self.summary_text.value = self._summary_line()
                self._load_history()
                remaining = float(self._summary.get("remaining_amount_original") or 0)
                self.amount_field.value = f"{remaining:.2f}" if remaining > 0 else ""
                self.amount_field.disabled = remaining <= 0
                self.save_btn.disabled = remaining <= 0
                self._page.update()
                if self.on_save:
                    self.on_save(self._summary)
                self._show("تم حذف الدفعة وإعادة احتساب المتبقي", False)
            except Exception as ex:
                self._show(f"فشل حذف الدفعة: {ex}", True)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("حذف دفعة", color=DANGER, weight=ft.FontWeight.BOLD),
            content=ft.Column([ft.Text("سيُحذف قيد التسوية المرتبط بهذه الدفعة أيضاً."), reason], tight=True, spacing=10),
            actions=[ft.TextButton("حذف", on_click=confirm, style=ft.ButtonStyle(color=DANGER)), ft.TextButton("إلغاء", on_click=lambda e: close_control(self._page, dlg))],
        )
        open_control(self._page, dlg)
