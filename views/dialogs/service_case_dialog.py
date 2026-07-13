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

    def __init__(
        self, page, on_save=None, client_company_name=None, supplier_company_name=None
    ):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False
        page_width = page.width or 400
        page_height = page.height or 650
        dialog_width = min(390, page_width - 32)
        dialog_height = min(590, page_height - 90)

        self.client_field = ft.TextField(
            label="الشركة العميلة",
            value=client_company_name or "",
            width=dialog_width - 20,
            hint_text="مثال: بلو ستار",
        )
        self.supplier_field = ft.TextField(
            label="الشركة المورّدة",
            value=supplier_company_name or "",
            width=dialog_width - 20,
            hint_text="مثال: سيف الشام",
        )
        self.person_field = ft.TextField(
            label="اسم الزبون / المسافر",
            width=dialog_width - 20,
            hint_text="مثال: أحمد محمد",
        )
        default_service = (
            "تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "فيزا"
        )
        self.service_dropdown = ft.Dropdown(
            label="نوع الخدمة",
            value=default_service,
            options=[ft.dropdown.Option(s) for s in SERVICE_TYPES],
            width=dialog_width - 20,
        )
        self.sale_field = ft.TextField(
            label="سعر البيع على الشركة العميلة",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=dialog_width - 20,
        )
        self.cost_field = ft.TextField(
            label="تكلفة الشركة المورّدة الأساسية",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=dialog_width - 20,
        )
        self.embassy_supplier_field = ft.TextField(
            label="حساب السفارة / رسوم السفارة",
            width=dialog_width - 20,
            hint_text="مثال: رسوم سفارات أو سفارة الأردن",
        )
        self.embassy_sale_field = ft.TextField(
            label="بيع رسوم السفارة على العميل",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=(dialog_width - 34) / 2,
        )
        self.embassy_cost_field = ft.TextField(
            label="تكلفة رسوم السفارة",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=(dialog_width - 34) / 2,
        )
        self.transport_supplier_field = ft.TextField(
            label="شركة النقل البري",
            width=dialog_width - 20,
            hint_text="مثال: شركة نقل الشام",
        )
        self.transport_sale_field = ft.TextField(
            label="بيع النقل على العميل",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=(dialog_width - 34) / 2,
        )
        self.transport_cost_field = ft.TextField(
            label="تكلفة النقل",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=(dialog_width - 34) / 2,
        )
        self.currency_dropdown = ft.Dropdown(
            label="العملة",
            value=currency.get_display_currency(),
            options=[
                ft.dropdown.Option(c)
                for c in ["USD", "SAR", "SYP", "EUR", "GBP", "AED", "QAR", "KWD", "OMR"]
            ],
            width=120,
        )
        self.date_field = ft.TextField(
            label="التاريخ",
            value=datetime.datetime.now().strftime("%Y-%m-%d"),
            hint_text="YYYY-MM-DD",
            width=150,
        )
        self.notes_field = ft.TextField(
            label="ملاحظات داخلية",
            multiline=True,
            min_lines=2,
            max_lines=3,
            width=dialog_width - 20,
        )
        self.profit_text = ft.Text(
            "", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO
        )
        self.info_text = ft.Text(
            "سيتم إنشاء قيدين مقفلين: لنا على الشركة العميلة، وله للشركة المورّدة. الربح يظهر داخليًا فقط.",
            size=12,
            color=ft.Colors.GREY_700,
        )
        self.error_text = ft.Text("", size=12, color=ft.Colors.RED, selectable=True)
        self.error_box = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=18),
                    self.error_text,
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.RED_50,
            border_radius=10,
            padding=10,
            visible=False,
        )

        self.save_btn = save_button("إنشاء ملف الخدمة", self._save)
        for fld in (
            self.sale_field,
            self.cost_field,
            self.embassy_sale_field,
            self.embassy_cost_field,
            self.transport_sale_field,
            self.transport_cost_field,
        ):
            fld.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        self.title = dialog_title("خدمة لعميل عبر مورد", ft.Icons.TRAVEL_EXPLORE)
        self.content = dialog_body(
            [
                self.info_text,
                self.error_box,
                self.client_field,
                self.supplier_field,
                self.person_field,
                self.service_dropdown,
                ft.Row(
                    [self.sale_field, self.currency_dropdown], spacing=10, wrap=True
                ),
                self.cost_field,
                ft.Divider(height=1),
                ft.Text(
                    "بنود إضافية اختيارية",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.INDIGO,
                ),
                self.embassy_supplier_field,
                ft.Row(
                    [self.embassy_sale_field, self.embassy_cost_field],
                    spacing=10,
                    wrap=True,
                ),
                self.transport_supplier_field,
                ft.Row(
                    [self.transport_sale_field, self.transport_cost_field],
                    spacing=10,
                    wrap=True,
                ),
                ft.Row([self.date_field], spacing=10, wrap=True),
                self.profit_text,
                self.notes_field,
            ],
            width=dialog_width - 10,
            height=dialog_height - 100,
        )
        self.actions = [cancel_button("إلغاء", lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=16)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _close(self):
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
            self.profit_text.color = (
                ft.Colors.GREEN if (sale - cost) >= 0 else ft.Colors.RED
            )
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
        if (
            normalize_text(self.embassy_supplier_field.value)
            or normalize_text(self.embassy_sale_field.value)
            or normalize_text(self.embassy_cost_field.value)
        ):
            components.append(
                {
                    "service_type": "سفارة / رسوم سفارة",
                    "supplier_company_name": normalize_text(
                        self.embassy_supplier_field.value
                    )
                    or "رسوم سفارات",
                    "sale_amount_original": self.embassy_sale_field.value,
                    "cost_amount_original": self.embassy_cost_field.value,
                }
            )
        if (
            normalize_text(self.transport_supplier_field.value)
            or normalize_text(self.transport_sale_field.value)
            or normalize_text(self.transport_cost_field.value)
        ):
            components.append(
                {
                    "service_type": "نقل بري",
                    "supplier_company_name": normalize_text(
                        self.transport_supplier_field.value
                    ),
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
            "date": normalize_text(self.date_field.value)
            or datetime.datetime.now().strftime("%Y-%m-%d"),
            "notes": self.notes_field.value or "",
            "components": components,
        }
        # Reuse the business validator before any network/database call so the
        # button returns a visible field-level error instead of appearing dead.
        return validate_service_case_payload(payload)

    def _set_busy(self, busy: bool):
        self._saving = bool(busy)
        set_button_busy(
            self.save_btn, busy, "إنشاء ملف الخدمة", busy_label="جارٍ إنشاء الخدمة..."
        )
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        if (
            UserSession.get_current()
            and UserSession.get_current().get("role") == "viewer"
        ):
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
            result = await asyncio.to_thread(
                lambda: ServiceCaseRepository().add(payload)
            )
        except Exception as ex:
            details = str(ex) or ex.__class__.__name__
            try:
                print(
                    f"[service-case-save-error] {details}\n{traceback.format_exc()}",
                    flush=True,
                )
            except Exception:
                pass
            self._show_inline_error(f"فشل إنشاء ملف الخدمة: {details}")
            self._show_snackbar(f"فشل إنشاء ملف الخدمة: {details}", True)
            self._set_busy(False)
            return

        self._set_busy(False)
        self._close()
        refresh_error = None
        if self.on_save:
            try:
                self.on_save(result)
            except Exception as ex:
                refresh_error = str(ex) or ex.__class__.__name__
        if refresh_error:
            self._show_snackbar(
                f"تم إنشاء ملف الخدمة، لكن تعذر تحديث الشاشة: {refresh_error}", True
            )
        else:
            self._show_snackbar(
                f"تم إنشاء ملف الخدمة: {result.get('reference')}", False
            )
