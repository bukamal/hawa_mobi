# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import traceback

import flet as ft

from auth.session import UserSession
from currency import currency
from database import ServiceCaseRepository
from services.form_suggestions_service import list_company_names, list_person_names
from services.ledger_operation_service import SERVICE_TYPES
from services.service_case_service import validate_service_case_payload
from views.design_system.tokens import (
    BRAND_PRIMARY,
    BRAND_PRIMARY_LIGHT,
    FINANCIAL_PAYABLE,
    FINANCIAL_RECEIVABLE,
    LIGHT_TEXT_SECONDARY,
    STATE_DANGER,
    STATE_SUCCESS,
    STATE_WARNING,
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


class ServiceCaseDialog(ft.AlertDialog):
    """Adaptive four-step intermediary-service workflow.

    The database payload and linked-ledger behavior remain identical to Phase 99.
    The form is split so no phone screen is overloaded with all supplier and
    pricing fields at the same time.
    """

    def __init__(self, page, on_save=None, client_company_name=None, supplier_company_name=None, service_case=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        self.service_case = dict(service_case or {})
        self.reference = (self.service_case.get("reference") or "").strip()
        self.is_edit = bool(self.reference)

        dialog_width, dialog_height, inset, radius = adaptive_dialog_metrics(page, max_width=720, max_height=760)
        field_width = max(280, dialog_width - 44)
        half_width = max(132, (field_width - 12) / 2)

        existing_components = list(self.service_case.get("components") or [])

        def component_by_kind(kind: str):
            for component in existing_components:
                service_type = str(component.get("service_type") or "")
                if kind == "embassy" and ("سفارة" in service_type or "رسوم" in service_type):
                    return component
                if kind == "transport" and ("نقل" in service_type or "transport" in service_type.lower()):
                    return component
            return None

        embassy_component = component_by_kind("embassy") or {}
        transport_component = component_by_kind("transport") or {}
        base_component = {}
        for component in existing_components:
            if component is not embassy_component and component is not transport_component:
                base_component = component
                break
        if not base_component and existing_components:
            base_component = existing_components[0]

        self.client_field = SearchableTextField(
            label="الشركة العميلة",
            value=self.service_case.get("client_company_name") or client_company_name or "",
            width=field_width,
            hint_text="ابحث عن شركة عميلة أو اكتب اسمًا جديدًا",
            suggestions_provider=list_company_names,
        )
        self.person_field = SearchableTextField(
            label="اسم الزبون / المسافر",
            value=self.service_case.get("person_name") or "",
            width=field_width,
            hint_text="ابحث عن زبون سابق أو اكتب اسمًا جديدًا",
            suggestions_provider=lambda: list_person_names(self.client_field.value),
        )
        default_service = "تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "فيزا"
        self.service_dropdown = ft.Dropdown(
            label="نوع الخدمة الأساسية",
            value=base_component.get("service_type") or self.service_case.get("primary_service_type") or self.service_case.get("service_type") or default_service,
            options=[ft.dropdown.Option(s) for s in SERVICE_TYPES],
            width=field_width,
            filled=True,
            border_radius=10,
        )
        self.supplier_field = SearchableTextField(
            label="الشركة المورّدة الأساسية",
            value=base_component.get("supplier_company_name") or self.service_case.get("supplier_company_name") or supplier_company_name or "",
            width=field_width,
            hint_text="ابحث عن شركة مورّدة أو اكتب اسمًا جديدًا",
            suggestions_provider=list_company_names,
        )
        self.sale_field = ft.TextField(
            label="بيع الخدمة الأساسية",
            value=str(base_component.get("sale_amount_original") or (self.service_case.get("sale_amount_original") if not existing_components else "") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            prefix_icon=ft.Icons.SELL_OUTLINED,
            filled=True,
            border_radius=10,
        )
        self.cost_field = ft.TextField(
            label="تكلفة المورد الأساسية",
            value=str(base_component.get("cost_amount_original") or (self.service_case.get("cost_amount_original") if not existing_components else "") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            prefix_icon=ft.Icons.RECEIPT_LONG_OUTLINED,
            filled=True,
            border_radius=10,
        )
        self.currency_dropdown = ft.Dropdown(
            label="العملة",
            value=self.service_case.get("currency_original") or currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in _CURRENCIES],
            width=half_width,
            filled=True,
            border_radius=10,
        )

        self.embassy_supplier_field = SearchableTextField(
            label="حساب السفارة / الرسوم",
            value=embassy_component.get("supplier_company_name") or "",
            width=field_width,
            hint_text="اتركه فارغًا إذا لم توجد رسوم سفارة",
            suggestions_provider=list_company_names,
        )
        self.embassy_sale_field = ft.TextField(
            label="بيع رسوم السفارة",
            value=str(embassy_component.get("sale_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            filled=True,
            border_radius=10,
        )
        self.embassy_cost_field = ft.TextField(
            label="تكلفة رسوم السفارة",
            value=str(embassy_component.get("cost_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            filled=True,
            border_radius=10,
        )
        self.transport_supplier_field = SearchableTextField(
            label="شركة النقل البري",
            value=transport_component.get("supplier_company_name") or "",
            width=field_width,
            hint_text="اتركه فارغًا إذا لم توجد خدمة نقل",
            suggestions_provider=list_company_names,
        )
        self.transport_sale_field = ft.TextField(
            label="بيع النقل",
            value=str(transport_component.get("sale_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            filled=True,
            border_radius=10,
        )
        self.transport_cost_field = ft.TextField(
            label="تكلفة النقل",
            value=str(transport_component.get("cost_amount_original") or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half_width,
            filled=True,
            border_radius=10,
        )

        self.operation_date = FinancialDateField(page, label="تاريخ الخدمة", value=self.service_case.get("date"), width=field_width)
        self.date_field = self.operation_date.field
        self.notes_field = ft.TextField(
            label="ملاحظات داخلية",
            value=self.service_case.get("notes") or "",
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
            hint_text="مثال: تصحيح سعر البيع أو المورد أو بند الخدمة",
            filled=True,
            border_radius=10,
        )
        self.profit_text = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=BRAND_PRIMARY)
        self.review_host = ft.Column([], spacing=10)

        self.info_box = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LINK_OUTLINED, color=BRAND_PRIMARY, size=20),
                    ft.Text(
                        "يحفظ ملف الخدمة كعملية واحدة مترابطة. أي تعديل لاحق يحدّث قيد العميل وجميع قيود الموردين معًا.",
                        size=12,
                        color=LIGHT_TEXT_SECONDARY,
                        expand=True,
                    ),
                ],
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

        for field in (
            self.sale_field,
            self.cost_field,
            self.embassy_sale_field,
            self.embassy_cost_field,
            self.transport_sale_field,
            self.transport_cost_field,
        ):
            field.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        party_step = section_card(
            "العميل والمسافر",
            [self.info_box, self.error_box, self.client_field, self.person_field, self.service_dropdown],
            icon=ft.Icons.GROUP_OUTLINED,
        )
        base_step = section_card(
            "الخدمة الأساسية",
            [
                self.supplier_field,
                ft.Row([self.sale_field, self.cost_field], spacing=12, wrap=True),
                ft.Row([self.currency_dropdown], spacing=12, wrap=True),
                ft.Container(content=self.profit_text, bgcolor="#F8FAFC", border_radius=12, padding=12),
            ],
            icon=ft.Icons.HANDSHAKE_OUTLINED,
            subtitle="المورد وسعر البيع والتكلفة الأساسية.",
        )
        components_step = ft.Column(
            [
                section_card(
                    "رسوم السفارة — اختياري",
                    [self.embassy_supplier_field, ft.Row([self.embassy_sale_field, self.embassy_cost_field], spacing=12, wrap=True)],
                    icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED,
                ),
                section_card(
                    "النقل البري — اختياري",
                    [self.transport_supplier_field, ft.Row([self.transport_sale_field, self.transport_cost_field], spacing=12, wrap=True)],
                    icon=ft.Icons.DIRECTIONS_BUS_OUTLINED,
                ),
            ],
            spacing=12,
        )
        review_step = section_card(
            "المراجعة النهائية",
            [self.review_host, self.operation_date, self.notes_field, self.edit_reason_field],
            icon=ft.Icons.FACT_CHECK_OUTLINED,
        )

        submit_label = "حفظ التعديل" if self.is_edit else "إنشاء ملف الخدمة"
        self.workflow = WorkflowController(
            page,
            [
                WorkflowStep("بيانات العميل", "حدد العميل والمسافر ونوع الخدمة.", ft.Icons.PERSON_SEARCH_OUTLINED, [party_step]),
                WorkflowStep("الخدمة الأساسية", "أدخل المورد والأسعار الأساسية.", ft.Icons.PRICE_CHECK_OUTLINED, [base_step]),
                WorkflowStep("البنود الإضافية", "أضف رسوم السفارة أو النقل عند وجودها.", ft.Icons.ADD_TASK_OUTLINED, [components_step]),
                WorkflowStep("المراجعة والحفظ", "راجع مجموع البيع والتكلفة والربح.", ft.Icons.CHECKLIST_OUTLINED, [review_step]),
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

        self.modal = True
        self.title = dialog_title("تعديل ملف خدمة" if self.is_edit else "ملف خدمة متعدد الموردين", ft.Icons.TRAVEL_EXPLORE_OUTLINED)
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
        sale = (
            parse_non_negative_amount(self.sale_field.value or 0)
            + parse_non_negative_amount(self.embassy_sale_field.value or 0)
            + parse_non_negative_amount(self.transport_sale_field.value or 0)
        )
        cost = (
            parse_non_negative_amount(self.cost_field.value or 0)
            + parse_non_negative_amount(self.embassy_cost_field.value or 0)
            + parse_non_negative_amount(self.transport_cost_field.value or 0)
        )
        return sale, cost

    def _update_profit(self, e):
        try:
            sale, cost = self._amounts()
            code = self.currency_dropdown.value or currency.get_display_currency()
            profit = sale - cost
            self.profit_text.value = (
                f"إجمالي البيع {currency.format_amount(sale, code)}  ·  "
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

    def _optional_component_values(self, supplier_field, sale_field, cost_field):
        supplier = normalize_text(supplier_field.value)
        sale_text = normalize_text(sale_field.value)
        cost_text = normalize_text(cost_field.value)
        sale = parse_non_negative_amount(sale_text or 0)
        cost = parse_non_negative_amount(cost_text or 0)
        active = bool(supplier or sale_text or cost_text)
        return supplier, sale, cost, active

    def _validate_step(self, index: int) -> bool:
        self._clear_inline_error()
        try:
            client = normalize_text(self.client_field.value)
            if index == 0:
                if not client:
                    raise ValueError("الشركة العميلة مطلوبة")
                if not normalize_text(self.person_field.value):
                    raise ValueError("اسم الزبون / المسافر مطلوب")
                if not self.service_dropdown.value:
                    raise ValueError("نوع الخدمة مطلوب")
            elif index == 1:
                supplier = normalize_text(self.supplier_field.value)
                sale = parse_non_negative_amount(self.sale_field.value or 0)
                cost = parse_non_negative_amount(self.cost_field.value or 0)
                if sale == 0 and cost == 0:
                    raise ValueError("أدخل سعر البيع أو تكلفة الخدمة الأساسية")
                if cost > 0 and not supplier:
                    raise ValueError("الشركة المورّدة مطلوبة عند وجود تكلفة")
                if supplier and supplier == client:
                    raise ValueError("لا يمكن أن تكون الشركة العميلة هي المورد نفسه")
            elif index == 2:
                for label, supplier_field, sale_field, cost_field in (
                    ("رسوم السفارة", self.embassy_supplier_field, self.embassy_sale_field, self.embassy_cost_field),
                    ("النقل البري", self.transport_supplier_field, self.transport_sale_field, self.transport_cost_field),
                ):
                    supplier, sale, cost, active = self._optional_component_values(supplier_field, sale_field, cost_field)
                    if not active:
                        continue
                    if sale == 0 and cost == 0:
                        raise ValueError(f"أدخل بيعًا أو تكلفة لبند {label}")
                    if cost > 0 and not supplier and label != "رسوم السفارة":
                        raise ValueError(f"المورد مطلوب لبند {label}")
                    if supplier and supplier == client:
                        raise ValueError(f"لا يمكن أن يكون العميل هو مورد بند {label}")
            return True
        except Exception as ex:
            self._show_inline_error(str(ex))
            self._show_snackbar(str(ex), True)
            return False

    def _before_step(self, index: int):
        if index != 3:
            return
        try:
            sale, cost = self._amounts()
        except Exception:
            sale, cost = 0.0, 0.0
        code = self.currency_dropdown.value or currency.get_display_currency()
        profit = sale - cost
        component_rows = []
        base_supplier = normalize_text(self.supplier_field.value)
        component_rows.append(review_row(self.service_dropdown.value or "الخدمة الأساسية", base_supplier or "—", icon=ft.Icons.HANDSHAKE_OUTLINED))
        embassy_supplier, embassy_sale, embassy_cost, embassy_active = self._optional_component_values(self.embassy_supplier_field, self.embassy_sale_field, self.embassy_cost_field)
        if embassy_active:
            component_rows.append(review_row("رسوم السفارة", embassy_supplier or "رسوم سفارات", icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED))
        transport_supplier, transport_sale, transport_cost, transport_active = self._optional_component_values(self.transport_supplier_field, self.transport_sale_field, self.transport_cost_field)
        if transport_active:
            component_rows.append(review_row("النقل البري", transport_supplier or "—", icon=ft.Icons.DIRECTIONS_BUS_OUTLINED))
        margin_color = STATE_SUCCESS if profit >= 0 else STATE_DANGER
        if sale > 0 and 0 <= profit < sale * 0.1:
            margin_color = STATE_WARNING
        self.review_host.controls = [
            financial_summary(
                "الأثر المالي المتوقع",
                [
                    ("إجمالي البيع على العميل", currency.format_amount(sale, code), FINANCIAL_RECEIVABLE),
                    ("إجمالي المستحق للموردين", currency.format_amount(cost, code), FINANCIAL_PAYABLE),
                    ("الربح الداخلي", currency.format_amount(profit, code), margin_color),
                ],
                tone_color=margin_color,
            ),
            section_card(
                "أطراف العملية",
                [
                    review_row("الشركة العميلة", normalize_text(self.client_field.value), icon=ft.Icons.BUSINESS_OUTLINED),
                    review_row("المسافر", normalize_text(self.person_field.value), icon=ft.Icons.PERSON_OUTLINE),
                    *component_rows,
                ],
                icon=ft.Icons.ACCOUNT_TREE_OUTLINED,
            ),
        ]

    def _build_payload(self):
        components = [
            {
                "service_type": self.service_dropdown.value or "تأشيرة سياحية",
                "supplier_company_name": normalize_text(self.supplier_field.value),
                "sale_amount_original": self.sale_field.value,
                "cost_amount_original": self.cost_field.value,
            }
        ]
        if normalize_text(self.embassy_supplier_field.value) or normalize_text(self.embassy_sale_field.value) or normalize_text(self.embassy_cost_field.value):
            components.append(
                {
                    "service_type": "سفارة / رسوم سفارة",
                    "supplier_company_name": normalize_text(self.embassy_supplier_field.value) or "رسوم سفارات",
                    "sale_amount_original": self.embassy_sale_field.value,
                    "cost_amount_original": self.embassy_cost_field.value,
                }
            )
        if normalize_text(self.transport_supplier_field.value) or normalize_text(self.transport_sale_field.value) or normalize_text(self.transport_cost_field.value):
            components.append(
                {
                    "service_type": "نقل بري",
                    "supplier_company_name": normalize_text(self.transport_supplier_field.value),
                    "sale_amount_original": self.transport_sale_field.value,
                    "cost_amount_original": self.transport_cost_field.value,
                }
            )
        payload = {
            "client_company_name": normalize_text(self.client_field.value),
            "supplier_company_name": normalize_text(self.supplier_field.value),
            "person_name": normalize_text(self.person_field.value),
            "service_type": self.service_dropdown.value or "تأشيرة سياحية",
            "currency_original": self.currency_dropdown.value,
            "date": self.operation_date.require_value("تاريخ الخدمة"),
            "notes": self.notes_field.value or "",
            "components": components,
        }
        return validate_service_case_payload(payload)

    def _set_busy(self, busy: bool):
        self._saving = bool(busy)
        self.workflow.set_busy(
            busy,
            busy_label="جارٍ حفظ التعديل..." if self.is_edit else "جارٍ إنشاء ملف الخدمة...",
        )

    def _save(self, e):
        if self._saving:
            return
        if UserSession.get_current() and UserSession.get_current().get("role") == "viewer":
            self._show_inline_error("ليست لديك صلاحية إنشاء ملف خدمة")
            self._show_snackbar("ليست لديك صلاحية إنشاء ملف خدمة", True)
            return
        self._clear_inline_error()
        try:
            payload = self._build_payload()
            if self.is_edit and not normalize_text(self.edit_reason_field.value):
                raise ValueError("سبب تعديل ملف الخدمة مطلوب")
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
                result = await asyncio.to_thread(lambda: ServiceCaseRepository().update(self.reference, payload, edit_reason=reason))
            else:
                result = await asyncio.to_thread(lambda: ServiceCaseRepository().add(payload))
        except Exception as ex:
            details = str(ex) or ex.__class__.__name__
            try:
                print(f"[service-case-save-error] {details}\n{traceback.format_exc()}", flush=True)
            except Exception:
                pass
            self._show_inline_error(f"فشل حفظ ملف الخدمة: {details}")
            self._show_snackbar(f"فشل حفظ ملف الخدمة: {details}", True)
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
            self._show_snackbar(f"تم حفظ ملف الخدمة، لكن تعذر تحديث الشاشة: {refresh_error}", True)
        else:
            self._show_snackbar(("تم تعديل ملف الخدمة" if self.is_edit else "تم إنشاء ملف الخدمة") + f": {result.get('reference')}", False)
