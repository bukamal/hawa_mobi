# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import traceback

import flet as ft

from auth.session import UserSession
from currency import currency
from database import DirectServiceRepository
from services.ledger_operation_service import SERVICE_TYPES
from services.direct_customer_service import validate_direct_service_payload
from views.flet_compat import close_control, run_async_task
from views.financial_date_field import FinancialDateField
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


class DirectServiceDialog(ft.AlertDialog):
    """Create a direct customer service with profit tracking.

    This is intentionally separate from a normal ledger entry: a normal entry
    affects receivables only, while this workflow stores sale, cost and profit.
    """

    def __init__(self, page, on_save=None, company_name=None, service=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        self.service = dict(service or {})
        self.reference = (self.service.get("reference") or "").strip()
        self.is_edit = bool(self.reference)
        page_width = page.width or 400
        page_height = page.height or 650
        dialog_width = min(390, page_width - 32)
        dialog_height = min(570, page_height - 90)

        default_service = "تذكرة سفر" if "تذكرة سفر" in SERVICE_TYPES else ("تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "أخرى")
        self.company_field = ft.TextField(label="الشركة / الحساب", value=self.service.get("company_name") or company_name or "", width=dialog_width - 20, hint_text="مثال: أبو تيم")
        self.person_field = ft.TextField(label="اسم الزبون / المسافر", value=self.service.get("person_name") or "", width=dialog_width - 20, hint_text="مثال: أحمد محمد")
        self.service_dropdown = ft.Dropdown(label="نوع الخدمة", value=self.service.get("service_type") or default_service, options=[ft.dropdown.Option(s) for s in SERVICE_TYPES], width=dialog_width - 20)
        self.sale_field = ft.TextField(label="سعر البيع على الزبون", value=str(self.service.get("sale_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20)
        self.cost_field = ft.TextField(label="التكلفة الداخلية / تكلفة المورد", value=str(self.service.get("cost_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20, hint_text="اتركها 0 إذا لم توجد تكلفة")
        self.supplier_field = ft.TextField(label="المورد / حساب التكلفة (اختياري)", value=self.service.get("supplier_company_name") or "", width=dialog_width - 20, hint_text="إذا أُدخل مع تكلفة، ينشئ قيدًا له على المورد")
        self.currency_dropdown = ft.Dropdown(label="العملة", value=self.service.get("currency_original") or currency.get_display_currency(), options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]], width=120)
        self.operation_date = FinancialDateField(page, label="تاريخ الخدمة المباشرة", value=self.service.get("date"), width=dialog_width - 20)
        self.notes_field = ft.TextField(label="ملاحظات", value=self.service.get("notes") or "", multiline=True, min_lines=2, max_lines=3, width=dialog_width - 20)
        self.profit_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)
        self.edit_reason_field = ft.TextField(label="سبب التعديل", multiline=True, min_lines=2, max_lines=3, width=dialog_width - 20, visible=self.is_edit, hint_text="مثال: تصحيح سعر البيع أو المورد")
        self.info_text = ft.Text(
            "الخدمة المباشرة تنشئ/تحدّث قيودًا مقفلة مترابطة وتخزن البيع والتكلفة والربح داخليًا. التعديل يتم على العملية الأصلية وليس على القيد المنفرد.",
            size=12,
            color=ft.Colors.GREY_700,
        )
        self.error_text = ft.Text("", size=12, color=ft.Colors.RED, selectable=True)
        self.error_box = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=18), self.error_text], spacing=8),
            bgcolor=ft.Colors.RED_50,
            border_radius=10,
            padding=10,
            visible=False,
        )
        self.save_btn = save_button("حفظ التعديل" if self.is_edit else "إنشاء خدمة مباشرة", self._save)
        for fld in (self.sale_field, self.cost_field):
            fld.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        self.title = dialog_title("تعديل خدمة مباشرة" if self.is_edit else "خدمة مباشرة / ربح زبون", ft.Icons.PERSON_ADD_ALT)
        self.content = dialog_body([
            self.info_text,
            self.error_box,
            self.company_field,
            self.person_field,
            self.service_dropdown,
            ft.Row([self.sale_field, self.currency_dropdown], spacing=10, wrap=True),
            self.cost_field,
            self.supplier_field,
            self.operation_date,
            self.profit_text,
            self.notes_field,
            self.edit_reason_field,
        ], width=dialog_width - 10, height=dialog_height - 100)
        self.actions = [cancel_button("إلغاء", lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=16)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _close(self):
        try:
            self.operation_date.close()
        except Exception:
            pass
        close_control(self._page, self)

    def _show_inline_error(self, message: str):
        self.error_text.value = str(message or "حدث خطأ غير معروف")
        self.error_box.visible = True
        try:
            self._page.update()
        except Exception:
            pass

    def _clear_inline_error(self):
        self.error_text.value = ""
        self.error_box.visible = False

    def _update_profit(self, e):
        try:
            sale = parse_non_negative_amount(self.sale_field.value or 0)
            cost = parse_non_negative_amount(self.cost_field.value or 0)
            code = self.currency_dropdown.value or currency.get_display_currency()
            profit = sale - cost
            self.profit_text.value = f"البيع: {currency.format_amount(sale, code)} · التكلفة: {currency.format_amount(cost, code)} · الربح: {currency.format_amount(profit, code)}"
            self.profit_text.color = ft.Colors.GREEN if profit >= 0 else ft.Colors.RED
        except Exception:
            self.profit_text.value = ""
        try:
            self._page.update()
        except Exception:
            pass

    def _build_payload(self):
        payload = {
            "company_name": normalize_text(self.company_field.value),
            "person_name": normalize_text(self.person_field.value),
            "service_type": self.service_dropdown.value or "خدمة",
            "sale_amount_original": self.sale_field.value,
            "cost_amount_original": self.cost_field.value or 0,
            "supplier_company_name": normalize_text(self.supplier_field.value),
            "currency_original": self.currency_dropdown.value,
            "date": self.operation_date.require_value("تاريخ الخدمة المباشرة"),
            "notes": self.notes_field.value or "",
        }
        return validate_direct_service_payload(payload)

    def _set_busy(self, busy: bool):
        self._saving = bool(busy)
        set_button_busy(self.save_btn, busy, "حفظ التعديل" if self.is_edit else "إنشاء خدمة مباشرة", busy_label="جارٍ حفظ التعديل..." if self.is_edit else "جارٍ إنشاء الخدمة...")
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_inline_error("ليست لديك صلاحية إنشاء خدمة مباشرة")
            self._show_snackbar("ليست لديك صلاحية إنشاء خدمة مباشرة", True)
            return
        self._clear_inline_error()
        try:
            payload = self._build_payload()
        except Exception as ex:
            self._show_inline_error(str(ex))
            self._show_snackbar(str(ex), True)
            return
        self._set_busy(True)
        run_async_task(self._page, self._save_async, payload)

    async def _save_async(self, payload):
        try:
            if self.is_edit:
                reason = normalize_text(self.edit_reason_field.value)
                if not reason:
                    raise ValueError("سبب تعديل الخدمة المباشرة مطلوب")
                result = await asyncio.to_thread(lambda: DirectServiceRepository().update(self.reference, payload, edit_reason=reason))
            else:
                result = await asyncio.to_thread(lambda: DirectServiceRepository().add(payload))
        except Exception as ex:
            details = str(ex) or ex.__class__.__name__
            try:
                print(f"[direct-service-save-error] {details}\n{traceback.format_exc()}", flush=True)
            except Exception:
                pass
            self._show_inline_error(f"فشل حفظ الخدمة المباشرة: {details}")
            self._show_snackbar(f"فشل حفظ الخدمة المباشرة: {details}", True)
            self._set_busy(False)
            return
        self._set_busy(False)
        self.operation_date.remember()
        self._close()
        refresh_error = None
        if self.on_save:
            try:
                self.on_save(result)
            except Exception as ex:
                refresh_error = str(ex) or ex.__class__.__name__
        if refresh_error:
            self._show_snackbar(f"تم حفظ الخدمة المباشرة، لكن تعذر تحديث الشاشة: {refresh_error}", True)
        else:
            self._show_snackbar(("تم تعديل الخدمة المباشرة" if self.is_edit else "تم إنشاء الخدمة المباشرة") + f": {result.get('reference')}", False)
