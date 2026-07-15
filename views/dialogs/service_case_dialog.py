# -*- coding: utf-8 -*-
import asyncio
import datetime
import traceback
import flet as ft

from auth.session import UserSession
from currency import currency
from database import ServiceCaseRepository
from services.ledger_operation_service import SERVICE_TYPES
from services.service_case_service import validate_service_case_payload
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


class ServiceCaseDialog(ft.AlertDialog):
    """Create a professional intermediary service case.

    Example: Blue Star requested a tourist visa for a passenger; Safe Al Sham
    supplies the visa. The dialog creates two locked ledger entries with one
    reference and keeps profit internal.
    """

    def __init__(self, page, on_save=None, client_company_name=None, supplier_company_name=None, service_case=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        self.service_case = dict(service_case or {})
        self.reference = (self.service_case.get("reference") or "").strip()
        self.is_edit = bool(self.reference)
        page_width = page.width or 400
        page_height = page.height or 650
        dialog_width = min(390, page_width - 32)
        dialog_height = min(600, page_height - 90)

        existing_components = list(self.service_case.get("components") or [])
        def _component_by_kind(kind: str):
            for comp in existing_components:
                st = str(comp.get("service_type") or "")
                if kind == "embassy" and ("سفارة" in st or "رسوم" in st):
                    return comp
                if kind == "transport" and ("نقل" in st or "transport" in st.lower()):
                    return comp
            return None
        embassy_component = _component_by_kind("embassy") or {}
        transport_component = _component_by_kind("transport") or {}
        base_component = {}
        for comp in existing_components:
            if comp is not embassy_component and comp is not transport_component:
                base_component = comp
                break
        if not base_component and existing_components:
            base_component = existing_components[0]

        self.client_field = ft.TextField(label="الشركة العميلة", value=self.service_case.get("client_company_name") or client_company_name or "", width=dialog_width - 20, hint_text="مثال: بلو ستار")
        self.supplier_field = ft.TextField(label="الشركة المورّدة", value=base_component.get("supplier_company_name") or self.service_case.get("supplier_company_name") or supplier_company_name or "", width=dialog_width - 20, hint_text="مثال: سيف الشام")
        self.person_field = ft.TextField(label="اسم الزبون / المسافر", value=self.service_case.get("person_name") or "", width=dialog_width - 20, hint_text="مثال: أحمد محمد")
        default_service = "تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "فيزا"
        self.service_dropdown = ft.Dropdown(label="نوع الخدمة", value=base_component.get("service_type") or self.service_case.get("primary_service_type") or self.service_case.get("service_type") or default_service, options=[ft.dropdown.Option(s) for s in SERVICE_TYPES], width=dialog_width - 20)
        self.sale_field = ft.TextField(label="سعر البيع على الشركة العميلة", value=str(base_component.get("sale_amount_original") or (self.service_case.get("sale_amount_original") if not existing_components else "") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20)
        self.cost_field = ft.TextField(label="تكلفة الشركة المورّدة الأساسية", value=str(base_component.get("cost_amount_original") or (self.service_case.get("cost_amount_original") if not existing_components else "") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20)
        self.embassy_supplier_field = ft.TextField(label="حساب السفارة / رسوم السفارة", value=embassy_component.get("supplier_company_name") or "", width=dialog_width - 20, hint_text="مثال: رسوم سفارات أو سفارة الأردن")
        self.embassy_sale_field = ft.TextField(label="بيع رسوم السفارة على العميل", value=str(embassy_component.get("sale_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=(dialog_width - 34) / 2)
        self.embassy_cost_field = ft.TextField(label="تكلفة رسوم السفارة", value=str(embassy_component.get("cost_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=(dialog_width - 34) / 2)
        self.transport_supplier_field = ft.TextField(label="شركة النقل البري", value=transport_component.get("supplier_company_name") or "", width=dialog_width - 20, hint_text="مثال: شركة نقل الشام")
        self.transport_sale_field = ft.TextField(label="بيع النقل على العميل", value=str(transport_component.get("sale_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=(dialog_width - 34) / 2)
        self.transport_cost_field = ft.TextField(label="تكلفة النقل", value=str(transport_component.get("cost_amount_original") or ""), keyboard_type=ft.KeyboardType.NUMBER, width=(dialog_width - 34) / 2)
        self.currency_dropdown = ft.Dropdown(label="العملة", value=self.service_case.get("currency_original") or currency.get_display_currency(), options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]], width=120)
        self.operation_date = FinancialDateField(page, label="تاريخ الخدمة", value=self.service_case.get("date"), width=dialog_width - 20)
        self.date_field = self.operation_date.field
        self.notes_field = ft.TextField(label="ملاحظات داخلية", value=self.service_case.get("notes") or "", multiline=True, min_lines=2, max_lines=3, width=dialog_width - 20)
        self.edit_reason_field = ft.TextField(label="سبب التعديل", multiline=True, min_lines=2, max_lines=3, width=dialog_width - 20, visible=self.is_edit, hint_text="مثال: تصحيح سعر البيع أو المورّد أو بند الخدمة")
        self.profit_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)
        self.info_text = ft.Text("يتم حفظ ملف الخدمة كعملية مرتبطة. التعديل يحدّث قيد العميل وكل قيود الموردين معًا، ولا يفتح القيود المولّدة للتعديل الفردي.", size=12, color=ft.Colors.GREY_700)
        self.error_text = ft.Text("", size=12, color=ft.Colors.RED, selectable=True)
        self.error_box = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=18), self.error_text], spacing=8),
            bgcolor=ft.Colors.RED_50,
            border_radius=10,
            padding=10,
            visible=False,
        )

        self.save_btn = save_button("حفظ التعديل" if self.is_edit else "إنشاء ملف الخدمة", self._save)
        for fld in (self.sale_field, self.cost_field, self.embassy_sale_field, self.embassy_cost_field, self.transport_sale_field, self.transport_cost_field):
            fld.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        self.title = dialog_title("تعديل ملف خدمة" if self.is_edit else "خدمة لعميل عبر مورد", ft.Icons.TRAVEL_EXPLORE)
        self.content = dialog_body([
            self.info_text,
            self.error_box,
            self.client_field,
            self.supplier_field,
            self.person_field,
            self.service_dropdown,
            ft.Row([self.sale_field, self.currency_dropdown], spacing=10, wrap=True),
            self.cost_field,
            ft.Divider(height=1),
            ft.Text("بنود إضافية اختيارية", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO),
            self.embassy_supplier_field,
            ft.Row([self.embassy_sale_field, self.embassy_cost_field], spacing=10, wrap=True),
            self.transport_supplier_field,
            ft.Row([self.transport_sale_field, self.transport_cost_field], spacing=10, wrap=True),
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
            code = self.currency_dropdown.value or currency.get_display_currency()
            self.profit_text.value = f"إجمالي البيع: {currency.format_amount(sale, code)} · التكلفة: {currency.format_amount(cost, code)} · الربح: {currency.format_amount(sale - cost, code)}"
            self.profit_text.color = ft.Colors.GREEN if (sale - cost) >= 0 else ft.Colors.RED
        except Exception:
            self.profit_text.value = ""
        try:
            self._page.update()
        except Exception:
            pass

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
            components.append({
                "service_type": "سفارة / رسوم سفارة",
                "supplier_company_name": normalize_text(self.embassy_supplier_field.value) or "رسوم سفارات",
                "sale_amount_original": self.embassy_sale_field.value,
                "cost_amount_original": self.embassy_cost_field.value,
            })
        if normalize_text(self.transport_supplier_field.value) or normalize_text(self.transport_sale_field.value) or normalize_text(self.transport_cost_field.value):
            components.append({
                "service_type": "نقل بري",
                "supplier_company_name": normalize_text(self.transport_supplier_field.value),
                "sale_amount_original": self.transport_sale_field.value,
                "cost_amount_original": self.transport_cost_field.value,
            })
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
        # Reuse the business validator before any network/database call so the
        # button returns a visible field-level error instead of appearing dead.
        return validate_service_case_payload(payload)

    def _set_busy(self, busy: bool):
        self._saving = bool(busy)
        set_button_busy(self.save_btn, busy, "حفظ التعديل" if self.is_edit else "إنشاء ملف الخدمة", busy_label="جارٍ حفظ التعديل..." if self.is_edit else "جارٍ إنشاء الخدمة...")
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_inline_error("ليست لديك صلاحية إنشاء ملف خدمة")
            self._show_snackbar("ليست لديك صلاحية إنشاء ملف خدمة", True)
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
            # Local SQLite writes and remote REST requests must not block the Flet
            # event callback.  On Android a synchronous request can make the
            # dialog look unresponsive while remaining open.
            if self.is_edit:
                reason = normalize_text(self.edit_reason_field.value)
                if not reason:
                    raise ValueError("سبب تعديل ملف الخدمة مطلوب")
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
