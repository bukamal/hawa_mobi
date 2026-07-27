# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import datetime
import flet as ft

from auth.session import UserSession
from currency import currency
from database import BatchPaymentRepository
from views.dialogs.dialog_kit import (
    cancel_button,
    dialog_body,
    dialog_title,
    parse_non_negative_amount,
    save_button,
    set_button_busy,
    show_snackbar,
)
from views.financial_date_field import FinancialDateField
from views.flet_compat import close_control, open_control, run_async_task
from views.ui_kit import PRIMARY, PRIMARY_SOFT, SUCCESS, WARNING, DANGER, MUTED, BORDER, TEXT


_PAYMENT_METHODS = [
    ("cash", "نقدي"),
    ("bank_transfer", "تحويل بنكي"),
    ("card", "بطاقة"),
    ("cheque", "شيك"),
    ("other", "أخرى"),
]


class BatchPaymentDialog(ft.AlertDialog):
    """Register one cash movement and allocate it across multiple claims."""

    def __init__(self, page, on_save=None, initial_record=None, initial_company=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.repo = BatchPaymentRepository()
        self._saving = False
        self.scopes = self.repo.list_party_scopes()
        if initial_company:
            company = str(initial_company).strip()
            self.scopes = [item for item in self.scopes if item.get("company_name") == company]
        self.claims = []
        self.manual_fields = {}
        width = min(max(float(getattr(page, "width", 420) or 420) - 32, 330), 760)

        self.scope_field = ft.Dropdown(
            label="الطرف ونوع الحركة",
            options=[ft.dropdown.Option(f"scope-{idx}", self._scope_label(item)) for idx, item in enumerate(self.scopes)],
            value="scope-0" if self.scopes else None,
            on_change=self._scope_changed,
            width=width - 24,
            filled=True,
        )
        self.amount_field = ft.TextField(
            label="مبلغ الدفعة المجمعة",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: self._refresh_preview(),
            width=220,
        )
        self.mode_field = ft.Dropdown(
            label="طريقة التوزيع",
            value="oldest",
            options=[
                ft.dropdown.Option("oldest", "تلقائيًا على الأقدم"),
                ft.dropdown.Option("manual", "توزيع يدوي"),
            ],
            on_change=self._mode_changed,
            width=230,
            filled=True,
        )
        self.method_field = ft.Dropdown(
            label="طريقة الدفع",
            value="cash",
            options=[ft.dropdown.Option(key, label) for key, label in _PAYMENT_METHODS],
            width=210,
            filled=True,
        )
        self.payment_date = FinancialDateField(
            page,
            label="تاريخ الدفعة",
            value=datetime.datetime.now().strftime("%Y-%m-%d"),
            width=210,
        )
        self.reference_field = ft.TextField(label="رقم المرجع / الحوالة", width=230)
        self.notes_field = ft.TextField(label="ملاحظات", multiline=True, min_lines=2, max_lines=3, width=width - 24)
        self.claims_host = ft.Column(spacing=8)
        self.preview_text = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=PRIMARY)
        self.save_btn = save_button("تسجيل وتوزيع الدفعة", self._save)

        self.title = dialog_title("دفعة مجمعة", ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED)
        if not self.scopes:
            self.scope_field.disabled = True
            self.amount_field.disabled = True
            self.save_btn.disabled = True
            self.claims_host.controls = [ft.Text("لا توجد مطالبات معلقة قابلة للتوزيع", color=MUTED)]
        else:
            self._load_scope()

        self.content = dialog_body(
            [
                ft.Container(
                    content=ft.Column([
                        ft.Text("سجّل قبضًا أو دفعًا واحدًا، ثم وزّعه على عدة قيود وخدمات.", size=12, color=TEXT),
                        ft.Text("أي مبلغ زائد يتحول إلى رصيد دائن أو دفعة مقدمة للطرف.", size=11, color=MUTED),
                    ], spacing=4),
                    bgcolor=PRIMARY_SOFT,
                    border_radius=12,
                    padding=12,
                ),
                self.scope_field,
                ft.Row([self.amount_field, self.mode_field], spacing=10, wrap=True),
                ft.Row([self.payment_date, self.method_field, self.reference_field], spacing=10, wrap=True),
                self.notes_field,
                ft.Divider(),
                ft.Text("المطالبات المشمولة", size=14, weight=ft.FontWeight.BOLD),
                self.claims_host,
                ft.Container(content=self.preview_text, bgcolor=PRIMARY_SOFT, border_radius=10, padding=10),
            ],
            width=width,
            height=min(max(float(getattr(page, "height", 760) or 760) - 130, 470), 690),
            spacing=12,
        )
        self.actions = [cancel_button("إغلاق", lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 16
        self.shape = ft.RoundedRectangleBorder(radius=16)

        if initial_record and self.scopes:
            self._select_initial(initial_record)

    @staticmethod
    def _scope_label(item):
        direction = "قبض من" if item.get("direction") == "received" else "دفع إلى"
        code = item.get("currency_original") or "USD"
        person = str(item.get("person_name") or "").strip()
        party = f"{person} / {item.get('company_name')}" if person else f"{item.get('company_name')} — كل المطالبات"
        total = currency.format_amount_ui(float(item.get("remaining_amount_original") or 0), code)
        return f"{direction} {party} · {total}"

    def _select_initial(self, record):
        company = str(record.get("company_name") or "").strip()
        person = str(record.get("person_name") or "").strip()
        direction = "received" if record.get("type") == "incoming" else "paid"
        code = record.get("currency_original") or "USD"
        for idx, item in enumerate(self.scopes):
            if (
                item.get("company_name") == company
                and item.get("person_name", "") == person
                and item.get("direction") == direction
                and item.get("currency_original") == code
            ):
                self.scope_field.value = f"scope-{idx}"
                self._load_scope()
                break

    def _selected_scope(self):
        value = str(self.scope_field.value or "")
        if not value.startswith("scope-"):
            return None
        try:
            return self.scopes[int(value.split("-", 1)[1])]
        except Exception:
            return None

    def _scope_changed(self, e=None):
        self._load_scope()
        self._safe_update()

    def _mode_changed(self, e=None):
        manual = self.mode_field.value == "manual"
        for field in self.manual_fields.values():
            field.visible = manual
        self._refresh_preview()
        self._safe_update()

    def _load_scope(self):
        scope = self._selected_scope()
        self.claims = []
        self.manual_fields = {}
        if not scope:
            self.claims_host.controls = []
            return
        self.claims = self.repo.list_outstanding(
            company_name=scope["company_name"],
            person_name=scope["person_name"] if scope.get("person_name") else None,
            direction=scope["direction"],
            currency_code=scope["currency_original"],
        )
        controls = []
        for row in self.claims:
            expense_id = int(row["id"])
            code = row.get("currency_original") or "USD"
            remaining = float(row.get("remaining_amount_original") or 0)
            field = ft.TextField(
                label="تخصيص",
                value="0.00",
                suffix_text=code,
                keyboard_type=ft.KeyboardType.NUMBER,
                width=145,
                visible=self.mode_field.value == "manual",
                on_change=lambda e: self._refresh_preview(),
            )
            self.manual_fields[expense_id] = field
            source = row.get("service_type") or row.get("source_type") or "قيد"
            ref = row.get("source_ref") or f"#{expense_id}"
            due = row.get("payment_due_date") or row.get("date") or "—"
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(f"{source} · {ref}", weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(f"{row.get('person_name') or row.get('company_name')} · الاستحقاق {due}", size=10, color=MUTED),
                    ], spacing=2, expand=True),
                    ft.Column([
                        ft.Text(currency.format_amount_ui(remaining, code), weight=ft.FontWeight.BOLD, color=WARNING),
                        ft.Text("المتبقي", size=9, color=MUTED),
                    ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.END),
                    field,
                ], spacing=9, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                border=ft.border.all(1, BORDER), border_radius=10, padding=9,
            ))
        self.claims_host.controls = controls or [ft.Text("لا توجد مطالبات لهذا الطرف", color=MUTED)]
        total = sum(float(row.get("remaining_amount_original") or 0) for row in self.claims)
        self.amount_field.value = f"{total:.2f}" if total > 0 else ""
        self._refresh_preview()

    def _manual_allocations(self):
        allocations = []
        for expense_id, field in self.manual_fields.items():
            amount = parse_non_negative_amount(field.value)
            if amount > 0:
                allocations.append({"expense_id": expense_id, "amount": amount})
        return allocations

    def _refresh_preview(self):
        scope = self._selected_scope()
        if not scope:
            self.preview_text.value = "اختر الطرف"
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
        except Exception:
            amount = 0.0
        outstanding = sum(float(row.get("remaining_amount_original") or 0) for row in self.claims)
        if self.mode_field.value == "manual":
            try:
                allocated = sum(item["amount"] for item in self._manual_allocations())
            except Exception:
                allocated = 0.0
        else:
            allocated = min(amount, outstanding)
        credit = max(0.0, amount - allocated)
        code = scope.get("currency_original") or "USD"
        credit_label = "رصيد دائن" if scope.get("direction") == "received" else "دفعة مقدمة"
        self.preview_text.value = (
            f"مبلغ الدفعة {currency.format_amount_ui(amount, code)} · "
            f"سيُوزع {currency.format_amount_ui(allocated, code)} · "
            f"{credit_label} {currency.format_amount_ui(credit, code)}"
        )

    def _save(self, e=None):
        if self._saving:
            return
        scope = self._selected_scope()
        if not scope:
            show_snackbar(self._page, "اختر الطرف", True)
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
            if amount <= 0:
                raise ValueError("مبلغ الدفعة يجب أن يكون أكبر من صفر")
            date = self.payment_date.require_value("تاريخ الدفعة")
            allocations = self._manual_allocations() if self.mode_field.value == "manual" else []
            if self.mode_field.value == "manual" and sum(item["amount"] for item in allocations) > amount + 0.005:
                raise ValueError("مجموع التوزيع اليدوي أكبر من مبلغ الدفعة")
        except Exception as ex:
            show_snackbar(self._page, str(ex), True)
            return
        payload = {
            "company_name": scope["company_name"],
            "person_name": scope.get("person_name") or "",
            "direction": scope["direction"],
            "currency_original": scope["currency_original"],
            "amount": amount,
            "date": date,
            "payment_method": self.method_field.value or "cash",
            "reference_number": self.reference_field.value or "",
            "notes": self.notes_field.value or "",
            "allocation_mode": self.mode_field.value or "oldest",
            "allocations": allocations,
        }
        self._saving = True
        set_button_busy(self.save_btn, True, "تسجيل وتوزيع الدفعة", "جارٍ التوزيع...")
        self._safe_update()
        run_async_task(self._page, self._save_async, payload)

    async def _save_async(self, payload):
        try:
            result = await asyncio.to_thread(lambda: self.repo.add(payload))
            credit = float(result.get("credit_amount_original") or 0)
            message = "تم تسجيل الدفعة وتوزيعها"
            if credit > 0.005:
                code = result.get("currency_original") or "USD"
                message += f"، وحُفظ {currency.format_amount_ui(credit, code)} كرصيد للطرف"
            show_snackbar(self._page, message, False)
            self._close()
            if self.on_save:
                self.on_save(result)
        except Exception as ex:
            show_snackbar(self._page, f"فشل تسجيل الدفعة المجمعة: {ex}", True)
            self._saving = False
            set_button_busy(self.save_btn, False, "تسجيل وتوزيع الدفعة")
            self._safe_update()

    def _safe_update(self):
        try:
            self._page.update()
        except Exception:
            pass

    def _close(self):
        try:
            self.payment_date.close()
        except Exception:
            pass
        close_control(self._page, self)


class BatchPaymentHistoryDialog(ft.AlertDialog):
    def __init__(self, page, on_change=None):
        super().__init__()
        self._page = page
        self.on_change = on_change
        self.repo = BatchPaymentRepository()
        width = min(max(float(getattr(page, "width", 420) or 420) - 32, 330), 700)
        self.host = ft.Column(spacing=8)
        self.title = dialog_title("سجل الدفعات المجمعة", ft.Icons.HISTORY_OUTLINED)
        self.content = dialog_body([self.host], width=width, height=560, spacing=10)
        self.actions = [cancel_button("إغلاق", lambda e: close_control(page, self))]
        self._load()

    def _load(self):
        try:
            rows = self.repo.list_recent(80)
        except Exception as ex:
            self.host.controls = [ft.Text(f"تعذر تحميل السجل: {ex}", color=DANGER)]
            return
        if not rows:
            self.host.controls = [ft.Text("لا توجد دفعات مجمعة", color=MUTED)]
            return
        can_delete = (UserSession.get_current() or {}).get("role") in {"admin", "manager", "accountant"}
        controls = []
        for row in rows:
            code = row.get("currency_original") or "USD"
            direction = "قبض" if row.get("direction") == "received" else "دفع"
            credit_label = "رصيد" if row.get("direction") == "received" else "مقدم"
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=PRIMARY),
                    ft.Column([
                        ft.Text(f"{direction} · {row.get('company_name')}", weight=ft.FontWeight.BOLD),
                        ft.Text(f"{row.get('person_name') or 'كل المطالبات'} · {row.get('date')} · {row.get('reference')}", size=10, color=MUTED),
                        ft.Text(
                            f"المبلغ {currency.format_amount_ui(float(row.get('amount_original') or 0), code)} · "
                            f"الموزع {currency.format_amount_ui(float(row.get('allocated_amount_original') or 0), code)} · "
                            f"{credit_label} {currency.format_amount_ui(float(row.get('credit_amount_original') or 0), code)}",
                            size=11,
                        ),
                    ], spacing=2, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=DANGER,
                        tooltip="حذف الدفعة المجمعة",
                        visible=can_delete,
                        on_click=lambda e, batch=dict(row): self._confirm_delete(batch),
                    ),
                ], spacing=8),
                border=ft.border.all(1, BORDER), border_radius=10, padding=9,
            ))
        self.host.controls = controls

    def _confirm_delete(self, batch):
        reason = ft.TextField(label="سبب حذف الدفعة المجمعة", multiline=True, min_lines=2, max_lines=3)
        dlg = None

        def confirm(e=None):
            clean = str(reason.value or "").strip()
            if not clean:
                show_snackbar(self._page, "سبب الحذف مطلوب", True)
                return
            try:
                self.repo.delete(int(batch["id"]), reason=clean)
                close_control(self._page, dlg)
                self._load()
                self._page.update()
                if self.on_change:
                    self.on_change()
                show_snackbar(self._page, "تم حذف الدفعة المجمعة وإعادة احتساب المطالبات", False)
            except Exception as ex:
                show_snackbar(self._page, f"فشل الحذف: {ex}", True)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("حذف دفعة مجمعة", color=DANGER, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text("سيتم حذف جميع توزيعات هذه الدفعة. لا يمكن الحذف إذا استُخدم الرصيد الدائن."),
                reason,
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("حذف", on_click=confirm, style=ft.ButtonStyle(color=DANGER)),
                ft.TextButton("إلغاء", on_click=lambda e: close_control(self._page, dlg)),
            ],
        )
        open_control(self._page, dlg)
