# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import traceback

import flet as ft

from auth.session import UserSession
from currency import currency
from database import DirectServiceRepository
from services.direct_customer_service import validate_direct_service_payload
from services.form_suggestions_service import list_company_names, list_person_names
from services.ledger_operation_service import SERVICE_TYPES
from views.design_system.tokens import (
    BRAND_PRIMARY,
    BRAND_PRIMARY_LIGHT,
    FINANCIAL_PAYABLE,
    FINANCIAL_RECEIVABLE,
    LIGHT_TEXT_SECONDARY,
    STATE_DANGER,
    STATE_SUCCESS,
)
from views.design_system.workflow import (
    WorkflowController,
    WorkflowStep,
    adaptive_dialog_metrics,
    financial_summary,
    review_row,
    section_card,
)
from views.dialogs.dialog_kit import dialog_title, normalize_text, parse_non_negative_amount, show_snackbar
from views.financial_date_field import FinancialDateField
from views.flet_compat import close_control, run_async_task
from views.searchable_field import SearchableTextField


_CURRENCIES = ["USD", "SAR", "SYP", "EUR", "GBP", "AED", "QAR", "KWD", "OMR"]


class DirectServiceDialog(ft.AlertDialog):
    """Adaptive three-step direct-service workflow.

    The accounting contract is unchanged.  Only the presentation is split into
    clear steps so the form remains usable on small Android screens.
    """

    def __init__(self, page, on_save=None, company_name=None, service=None, supplier_company_name=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        self.service = dict(service or {})
        self.reference = (self.service.get("reference") or "").strip()
        self.is_edit = bool(self.reference)
        self.supplier_locked_name = (supplier_company_name or "").strip()
        if self.is_edit and not self.supplier_locked_name and not self.service.get("client_expense_id") and self.service.get("supplier_company_name"):
            self.supplier_locked_name = str(self.service.get("supplier_company_name") or self.service.get("company_name") or "").strip()
        self.supplier_only_mode = bool(self.supplier_locked_name)

        dialog_width, dialog_height, inset, radius = adaptive_dialog_metrics(page, max_width=680, max_height=720)
        field_width = max(280, dialog_width - 44)
        half_width = max(132, (field_width - 12) / 2)

        default_service = "تذكرة سفر" if "تذكرة سفر" in SERVICE_TYPES else ("تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "أخرى")
        self.company_field = SearchableTextField(
            label="الشركة / الحساب",
            value=self.service.get("company_name") or company_name or "",
            width=field_width,
            hint_text="ابحث عن شركة أو اكتب اسمًا جديدًا",
            suggestions_provider=list_company_names,
        )
        person_suggestions_company = lambda: self.supplier_locked_name if self.supplier_only_mode else self.company_field.value
        self.person_field = SearchableTextField(
            label="اسم الزبون / المسافر",
            value=self.service.get("person_name") or "",
            width=field_width,
            hint_text="ابحث عن زبون سابق أو اكتب اسمًا جديدًا",
            suggestions_provider=lambda: list_person_names(person_suggestions_company()),
        )
        self.service_dropdown = ft.Dropdown(
            label="نوع الخدمة",
            value=self.service.get("service_type") or default_service,
            options=[ft.dropdown.Option(s) for s in SERVICE_TYPES],
            width=field_width,
            filled=True,
            border_radius=10,
        )
        self.sale_field = ft.TextField(
            label="سعر البيع على الزبون",
            value=str(self.service.get("sale_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            prefix_icon=ft.Icons.SELL_OUTLINED,
            filled=True,
            border_radius=10,
        )
        self.currency_dropdown = ft.Dropdown(
            label="العملة",
            value=self.service.get("currency_original") or currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in _CURRENCIES],
            width=half_width,
            filled=True,
            border_radius=10,
        )
        self.cost_field = ft.TextField(
            label="تكلفة المورد",
            value=str(self.service.get("cost_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            hint_text="المبلغ المستحق للمورد",
            prefix_icon=ft.Icons.RECEIPT_LONG_OUTLINED,
            filled=True,
            border_radius=10,
        )
        self.supplier_field = SearchableTextField(
            label="المورد / حساب التكلفة (اختياري)",
            value=self.service.get("supplier_company_name") or "",
            width=field_width,
            hint_text="ابحث عن مورد سابق أو اكتب اسمًا جديدًا",
            suggestions_provider=list_company_names,
        )
        self.supplier_badge = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.BUSINESS_CENTER_OUTLINED, color=BRAND_PRIMARY, size=19),
                    ft.Column(
                        [
                            ft.Text("المورد المحدد", size=11, color=LIGHT_TEXT_SECONDARY),
                            ft.Text(self.supplier_locked_name or "—", weight=ft.FontWeight.BOLD, color=BRAND_PRIMARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=BRAND_PRIMARY_LIGHT,
            border_radius=14,
            padding=12,
            visible=self.supplier_only_mode,
        )
        self.company_field.visible = not self.supplier_only_mode
        self.supplier_field.visible = not self.supplier_only_mode

        self.operation_date = FinancialDateField(page, label="تاريخ الخدمة المباشرة", value=self.service.get("date"), width=field_width)
        self.notes_field = ft.TextField(
            label="ملاحظات",
            value=self.service.get("notes") or "",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=field_width,
            filled=True,
            border_radius=10,
        )
        self.edit_reason_field = ft.TextField(
            label="سبب التعديل",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=field_width,
            visible=self.is_edit,
            hint_text="مثال: تصحيح سعر البيع أو المورد",
            filled=True,
            border_radius=10,
        )
        self.profit_text = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=BRAND_PRIMARY)
        self.review_host = ft.Column([], spacing=10)

        info_message = (
            "ستسجل تكلفة الخدمة على المورد المحدد، بينما يبقى البيع والربح ضمن بيانات الخدمة المباشرة."
            if self.supplier_only_mode
            else "تنشئ العملية قيودًا مترابطة وتخزن البيع والتكلفة والربح. لا تعدّل القيود المولدة منفردة."
        )
        self.info_box = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.INFO_OUTLINE, color=BRAND_PRIMARY, size=20), ft.Text(info_message, size=12, color=LIGHT_TEXT_SECONDARY, expand=True)],
                spacing=10,
            ),
            bgcolor=BRAND_PRIMARY_LIGHT,
            border_radius=14,
            padding=12,
        )
        self.error_text = ft.Text("", size=12, color=STATE_DANGER, selectable=True, expand=True)
        self.error_box = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=STATE_DANGER, size=19), self.error_text], spacing=8),
            bgcolor="#FDECEC",
            border_radius=12,
            padding=10,
            visible=False,
        )

        for field in (self.sale_field, self.cost_field):
            field.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        party_controls = [self.info_box, self.error_box, self.supplier_badge, self.company_field, self.person_field, self.service_dropdown]
        price_controls = [
            ft.Row([self.sale_field, self.currency_dropdown], spacing=12, wrap=True),
            ft.Row([self.cost_field], spacing=12, wrap=True),
            self.supplier_field,
            ft.Container(content=self.profit_text, bgcolor="#F8FAFC", border_radius=12, padding=12),
        ]
        review_controls = [self.review_host, self.operation_date, self.notes_field, self.edit_reason_field]

        submit_label = "حفظ التعديل" if self.is_edit else "إنشاء الخدمة"
        self.workflow = WorkflowController(
            page,
            [
                WorkflowStep(
                    "العميل والخدمة",
                    "حدد الحساب والمسافر ونوع الخدمة.",
                    ft.Icons.PERSON_SEARCH_OUTLINED,
                    [section_card("بيانات الخدمة", party_controls, icon=ft.Icons.BADGE_OUTLINED)],
                ),
                WorkflowStep(
                    "البيع والتكلفة",
                    "أدخل الأسعار وحدد المورد عند الحاجة.",
                    ft.Icons.MONETIZATION_ON_OUTLINED,
                    [section_card("التسعير", price_controls, icon=ft.Icons.PRICE_CHECK_OUTLINED)],
                ),
                WorkflowStep(
                    "المراجعة والحفظ",
                    "راجع الأثر المالي ثم أكمل التاريخ والملاحظات.",
                    ft.Icons.FACT_CHECK_OUTLINED,
                    [section_card("المراجعة النهائية", review_controls, icon=ft.Icons.CHECKLIST_OUTLINED)],
                ),
            ],
            validate_step=self._validate_step,
            before_step=self._before_step,
            on_cancel=lambda e: self._close(),
            on_submit=self._save,
            submit_label=submit_label,
            width=dialog_width - 12,
            height=dialog_height - 76,
        )
        self.save_btn = self.workflow.submit_button

        title_text = (
            "تعديل خدمة مباشرة عبر مورد"
            if self.is_edit and self.supplier_only_mode
            else ("خدمة مباشرة عبر مورد" if self.supplier_only_mode else ("تعديل خدمة مباشرة" if self.is_edit else "خدمة مباشرة"))
        )
        self.modal = True
        self.title = dialog_title(title_text, ft.Icons.ROUTE_OUTLINED)
        self.content = self.workflow.control
        self.actions = []
        self.inset_padding = inset
        self.shape = ft.RoundedRectangleBorder(radius=radius)

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

    def _amounts(self):
        sale = parse_non_negative_amount(self.sale_field.value or 0)
        cost = parse_non_negative_amount(self.cost_field.value or 0)
        return sale, cost

    def _update_profit(self, e):
        try:
            sale, cost = self._amounts()
            code = self.currency_dropdown.value or currency.get_display_currency()
            profit = sale - cost
            self.profit_text.value = (
                f"البيع {currency.format_amount(sale, code)}  ·  "
                f"التكلفة {currency.format_amount(cost, code)}  ·  "
                f"الربح {currency.format_amount(profit, code)}"
            )
            self.profit_text.color = STATE_SUCCESS if profit >= 0 else STATE_DANGER
        except Exception:
            self.profit_text.value = "أدخل مبالغ صحيحة لعرض الربح"
            self.profit_text.color = LIGHT_TEXT_SECONDARY
        try:
            self._page.update()
        except Exception:
            pass

    def _validate_step(self, index: int) -> bool:
        self._clear_inline_error()
        try:
            if index == 0:
                company = self.supplier_locked_name if self.supplier_only_mode else normalize_text(self.company_field.value)
                if not company:
                    raise ValueError("الشركة / الحساب مطلوب")
                if not normalize_text(self.person_field.value):
                    raise ValueError("اسم الزبون / المسافر مطلوب")
                if not self.service_dropdown.value:
                    raise ValueError("نوع الخدمة مطلوب")
            elif index == 1:
                sale, cost = self._amounts()
                if sale <= 0:
                    raise ValueError("سعر البيع يجب أن يكون أكبر من صفر")
                supplier = self.supplier_locked_name if self.supplier_only_mode else normalize_text(self.supplier_field.value)
                company = self.supplier_locked_name if self.supplier_only_mode else normalize_text(self.company_field.value)
                if supplier and supplier == company and not self.supplier_only_mode:
                    raise ValueError("لا يمكن أن يكون حساب المورد هو نفس حساب العميل")
                if cost > sale:
                    # Warning, not a hard block.  Keep it visible for the review step.
                    self._show_snackbar("تنبيه: تكلفة الخدمة أعلى من سعر البيع", True)
            return True
        except Exception as ex:
            self._show_inline_error(str(ex))
            self._show_snackbar(str(ex), True)
            return False

    def _before_step(self, index: int):
        if index != 2:
            return
        try:
            sale, cost = self._amounts()
        except Exception:
            sale, cost = 0.0, 0.0
        code = self.currency_dropdown.value or currency.get_display_currency()
        profit = sale - cost
        company = self.supplier_locked_name if self.supplier_only_mode else normalize_text(self.company_field.value)
        supplier = self.supplier_locked_name if self.supplier_only_mode else normalize_text(self.supplier_field.value)
        self.review_host.controls = [
            financial_summary(
                "الأثر المالي المتوقع",
                [
                    ("سعر البيع", currency.format_amount(sale, code), FINANCIAL_RECEIVABLE),
                    ("تكلفة المورد", currency.format_amount(cost, code), FINANCIAL_PAYABLE),
                    ("الربح", currency.format_amount(profit, code), STATE_SUCCESS if profit >= 0 else STATE_DANGER),
                ],
                tone_color=STATE_SUCCESS if profit >= 0 else STATE_DANGER,
            ),
            section_card(
                "ملخص العملية",
                [
                    review_row("الحساب", company, icon=ft.Icons.BUSINESS_OUTLINED),
                    review_row("المسافر", normalize_text(self.person_field.value), icon=ft.Icons.PERSON_OUTLINE),
                    review_row("الخدمة", self.service_dropdown.value or "—", icon=ft.Icons.CARD_TRAVEL_OUTLINED),
                    review_row("المورد", supplier or "تكلفة داخلية بلا قيد مورد", icon=ft.Icons.LOCAL_SHIPPING_OUTLINED),
                ],
                icon=ft.Icons.SUMMARIZE_OUTLINED,
            ),
        ]

    def _build_payload(self):
        if self.supplier_only_mode:
            company_name = normalize_text(self.supplier_locked_name)
            supplier_name = company_name
        else:
            company_name = normalize_text(self.company_field.value)
            supplier_name = normalize_text(self.supplier_field.value)
        payload = {
            "company_name": company_name,
            "person_name": normalize_text(self.person_field.value),
            "service_type": self.service_dropdown.value or "خدمة",
            "sale_amount_original": self.sale_field.value,
            "cost_amount_original": self.cost_field.value or 0,
            "supplier_company_name": supplier_name,
            "currency_original": self.currency_dropdown.value,
            "date": self.operation_date.require_value("تاريخ الخدمة المباشرة"),
            "notes": self.notes_field.value or "",
            "supplier_only": self.supplier_only_mode,
        }
        return validate_direct_service_payload(payload)

    def _set_busy(self, busy: bool):
        self._saving = bool(busy)
        self.workflow.set_busy(
            busy,
            busy_label="جارٍ حفظ التعديل..." if self.is_edit else "جارٍ إنشاء الخدمة...",
        )

    def _save(self, e):
        if self._saving:
            return
        if UserSession.get_current() and UserSession.get_current().get("role") == "viewer":
            self._show_inline_error("ليست لديك صلاحية إنشاء خدمة مباشرة")
            self._show_snackbar("ليست لديك صلاحية إنشاء خدمة مباشرة", True)
            return
        self._clear_inline_error()
        try:
            payload = self._build_payload()
            if self.is_edit and not normalize_text(self.edit_reason_field.value):
                raise ValueError("سبب تعديل الخدمة المباشرة مطلوب")
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
