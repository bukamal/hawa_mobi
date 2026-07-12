# -*- coding: utf-8 -*-
import datetime
import flet as ft

from auth.session import UserSession
from currency import currency
from database import ServiceCaseRepository
from services.ledger_operation_service import SERVICE_TYPES
from views.flet_compat import close_control
from views.dialogs.dialog_kit import dialog_title, dialog_body, cancel_button, save_button, show_snackbar, set_button_busy, normalize_text, parse_non_negative_amount


class ServiceCaseDialog(ft.AlertDialog):
    """Create a professional intermediary service case.

    Example: Blue Star requested a tourist visa for a passenger; Safe Al Sham
    supplies the visa. The dialog creates two locked ledger entries with one
    reference and keeps profit internal.
    """

    def __init__(self, page, on_save=None, client_company_name=None, supplier_company_name=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        page_width = page.width or 400
        page_height = page.height or 650
        dialog_width = min(390, page_width - 32)
        dialog_height = min(590, page_height - 90)

        self.client_field = ft.TextField(label="الشركة العميلة", value=client_company_name or "", width=dialog_width - 20, hint_text="مثال: بلو ستار")
        self.supplier_field = ft.TextField(label="الشركة المورّدة", value=supplier_company_name or "", width=dialog_width - 20, hint_text="مثال: سيف الشام")
        self.person_field = ft.TextField(label="اسم الزبون / المسافر", width=dialog_width - 20, hint_text="مثال: أحمد محمد")
        default_service = "تأشيرة سياحية" if "تأشيرة سياحية" in SERVICE_TYPES else "فيزا"
        self.service_dropdown = ft.Dropdown(label="نوع الخدمة", value=default_service, options=[ft.dropdown.Option(s) for s in SERVICE_TYPES], width=dialog_width - 20)
        self.sale_field = ft.TextField(label="سعر البيع على الشركة العميلة", keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20)
        self.cost_field = ft.TextField(label="تكلفة الشركة المورّدة", keyboard_type=ft.KeyboardType.NUMBER, width=dialog_width - 20)
        self.currency_dropdown = ft.Dropdown(label="العملة", value=currency.get_display_currency(), options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]], width=120)
        self.date_field = ft.TextField(label="التاريخ", value=datetime.datetime.now().strftime("%Y-%m-%d"), hint_text="YYYY-MM-DD", width=150)
        self.notes_field = ft.TextField(label="ملاحظات داخلية", multiline=True, min_lines=2, max_lines=3, width=dialog_width - 20)
        self.profit_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)
        self.info_text = ft.Text("سيتم إنشاء قيدين مقفلين: لنا على الشركة العميلة، وله للشركة المورّدة. الربح يظهر داخليًا فقط.", size=12, color=ft.Colors.GREY_700)

        self.save_btn = save_button("إنشاء ملف الخدمة", self._save)
        self._saving = False
        for fld in (self.sale_field, self.cost_field):
            fld.on_change = self._update_profit
        self.currency_dropdown.on_change = self._update_profit
        self._update_profit(None)

        self.title = dialog_title("خدمة لعميل عبر مورد", ft.Icons.TRAVEL_EXPLORE)
        self.content = dialog_body([
            self.info_text,
            self.client_field,
            self.supplier_field,
            self.person_field,
            self.service_dropdown,
            ft.Row([self.sale_field, self.currency_dropdown], spacing=10, wrap=True),
            self.cost_field,
            ft.Row([self.date_field], spacing=10, wrap=True),
            self.profit_text,
            self.notes_field,
        ], width=dialog_width - 10, height=dialog_height - 100)
        self.actions = [cancel_button("إلغاء", lambda e: self._close()), self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=16)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _close(self):
        close_control(self._page, self)

    def _update_profit(self, e):
        try:
            sale = parse_non_negative_amount(self.sale_field.value or 0)
            cost = parse_non_negative_amount(self.cost_field.value or 0)
            code = self.currency_dropdown.value or currency.get_display_currency()
            self.profit_text.value = f"الربح المتوقع: {currency.format_amount(sale - cost, code)}"
            self.profit_text.color = ft.Colors.GREEN if (sale - cost) >= 0 else ft.Colors.RED
        except Exception:
            self.profit_text.value = ""
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليست لديك صلاحية إنشاء ملف خدمة", True)
            return
        payload = {
            "client_company_name": normalize_text(self.client_field.value),
            "supplier_company_name": normalize_text(self.supplier_field.value),
            "person_name": normalize_text(self.person_field.value),
            "service_type": self.service_dropdown.value or "تأشيرة سياحية",
            "sale_amount_original": self.sale_field.value,
            "cost_amount_original": self.cost_field.value,
            "currency_original": self.currency_dropdown.value,
            "date": normalize_text(self.date_field.value) or datetime.datetime.now().strftime("%Y-%m-%d"),
            "notes": self.notes_field.value or "",
        }
        self._saving = True
        set_button_busy(self.save_btn, True, "إنشاء ملف الخدمة")
        try:
            repo = ServiceCaseRepository()
            result = repo.add(payload)
            self._close()
            if self.on_save:
                self.on_save(result)
            self._show_snackbar(f"تم إنشاء ملف الخدمة: {result.get('reference')}", False)
        except Exception as ex:
            self._show_snackbar(f"فشل إنشاء ملف الخدمة: {ex}", True)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, "إنشاء ملف الخدمة")
            try:
                self._page.update()
            except Exception:
                pass
