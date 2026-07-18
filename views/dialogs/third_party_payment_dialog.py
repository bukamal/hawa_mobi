# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import flet as ft
from views.ui_kit import PRIMARY, PRIMARY_SOFT

from auth.session import UserSession
from currency import currency
from database import ThirdPartyPaymentRepository
from i18n.translator import translate
from views.flet_compat import close_control, ALIGN_CENTER
from views.financial_date_field import FinancialDateField
from views.searchable_field import SearchableTextField
from services.form_suggestions_service import list_company_names
from views.dialogs.dialog_kit import (
    dialog_title,
    dialog_body,
    cancel_button,
    save_button,
    show_snackbar,
    set_button_busy,
    normalize_text,
    parse_non_negative_amount,
)


class ThirdPartyPaymentDialog(ft.AlertDialog):
    """Mobile dialog for: شركة سدّدت عني لشركة أخرى."""

    def __init__(self, page, on_save=None, payer_company_name=None, paid_to_company_name=None, payment=None, reference=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        if payment is None and reference:
            payment = ThirdPartyPaymentRepository().get_by_reference(reference)
        self.payment = dict(payment or {})
        self.edit_mode = bool(self.payment.get("reference"))
        self.reference = self.payment.get("reference") or reference

        page_width = self._page.width or 400
        page_height = self._page.height or 650
        dialog_width = min(390, page_width - 36)
        dialog_height = min(540, page_height - 90)

        self.payer_field = SearchableTextField(
            label=translate("payer_company"),
            value=self.payment.get("payer_company_name") or payer_company_name or "",
            width=dialog_width - 20,
            hint_text="ابحث عن الشركة التي سدّدت أو اكتب اسمها",
            suggestions_provider=list_company_names,
        )
        self.paid_to_field = SearchableTextField(
            label=translate("paid_to_company"),
            value=self.payment.get("paid_to_company_name") or paid_to_company_name or "",
            disabled=(bool(paid_to_company_name) and not self.edit_mode),
            width=dialog_width - 20,
            hint_text="ابحث عن الشركة المدفوع لها أو اكتب اسمها",
            suggestions_provider=list_company_names,
        )
        self.amount_field = ft.TextField(
            label=translate("amount"),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=dialog_width - 150,
            value=str(self.payment.get("amount_original") or ""),
        )
        self.currency_dropdown = ft.Dropdown(
            label=translate("currency"),
            value=self.payment.get("currency_original") or currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD", "SAR", "SYP", "EUR", "GBP", "AED", "QAR", "KWD", "OMR"]],
            width=120,
        )
        self.operation_date = FinancialDateField(
            self._page,
            label="تاريخ السداد",
            value=self.payment.get("date"),
            width=dialog_width - 20,
        )
        self.date_field = self.operation_date.field
        self.notes_field = ft.TextField(
            label=translate("notes"),
            multiline=True,
            min_lines=2,
            max_lines=4,
            value=self.payment.get("notes") or "",
            width=dialog_width - 20,
        )
        self.edit_reason_field = ft.TextField(
            label="سبب التعديل",
            hint_text="مثال: تصحيح مبلغ السداد أو تاريخ العملية",
            multiline=True,
            min_lines=1,
            max_lines=3,
            width=dialog_width - 20,
            visible=self.edit_mode,
        )
        self.exchange_rate_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        self.preview_text = ft.Text("", size=12, color=PRIMARY, weight=ft.FontWeight.BOLD)
        self.preview_box = ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.SWAP_HORIZ, size=18, color=PRIMARY), ft.Text(translate("preview"), weight=ft.FontWeight.BOLD, size=13)]),
                self.preview_text,
                ft.Text("لا يتم لمس الصندوق أو البنك؛ يتم فقط نقل الذمة من شركة إلى شركة.", size=11, color=ft.Colors.GREY_600),
            ], spacing=6),
            bgcolor=PRIMARY_SOFT,
            border_radius=12,
            padding=10,
        )

        self.save_btn = save_button("حفظ التعديل" if self.edit_mode else translate("save"), self._save)
        self.title = dialog_title("تعديل سداد بالنيابة" if self.edit_mode else translate("third_party_payment"), ft.Icons.SWAP_HORIZ)
        self.content = dialog_body(
            controls=[
                ft.Text("سيتم تعديل القيدين المرتبطين معاً داخل عملية واحدة، ولا يمكن تعديل قيد منفرد." if self.edit_mode else "شركة دفعت عنك لشركة أخرى؛ التطبيق ينشئ قيدين متوازنين تلقائياً.", size=12, color=ft.Colors.GREY_600),
                self.payer_field,
                self.paid_to_field,
                ft.Row([self.amount_field, self.currency_dropdown], spacing=10, wrap=True),
                self.operation_date,
                ft.Container(content=self.exchange_rate_text, alignment=ALIGN_CENTER),
                self.preview_box,
                self.notes_field,
                self.edit_reason_field,
            ],
            spacing=14,
            width=dialog_width - 10,
            height=dialog_height - 105,
        )
        self.actions = [cancel_button(translate("cancel"), lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=15)

        self.amount_field.on_change = self._update_preview
        self.currency_dropdown.on_change = self._update_preview
        self.payer_field.on_change = self._update_preview
        self.paid_to_field.on_change = self._update_preview
        self._update_preview(None)

    def _close(self):
        try:
            self.operation_date.close()
        except Exception:
            pass
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _update_preview(self, e):
        payer = normalize_text(self.payer_field.value) or "الشركة التي سدّدت عني"
        paid_to = normalize_text(self.paid_to_field.value) or "الشركة التي تم السداد لها"
        code = self.currency_dropdown.value or currency.get_display_currency()
        try:
            amount = float(str(self.amount_field.value or "0").replace(",", "."))
        except Exception:
            amount = 0.0
        try:
            rate = currency.get_rate_to_usd(code)
            display_curr = currency.get_display_currency()
            base_usd = amount / rate if rate else amount
            display_amount = currency.convert(base_usd, "USD", display_curr)
            self.exchange_rate_text.value = f"المخزّن محاسبياً: {base_usd:.4f} USD | المعروض: {currency.format_amount(display_amount, display_curr)}"
        except Exception:
            self.exchange_rate_text.value = ""
        amount_str = currency.format_amount(amount, code) if amount else "—"
        self.preview_text.value = f"{translate('will_decrease_paid_to')}: {paid_to} بمبلغ {amount_str}\n{translate('will_increase_payer')}: {payer} بمبلغ {amount_str}"
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        payer = normalize_text(self.payer_field.value)
        paid_to = normalize_text(self.paid_to_field.value)
        if not payer:
            self._show_snackbar("الشركة التي سدّدت عني مطلوبة", True)
            return
        if not paid_to:
            self._show_snackbar("الشركة التي تم السداد لها مطلوبة", True)
            return
        if payer == paid_to:
            self._show_snackbar(translate("cannot_same_company"), True)
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
        except Exception as ex:
            self._show_snackbar(str(ex), True)
            return
        if amount <= 0:
            self._show_snackbar("المبلغ يجب أن يكون أكبر من صفر", True)
            return
        try:
            operation_date = self.operation_date.require_value("تاريخ السداد")
        except Exception as ex:
            self._show_snackbar(str(ex), True)
            return
        user = UserSession.get_current() or {}
        user_id = user.get("id") or 1
        self._saving = True
        set_button_busy(self.save_btn, True, translate("save"))
        try:
            repo = ThirdPartyPaymentRepository()
            if self.edit_mode:
                reason = normalize_text(self.edit_reason_field.value)
                if not reason:
                    self._show_snackbar("سبب تعديل العملية مطلوب", True)
                    return
                result = repo.update_payment_on_behalf(
                    reference=self.reference,
                    payer_company_name=payer,
                    paid_to_company_name=paid_to,
                    amount=amount,
                    currency_code=self.currency_dropdown.value,
                    date=operation_date,
                    notes=self.notes_field.value or "",
                    edit_reason=reason,
                    user_id=user_id,
                )
            else:
                result = repo.add_payment_on_behalf(
                    payer_company_name=payer,
                    paid_to_company_name=paid_to,
                    amount=amount,
                    currency_code=self.currency_dropdown.value,
                    date=operation_date,
                    notes=self.notes_field.value or "",
                    user_id=user_id,
                )
            self.operation_date.remember()
            self._close()
            if self.on_save:
                self.on_save(result)
            msg = "تم تعديل عملية السداد بالنيابة" if self.edit_mode else translate('payment_on_behalf_saved')
            self._show_snackbar(f"{msg} | {result.get('reference', '')}", False)
        except Exception as ex:
            self._show_snackbar(f"فشل الحفظ: {str(ex)}", True)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, translate("save"))
            try:
                self._page.update()
            except Exception:
                pass
