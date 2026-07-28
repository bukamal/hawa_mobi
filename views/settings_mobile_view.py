# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, make_file_picker, attach_service_control, service_control_attached, filepicker_unavailable_message, run_async_task, make_expansion_tile, clear_transient_ui
from views.ui_kit import page_header, data_card, show_snackbar, empty_state, info_banner, responsive_wrap, PRIMARY, PRIMARY_SOFT, TEXT, MUTED, BORDER, SUCCESS, DANGER, WARNING
from database import SettingsRepository
from auth.session import UserSession
from auth.permissions import can_access_settings_section, access_denied_message
from currency import currency
from i18n.translator import translate, set_language, language_code_from_label, language_label, is_rtl
from config import get_company_info, save_company_info, default_company_info
from database.connection import DatabaseConnection
from views.ui_runtime import network_status_chip
import datetime
import os
import shutil
import csv
import asyncio

class SettingsMobileView(ft.Column):
    SECTION_META = {
        "currency": ("العملات", ft.Icons.PAID_OUTLINED, "_currency_tab"),
        "rates": ("أسعار الصرف", ft.Icons.CURRENCY_EXCHANGE, "_rates_tab"),
        "company": ("بيانات الشركة", ft.Icons.BUSINESS_OUTLINED, "_company_tab"),
        "reports": ("التقارير والطباعة", ft.Icons.PRINT_OUTLINED, "_reports_tab"),
        "appearance": ("اللغة والمظهر", ft.Icons.PALETTE_OUTLINED, "_lang_theme_tab"),
        "network": ("الاتصال والخادم", ft.Icons.LAN_OUTLINED, "_network_tab"),
        "backup": ("النسخ الاحتياطي", ft.Icons.CLOUD_SYNC_OUTLINED, "_backup_tab"),
    }

    def __init__(self, page, section=None):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.repo = SettingsRepository()
        self.rate_fields = {}
        self._restore_file_picker = None
        self._restore_picker_opened_at = None
        self._restore_picker_result_seen = False
        self._restore_operation_busy = False
        self.section = section

        if section:
            self.controls = self._build_section_page(section)
        elif UserSession.is_admin():
            # Backward-compatible direct construction used by older smoke tests.
            self.controls = [
                page_header(translate('settings'), ft.Icons.SETTINGS_OUTLINED, subtitle="إعدادات النظام، الشبكة، النسخ الاحتياطي والعملات"),
                self._settings_tile("العملات", self._currency_tab(), ft.Icons.PAID_OUTLINED, expanded=True),
                self._settings_tile("أسعار الصرف", self._rates_tab(), ft.Icons.CURRENCY_EXCHANGE),
                self._settings_tile("بيانات الشركة", self._company_tab(), ft.Icons.BUSINESS_OUTLINED),
                self._settings_tile("التقارير والطباعة", self._reports_tab(), ft.Icons.PRINT_OUTLINED),
                self._settings_tile("اللغة والمظهر", self._lang_theme_tab(), ft.Icons.PALETTE_OUTLINED),
                self._settings_tile("الاتصال والخادم", self._network_tab(), ft.Icons.LAN_OUTLINED),
                self._settings_tile("النسخ الاحتياطي", self._backup_tab(), ft.Icons.CLOUD_SYNC_OUTLINED),
                ft.Container(height=24),
            ]
        else:
            self.controls = self._build_section_page("appearance")

    def _build_section_page(self, section):
        meta = self.SECTION_META.get(section)
        if not meta:
            return [page_header("إعدادات غير معروفة", ft.Icons.ERROR_OUTLINE), empty_state("القسم غير موجود")]
        title, icon, builder_name = meta
        back_btn = ft.IconButton(icon=ft.Icons.ARROW_FORWARD, tooltip="العودة إلى الإعدادات", on_click=self._open_settings_hub)
        if not can_access_settings_section(section):
            return [
                page_header(title, icon, trailing=back_btn, subtitle="قسم إداري محمي"),
                empty_state("وصول غير مسموح", access_denied_message(), ft.Icons.LOCK_OUTLINE),
            ]
        content = getattr(self, builder_name)()
        return [
            page_header(title, icon, trailing=back_btn, subtitle="إعدادات موحدة وآمنة"),
            data_card(content, elevation=0),
            ft.Container(height=24),
        ]

    def _open_settings_hub(self, e=None):
        opener = getattr(self._page, "_hawaa_open_page", None)
        if callable(opener):
            opener("settings")

    def _require_admin(self):
        if UserSession.is_admin():
            return True
        self._show_snackbar(access_denied_message(), True)
        return False

    def _settings_tile(self, title, content, icon=None, expanded=False):
        title_control = ft.Row([
            ft.Container(content=ft.Icon(icon or ft.Icons.SETTINGS_OUTLINED, color=PRIMARY, size=20), bgcolor=PRIMARY_SOFT, border_radius=12, padding=8),
            ft.Column([
                ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text("اضغط لعرض الإعدادات", size=11, color=MUTED),
            ], spacing=2, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return data_card(
            make_expansion_tile(
                title=title_control,
                expanded=expanded,
                controls=[ft.Container(content=content, padding=ft.Padding(left=8, right=8, top=8, bottom=8))],
            ),
            padding=0,
            elevation=0,
        )

    def _show_snackbar(self, message, is_error=False, duration=3000):
        """Settings-local snackbar wrapper.

        Backup restore actions use short status messages before opening the
        Android file picker.  Earlier code accepted only (message, is_error),
        so calls passing duration crashed before the FilePicker could open; the
        button looked dead and diagnostics showed:
        SettingsMobileView._show_snackbar() got an unexpected keyword argument
        'duration'.
        """
        try:
            return show_snackbar(self._page, message, is_error, duration=duration)
        except TypeError:
            # Compatibility with older local/ui_kit wrappers.  Do not let a
            # transient notification block backup restore.
            return show_snackbar(self._page, message, is_error)

    def _currency_tab(self):
        field_width = 280
        self.base_curr = ft.Dropdown(
            label="العملة الأساسية",
            value=currency.get_base_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=field_width
        )
        self.display_curr = ft.Dropdown(
            label="العملة المعروضة",
            value=currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=field_width
        )
        self.decimals = ft.Slider(
            label="الخانات العشرية: {value}",
            min=0, max=2, divisions=2,
            value=int(self.repo.get('currency_decimals','2')),
            width=field_width
        )
        self.format_dropdown = ft.Dropdown(
            label="تنسيق الأرقام",
            value="غربية" if self.repo.get('number_format','western')=='western' else "شرقية",
            options=[ft.dropdown.Option("غربية"), ft.dropdown.Option("شرقية")],
            width=field_width
        )
        self.abbreviate = ft.Checkbox(
            label="اختصار الأعداد الكبيرة",
            value=currency.abbreviate_numbers()
        )
        save_btn = ft.FilledButton(
            content=ft.Text("حفظ"),
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._save_currency
        )
        return ft.Column([
            self.base_curr, self.display_curr, self.decimals,
            self.format_dropdown, self.abbreviate, save_btn
        ], spacing=15)

    def _save_currency(self, e):
        if not self._require_admin():
            return
        previous_display = currency.get_display_currency()
        fmt = 'western' if self.format_dropdown.value == 'غربية' else 'arabic'
        currency.save_runtime_settings(
            base_currency=self.base_curr.value,
            display_currency=self.display_curr.value,
            decimals=int(self.decimals.value),
            number_format=fmt,
            abbreviate_numbers=bool(self.abbreviate.value),
        )
        new_display = currency.get_display_currency()
        if new_display != previous_display:
            self._show_snackbar(f"تم تطبيق عملة العرض فوراً: {new_display}", is_error=False)
        else:
            self._show_snackbar("تم حفظ إعدادات العملة", is_error=False)
        refresh = getattr(self._page, '_hawaa_refresh_current_page', None)
        if callable(refresh):
            refresh()
        else:
            self._page.update()

    def _rates_tab(self):
        self.rates_list = ft.Column(spacing=10)
        refresh_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.REFRESH), ft.Text("تحديث من الإنترنت")]),
            on_click=self._fetch_online_rates
        )
        save_all_btn = ft.FilledButton(
            content=ft.Text("حفظ جميع الأسعار", weight=ft.FontWeight.BOLD),
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._save_all_rates
        )
        self._load_rates_cards()
        return ft.Column([
            ft.Container(content=self.rates_list, expand=True),
            ft.Row([refresh_btn, save_all_btn], spacing=10)
        ], spacing=15, expand=True)

    def _load_rates_cards(self):
        try:
            rates = currency.get_all_currencies()
            if not rates:
                self.rates_list.controls = [
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.WARNING, size=40, color=ft.Colors.ORANGE),
                                ft.Text("لا توجد أسعار صرف في قاعدة البيانات", size=14, weight=ft.FontWeight.BOLD),
                                ft.Text("يمكنك إضافة أسعار يدوياً أو تحديثها من الإنترنت", size=12, color=ft.Colors.GREY_600),
                                ft.FilledButton(
                                    content=ft.Text("إضافة أسعار افتراضية"),
                                    on_click=self._insert_default_rates,
                                    bgcolor=PRIMARY,
                                    color=ft.Colors.WHITE
                                )
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20
                        ),
                        elevation=1,
                        margin=ft.Margin(left=20, right=20, top=10, bottom=10)
                    )
                ]
                self._page.update()
                return
            cards = []
            self.rate_fields = {}
            for r in rates:
                code = r['currency_code']
                rate_field = ft.TextField(
                    value=f"{r['rate_to_usd']:.4f}",
                    width=120,
                    text_align=ft.TextAlign.CENTER,
                    keyboard_type=ft.KeyboardType.NUMBER
                )
                self.rate_fields[code] = rate_field
                updated_at = r['updated_at'][:19] if r['updated_at'] else 'غير محدد'
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Row([
                            ft.Text(code, size=16, weight=ft.FontWeight.BOLD, width=60),
                            ft.Container(content=rate_field, width=130),
                            ft.Text(updated_at, size=11, color=ft.Colors.GREY_500, expand=True)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=12
                    ),
                    elevation=1,
                    margin=ft.Margin(left=5, right=5, top=3, bottom=3)
                )
                cards.append(card)
            self.rates_list.controls = cards
            self._page.update()
        except Exception as e:
            self.rates_list.controls = [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.ERROR, size=40, color=ft.Colors.RED),
                            ft.Text("حدث خطأ أثناء تحميل أسعار الصرف", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(str(e), size=12, color=ft.Colors.RED),
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20
                    ),
                    elevation=1,
                    margin=ft.Margin(left=20, right=20, top=10, bottom=10)
                )
            ]
            self._page.update()

    def _insert_default_rates(self, e):
        if not self._require_admin():
            return
        try:
            default_rates = [
                ('USD', 1.0), ('SAR', 3.75), ('SYP', 14000.0), ('EUR', 0.92),
                ('GBP', 0.79), ('AED', 3.67), ('QAR', 3.64), ('KWD', 0.31), ('OMR', 0.38)
            ]
            db = DatabaseConnection()
            now = datetime.datetime.now().isoformat()
            for code, rate in default_rates:
                db.update_exchange_rate(code, rate)
            self._show_snackbar("تم إضافة الأسعار الافتراضية", is_error=False)
            self._load_rates_cards()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _save_all_rates(self, e):
        if not self._require_admin():
            return
        try:
            for code, field in self.rate_fields.items():
                try:
                    rate = float(field.value)
                    currency.update_rate(code, rate)
                except:
                    pass
            currency.invalidate_cache()
            self._show_snackbar("تم حفظ جميع الأسعار وتحديث العرض الحالي", is_error=False)
            self._load_rates_cards()
            refresh = getattr(self._page, '_hawaa_refresh_current_page', None)
            if callable(refresh):
                refresh()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _fetch_online_rates(self, e):
        if not self._require_admin():
            return
        import requests
        try:
            resp = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get('rates', {})
                for code, field in self.rate_fields.items():
                    if code in rates:
                        field.value = f"{rates[code]:.4f}"
                self._show_snackbar("تم تحديث الأسعار من الإنترنت", is_error=False)
                self._page.update()
            else:
                self._show_snackbar("فشل الاتصال بالخادم", True)
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _company_tab(self):
        info = get_company_info()
        self.company_name = ft.TextField(label="اسم الشركة", value=info.get('name',''), width=350)
        self.company_address = ft.TextField(label="العنوان", value=info.get('address',''), width=350)
        self.company_phone = ft.TextField(label="الهاتف", value=info.get('phone',''), width=350)
        self.company_email = ft.TextField(label="البريد الإلكتروني", value=info.get('email',''), width=350)
        self.company_logo = ft.TextField(label="مسار الشعار داخل التطبيق", value=info.get('logo_path',''), width=350, read_only=True)
        self.logo_preview = ft.Container(content=self._logo_preview_control(info.get('logo_path','')), padding=8, border_radius=14, bgcolor=ft.Colors.GREY_100)
        logo_btn = ft.FilledButton(content=ft.Row([ft.Icon(ft.Icons.IMAGE), ft.Text("اختيار شعار")]), on_click=self._browse_logo)
        remove_logo_btn = ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.RESTART_ALT), ft.Text("إعادة الشعار الافتراضي")]), on_click=self._remove_company_logo)
        reset_defaults_btn = ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.SETTINGS_BACKUP_RESTORE), ft.Text("إعادة القيم الافتراضية")]), on_click=self._reset_company_defaults)
        save_btn = ft.FilledButton(content=ft.Text("حفظ"), bgcolor=PRIMARY, color=ft.Colors.WHITE, on_click=self._save_company)
        return ft.Column([
            self.company_name,
            self.company_address,
            self.company_phone,
            self.company_email,
            info_banner("يتم نسخ الشعار إلى تخزين التطبيق وإدخاله داخل تقارير HTML كصورة Base64 حتى يظهر عند الطباعة والمشاركة.", icon=ft.Icons.IMAGE),
            self.logo_preview,
            self.company_logo,
            responsive_wrap([logo_btn, remove_logo_btn, reset_defaults_btn, save_btn], spacing=10),
        ], spacing=15)

    def _logo_preview_control(self, path: str):
        try:
            from services.company_logo_service import image_to_base64
            b64 = image_to_base64(path or "")
            if b64:
                return ft.Row([
                    ft.Image(src_base64=b64, width=86, height=86, fit="contain"),
                    ft.Column([
                        ft.Text("شعار التقارير والطباعة", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text("سيظهر في كشف الحساب والطباعة عند تفعيل إظهار الشعار.", size=11, color=ft.Colors.GREY_600),
                    ], spacing=3, expand=True),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        except Exception:
            pass
        return ft.Row([
            ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED, size=38, color=ft.Colors.GREY_500),
            ft.Text("تعذر عرض الشعار الافتراضي", size=12, color=ft.Colors.GREY_600),
        ], alignment=ft.MainAxisAlignment.START)

    def _save_company(self, e):
        if not self._require_admin():
            return
        info = {
            'name': self.company_name.value,
            'address': self.company_address.value,
            'phone': self.company_phone.value,
            'email': self.company_email.value,
            'logo_path': self.company_logo.value,
        }
        save_company_info(info)
        self._show_snackbar("تم حفظ معلومات الشركة", is_error=False)

    def _reset_company_defaults(self, e):
        if not self._require_admin():
            return
        defaults = default_company_info()
        self.company_name.value = defaults.get('name', '')
        self.company_address.value = defaults.get('address', '')
        self.company_phone.value = defaults.get('phone', '')
        self.company_email.value = defaults.get('email', '')
        self.company_logo.value = defaults.get('logo_path', '')
        self.logo_preview.content = self._logo_preview_control(self.company_logo.value)
        self._page.update()
        self._show_snackbar("تمت إعادة بيانات الشركة والشعار الافتراضي", False)

    def _browse_logo(self, e):
        if not self._require_admin():
            return
        picker = make_file_picker(self._on_logo_picked)
        attach_service_control(self._page, picker)
        if not service_control_attached(picker):
            self._open_logo_path_fallback_dialog(filepicker_unavailable_message())
            return
        try:
            picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg", "webp"],
                dialog_title="اختيار شعار التقارير",
            )
        except Exception as ex:
            self._show_snackbar(f"تعذر فتح منتقي الملفات: {ex}", True)

    def _on_logo_picked(self, e):
        try:
            files = getattr(e, 'files', None) or []
            if not files:
                self._show_snackbar("لم يتم اختيار شعار", False)
                return
            selected = files[0]
            source_path = getattr(selected, 'path', None) or getattr(selected, 'name', None)
            if not source_path or not os.path.exists(source_path):
                self._show_snackbar("لم يستطع Android إعطاء مسار قابل للقراءة. انسخ الصورة إلى Files ثم أعد المحاولة.", True)
                return
            from services.company_logo_service import import_logo
            stored = import_logo(source_path)
            self.company_logo.value = stored
            self.logo_preview.content = self._logo_preview_control(stored)
            self._show_snackbar("تم اختيار الشعار وسيُستخدم في الطباعة", False)
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"فشل اختيار الشعار: {ex}", True)

    def _remove_company_logo(self, e):
        if not self._require_admin():
            return
        try:
            from services.company_logo_service import remove_logo
            remove_logo(self.company_logo.value)
        except Exception:
            pass
        defaults = default_company_info()
        self.company_logo.value = defaults.get('logo_path', '')
        self.logo_preview.content = self._logo_preview_control(self.company_logo.value)
        self._show_snackbar("تمت إعادة الشعار الافتراضي", False)
        self._page.update()


    def _reports_tab(self):
        from reports.config import get_report_settings
        settings = get_report_settings()
        layout_options = [
            ft.dropdown.Option("جدول كامل"),
            ft.dropdown.Option("جدول مدمج"),
            ft.dropdown.Option("بطاقات"),
        ]
        layout_label = {
            'full_table': 'جدول كامل',
            'compact_table': 'جدول مدمج',
            'cards': 'بطاقات',
        }
        self.report_reconciliation_layout = ft.Dropdown(
            label="نمط كشف المطابقة",
            value=layout_label.get(settings.get('reconciliation_layout_mode'), 'جدول مدمج'),
            options=layout_options,
            width=260,
        )
        self.report_whatsapp_layout = ft.Dropdown(
            label="نمط واتساب / المشاركة",
            value=layout_label.get(settings.get('whatsapp_statement_layout_mode'), 'جدول مدمج'),
            options=layout_options,
            width=260,
        )
        self.report_print_layout = ft.Dropdown(
            label="نمط كشف الطباعة",
            value=layout_label.get(settings.get('print_statement_layout_mode'), 'جدول كامل'),
            options=[ft.dropdown.Option("جدول كامل"), ft.dropdown.Option("جدول مدمج")],
            width=260,
        )
        self.report_header_note = ft.TextField(label="نص الرأس", value=settings.get('header_note', ''), width=350)
        self.report_footer_note = ft.TextField(label="نص التذييل", value=settings.get('footer_note', ''), width=350, multiline=True, min_lines=2, max_lines=3)
        self.report_show_logo = ft.Checkbox(label="إظهار شعار الشركة في الطباعة", value=bool(settings.get('show_company_logo', True)))
        self.report_show_contact = ft.Checkbox(label="إظهار بيانات الشركة", value=bool(settings.get('show_company_contact', True)))
        self.report_show_generated_at = ft.Checkbox(label="إظهار تاريخ إنشاء التقرير", value=bool(settings.get('show_generated_at', True)))
        self.report_show_summary = ft.Checkbox(label="إظهار ملخص الرصيد", value=bool(settings.get('show_statement_summary', True)))
        self.report_show_reconciliation_note = ft.Checkbox(label="إظهار ملاحظة المطابقة", value=bool(settings.get('show_reconciliation_note', True)))
        self.report_use_colors = ft.Checkbox(label="استخدام الألوان", value=bool(settings.get('statement_use_colors', True)))
        self.report_shorten_refs = ft.Checkbox(label="اختصار المرجع الطويل", value=bool(settings.get('shorten_long_references', False)))
        self.report_columns = []
        column_controls = []
        for col in settings.get('account_statement_columns', []):
            checkbox = ft.Checkbox(label=str(col.get('label', col.get('key'))), value=bool(col.get('visible', True)))
            label_field = ft.TextField(label="اسم العمود", value=str(col.get('label', '')), width=180)
            self.report_columns.append((str(col.get('key')), checkbox, label_field))
            column_controls.append(ft.Row([checkbox, label_field], spacing=8, wrap=True))
        save_btn = ft.FilledButton(content=ft.Text("حفظ إعدادات التقارير"), bgcolor=PRIMARY, color=ft.Colors.WHITE, on_click=self._save_reports)
        return ft.Column([
            info_banner("القالب الجديد لا يحذف الأعمدة: في الجدول الكامل تظهر كأعمدة، وفي الجدول المدمج تظهر التفاصيل أسفل البيان، وفي البطاقات تظهر كحقول واضحة."),
            ft.Text("أنماط العرض", size=14, weight=ft.FontWeight.BOLD),
            responsive_wrap([self.report_reconciliation_layout, self.report_whatsapp_layout, self.report_print_layout], spacing=10),
            ft.Text("خيارات الشكل", size=14, weight=ft.FontWeight.BOLD),
            responsive_wrap([self.report_show_logo, self.report_show_contact, self.report_show_generated_at, self.report_show_summary, self.report_show_reconciliation_note, self.report_use_colors, self.report_shorten_refs], spacing=8),
            self.report_header_note,
            self.report_footer_note,
            ft.Text("الأعمدة الظاهرة", size=14, weight=ft.FontWeight.BOLD),
            ft.Column(column_controls, spacing=4),
            save_btn,
        ], spacing=12)

    def _save_reports(self, e):
        if not self._require_admin():
            return
        from reports.config import get_report_settings, save_report_settings
        settings = get_report_settings()
        layout_code = {
            'جدول كامل': 'full_table',
            'جدول مدمج': 'compact_table',
            'بطاقات': 'cards',
        }
        by_key = {c.get('key'): dict(c) for c in settings.get('account_statement_columns', [])}
        for key, checkbox, label_field in getattr(self, 'report_columns', []):
            if key in by_key:
                by_key[key]['visible'] = bool(checkbox.value)
                by_key[key]['label'] = label_field.value or by_key[key].get('label', key)
        ordered = []
        for c in settings.get('account_statement_columns', []):
            if c.get('key') in by_key:
                ordered.append(by_key[c.get('key')])
        save_report_settings({
            'header_note': self.report_header_note.value,
            'footer_note': self.report_footer_note.value,
            'show_company_logo': bool(self.report_show_logo.value),
            'show_company_contact': bool(self.report_show_contact.value),
            'show_generated_at': bool(self.report_show_generated_at.value),
            'show_statement_summary': bool(self.report_show_summary.value),
            'show_reconciliation_note': bool(self.report_show_reconciliation_note.value),
            'statement_use_colors': bool(self.report_use_colors.value),
            'shorten_long_references': bool(self.report_shorten_refs.value),
            'reconciliation_layout_mode': layout_code.get(self.report_reconciliation_layout.value, 'compact_table'),
            'whatsapp_statement_layout_mode': layout_code.get(self.report_whatsapp_layout.value, 'compact_table'),
            'print_statement_layout_mode': layout_code.get(self.report_print_layout.value, 'full_table'),
            'account_statement_columns': ordered,
        })
        self._show_snackbar("تم حفظ إعدادات التقارير والطباعة", False)

    def _lang_theme_tab(self):
        cur_lang = self.repo.get('language','ar')
        cur_theme = self.repo.get('theme','light')
        self.lang_dropdown = ft.Dropdown(
            label="اللغة",
            value=language_label(cur_lang),
            options=[ft.dropdown.Option("العربية"), ft.dropdown.Option("English"), ft.dropdown.Option("Français")],
            width=250
        )
        self.theme_dropdown = ft.Dropdown(
            label="المظهر",
            value="فاتح" if cur_theme=='light' else "داكن",
            options=[ft.dropdown.Option("فاتح"), ft.dropdown.Option("داكن")],
            width=250
        )
        lang_btn = ft.FilledButton(content=ft.Text("تغيير اللغة"), bgcolor=PRIMARY, color=ft.Colors.WHITE, on_click=self._save_language)
        theme_btn = ft.FilledButton(content=ft.Text("تطبيق المظهر"), bgcolor=PRIMARY, color=ft.Colors.WHITE, on_click=self._save_theme)
        return ft.Column([self.lang_dropdown, lang_btn, ft.Divider(), self.theme_dropdown, theme_btn], spacing=15)

    def _save_language(self, e):
        new_lang = language_code_from_label(self.lang_dropdown.value)
        self.repo.set('language', new_lang)
        set_language(new_lang)
        self._page.rtl = is_rtl(new_lang)
        self._page.title = translate('app_title')
        rebuild = getattr(self._page, '_hawaa_rebuild_main', None)
        if callable(rebuild):
            rebuild()
        else:
            self._show_snackbar(translate('language_applied'), is_error=False)
            self._page.update()

    def _save_theme(self, e):
        theme = 'light' if self.theme_dropdown.value == 'فاتح' else 'dark'
        self.repo.set('theme', theme)
        self._page.theme_mode = ft.ThemeMode.LIGHT if theme == 'light' else ft.ThemeMode.DARK
        self._show_snackbar("تم تغيير المظهر", is_error=False)
        self._page.update()

    def _network_tab(self):
        db = DatabaseConnection()
        current_mode = db.mode

        self.mode_dropdown = ft.Dropdown(
            label="وضع التشغيل",
            value="محلي" if current_mode == "local" else "عميل",
            options=[ft.dropdown.Option("محلي"), ft.dropdown.Option("عميل")],
            width=250
        )
        self.server_url = ft.TextField(
            label="عنوان الخادم (للعميل)",
            value=db.server_url,
            width=350,
            hint_text="http://192.168.1.100:8000"
        )
        self.network_test_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.NETWORK_CHECK), ft.Text("اختبار الاتصال")]),
            on_click=self._test_connection
        )
        self.network_save_btn = ft.FilledButton(
            content=ft.Text("حفظ"),
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._save_network
        )
        self.qr_pair_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.QR_CODE_SCANNER), ft.Text("ربط عبر QR")]),
            on_click=self._open_qr_pairing_dialog,
        )
        self.network_diag = ft.Column(spacing=6)
        self.network_diag_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.MEDICAL_INFORMATION_OUTLINED), ft.Text("تشخيص الشبكة")]),
            on_click=self._show_network_diagnostics,
        )
        return ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Text("الحالة الحالية", size=13, weight=ft.FontWeight.BOLD, expand=True),
                    network_status_chip(),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
                padding=12,
            ),
            info_banner("نسخة APK تعمل كمحلي أو عميل فقط. شغّل الخادم من مجلد server/ على جهاز آخر.", icon=ft.Icons.PHONE_ANDROID),
            self.mode_dropdown,
            self.server_url,
            ft.Text("في وضع العميل استخدم IP جهاز الخادم داخل الشبكة، مثل http://192.168.1.100:8000، وليس localhost.", size=11, color=ft.Colors.GREY_600),
            info_banner("الأفضل للربط: افتح Windows > الإعدادات > الشبكة > ربط Android، ثم امسح QR أو الصق نص QR هنا. الربط لا يسجّل الدخول؛ ستحتاج اسم المستخدم وكلمة المرور بعده.", icon=ft.Icons.QR_CODE),
            responsive_wrap([self.network_test_btn, self.network_diag_btn, self.network_save_btn, self.qr_pair_btn], spacing=10),
            self.network_diag,
        ], spacing=15)


    def _open_qr_pairing_dialog(self, e):
        if not self._require_admin():
            return
        from views.dialogs.qr_pairing_dialog import open_qr_pairing_dialog

        def on_success(result):
            self.server_url.value = result.server_url
            self.mode_dropdown.value = "عميل"
            logout_hook = getattr(self._page, '_hawaa_logout', None)
            if callable(logout_hook):
                logout_hook()

        return open_qr_pairing_dialog(self._page, on_success=on_success)

    def _normalize_server_url(self):
        from services.network_service import NetworkService
        return NetworkService.normalize_server_url(self.server_url.value or "")

    def _is_forbidden_client_url(self, url: str) -> bool:
        try:
            from services.network_service import NetworkService
            NetworkService.normalize_server_url(url)
            return False
        except ValueError:
            return True

    def _render_network_diagnostics(self, title: str, message: str, steps=None, technical: str = ""):
        steps = list(steps or [])
        controls = [
            ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.BLUE_700), ft.Text(title, weight=ft.FontWeight.BOLD, expand=True)]),
            ft.Text(message, size=12, color=ft.Colors.GREY_800),
        ]
        if steps:
            controls.append(ft.Text("خطوات الفحص:", size=12, weight=ft.FontWeight.BOLD))
            controls.extend([ft.Text(f"• {x}", size=11, color=ft.Colors.GREY_700) for x in steps])
        if technical:
            controls.append(ft.Text("تفاصيل تقنية:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600))
            controls.append(ft.Container(
                content=ft.Text(technical, size=10, selectable=True, color=ft.Colors.GREY_700),
                bgcolor=ft.Colors.GREY_100,
                border_radius=10,
                padding=8,
            ))
        self.network_diag.controls = [ft.Container(content=ft.Column(controls, spacing=5), bgcolor=ft.Colors.BLUE_50, border_radius=14, padding=12)]
        self._page.update()

    def _show_network_diagnostics(self, e=None):
        try:
            from services.network_diagnostics_service import build_diagnostic_steps
            url = self._normalize_server_url()
            self._render_network_diagnostics(
                "تشخيص الاتصال",
                "إذا فشل الربط، اختبر الرابط من متصفح الهاتف أولًا. QR لا يحل مشكلة الشبكة إذا كان الهاتف لا يصل إلى خادم Windows.",
                build_diagnostic_steps(url),
            )
        except Exception as ex:
            self._show_snackbar(f"تعذر بناء التشخيص: {ex}", True)

    def _test_connection(self, e):
        if not self._require_admin():
            return
        try:
            if hasattr(self, 'network_test_btn'):
                self.network_test_btn.disabled = True
                self.network_test_btn.content = ft.Row([ft.ProgressRing(width=16, height=16), ft.Text("جاري الاختبار")])
                self._page.update()
            from services.network_service import NetworkService
            from services.network_diagnostics_service import build_diagnostic_steps
            result = NetworkService.check_connection(self.server_url.value or "")
            self._show_snackbar(("✅ " if result.ok else "❌ ") + result.message, is_error=not result.ok)
            if result.ok:
                self.network_diag.controls = [ft.Container(content=ft.Text(result.message, size=12, color=ft.Colors.GREEN_800), bgcolor=ft.Colors.GREEN_50, border_radius=12, padding=10)]
                self._page.update()
            else:
                self._render_network_diagnostics("فشل الاتصال", result.message, build_diagnostic_steps(result.server_url or self.server_url.value or ""))
        except Exception as ex:
            from services.network_diagnostics_service import classify_connection_error, build_diagnostic_steps
            url = self.server_url.value or ""
            hint = classify_connection_error(url, ex)
            self._show_snackbar(f"❌ {hint.title}", True)
            self._render_network_diagnostics(hint.title, hint.message, build_diagnostic_steps(url), hint.technical)
        finally:
            if hasattr(self, 'network_test_btn'):
                self.network_test_btn.disabled = False
                self.network_test_btn.content = ft.Row([ft.Icon(ft.Icons.NETWORK_CHECK), ft.Text("اختبار الاتصال")])
                self._page.update()

    def _save_network(self, e):
        if not self._require_admin():
            return
        mode_map = {"محلي": "local", "عميل": "client"}
        new_mode = mode_map.get(self.mode_dropdown.value, "local")
        try:
            if hasattr(self, 'network_save_btn'):
                self.network_save_btn.disabled = True
                self.network_save_btn.content = ft.Row([ft.ProgressRing(width=16, height=16), ft.Text("جاري الحفظ")])
                self._page.update()
            from services.network_service import NetworkService
            old_mode = DatabaseConnection().mode
            NetworkService.save_mode(new_mode, self.server_url.value or "")
            if old_mode != new_mode:
                self._show_snackbar("تم حفظ وضع الشبكة. يجب تسجيل الدخول من جديد.", is_error=False)
                try:
                    from views.flet_compat import close_all_dialogs
                    close_all_dialogs(self._page)
                except Exception:
                    pass
                logout_hook = getattr(self._page, '_hawaa_logout', None)
                if callable(logout_hook):
                    logout_hook()
                return
            self._show_snackbar("تم حفظ إعدادات الشبكة", is_error=False)
        except Exception as ex:
            self._show_snackbar(f"❌ {str(ex)}", True)
        finally:
            if hasattr(self, 'network_save_btn'):
                self.network_save_btn.disabled = False
                self.network_save_btn.content = ft.Text("حفظ")
                self._page.update()

    def _backup_tab(self):
        backup_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.BACKUP), ft.Text("إنشاء ومشاركة نسخة احتياطية")]),
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE,
            on_click=self._perform_backup
        )
        export_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.IOS_SHARE), ft.Text("تصدير CSV ومشاركته")]),
            on_click=self._export_csv
        )
        import_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.RESTORE), ft.Text("استيراد نسخة احتياطية خارجية")]),
            on_click=self._pick_backup_to_restore
        )
        import_latest_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.RESTORE), ft.Text("استيراد آخر نسخة محفوظة داخليًا")]),
            on_click=self._restore_latest_internal_backup
        )
        import_download_btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN), ft.Text("استيراد من Download/Hawaa")]),
            on_click=self._restore_from_public_downloads
        )
        restore_diag_btn = ft.TextButton(
            content=ft.Row([ft.Icon(ft.Icons.BUG_REPORT_OUTLINED), ft.Text("تشخيص الاستيراد")]),
            on_click=self._show_restore_diagnostics
        )
        vacuum_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.COMPRESS), ft.Text("ضغط قاعدة البيانات")]),
            on_click=self._vacuum_db
        )
        reset_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.WARNING), ft.Text("إعادة تهيئة النظام")]),
            bgcolor=ft.Colors.RED,
            color=ft.Colors.WHITE,
            on_click=self._reset_db_dialog
        )
        return ft.Column([
            info_banner(
                "استيراد النسخة الخارجية يستخدم منتقي ملفات Android أولًا. إذا لم يرجع المنتقي نتيجة، استخدم زر Download/Hawaa أو افتح التشخيص. لا يتم طلب صلاحيات التخزين داخل زر الاستيراد حتى لا يتجمد الحدث.",
                icon=ft.Icons.FOLDER_SHARED,
            ),
            backup_btn,
            export_btn,
            import_btn,
            import_latest_btn,
            import_download_btn,
            restore_diag_btn,
            vacuum_btn,
            ft.Divider(),
            ft.Text("⚠️ إعادة التهيئة تحذف جميع البيانات نهائياً", color=ft.Colors.RED, size=12),
            reset_btn
        ], spacing=15)

    async def _perform_backup(self, e):
        if not self._require_admin():
            return
        try:
            from services.file_export_service import FileExportService
            backup_path = FileExportService.create_backup_archive()
            result = await FileExportService.share_file_async(
                self._page,
                backup_path,
                "نسخة احتياطية من نظام هوى الشام. احتفظ بها في مكان آمن.",
                open_whatsapp=False,
                title="مشاركة نسخة احتياطية",
            )
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء النسخة الاحتياطية: {backup_path}", is_error=not result.ok)
        except Exception as ex:
            self._show_snackbar(f"فشل النسخ الاحتياطي: {str(ex)}", True)

    async def _export_csv(self, e):
        if not self._require_admin():
            return
        try:
            from services.file_export_service import FileExportService
            export_path = FileExportService.create_csv_archive(['expenses', 'users', 'audit_log'])
            result = await FileExportService.share_file_async(
                self._page,
                export_path,
                "تصدير CSV من نظام هوى الشام.",
                open_whatsapp=False,
                title="مشاركة تصدير CSV",
            )
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء ملف CSV: {export_path}", is_error=not result.ok)
        except Exception as ex:
            self._show_snackbar(f"فشل التصدير: {str(ex)}", True)

    def _pick_backup_to_restore(self, e):
        if not self._require_admin():
            return
        """Open Android FilePicker without blocking the click handler.

        Earlier phases requested storage permission before opening the picker.
        On some Android/Flet 0.28.x builds PermissionHandler blocks the UI event
        thread; the button then looks completely dead.  SAF/FilePicker does not
        need broad storage permission to hand the selected file to the app, so we
        open the picker immediately and run a watchdog that shows diagnostics if
        the native chooser never calls back into Python.
        """
        try:
            from database.connection import DatabaseConnection
            from services.file_export_service import FileExportService
            if DatabaseConnection().is_remote():
                self._show_snackbar("أنت في وضع العميل. الاستعادة تتم من نسخة Windows فقط. غيّر الوضع إلى محلي لاستعادة نسخة داخل الهاتف.", True)
                return

            self._restore_picker_result_seen = False
            self._show_snackbar("جاري فتح اختيار النسخة الاحتياطية...", False, duration=1800)
            FileExportService.log_restore_event("restore picker button tapped")

            self._restore_file_picker = make_file_picker(self._on_restore_backup_picked)
            picker = self._restore_file_picker
            attach_service_control(self._page, picker)
            if not service_control_attached(picker):
                FileExportService.log_restore_event("restore picker not attached; opening fallback dialog")
                self._open_restore_fallback_dialog(filepicker_unavailable_message())
                return

            pick_kwargs = dict(
                allow_multiple=False,
                allowed_extensions=["zip", "db", "sqlite", "sqlite3"],
                dialog_title="اختيار نسخة هوى الشام الاحتياطية",
            )
            try:
                pick_kwargs["file_type"] = ft.FilePickerFileType.CUSTOM
            except Exception:
                pass
            try:
                import datetime as _dt
                self._restore_picker_opened_at = _dt.datetime.now().isoformat(timespec="seconds")
            except Exception:
                self._restore_picker_opened_at = "started"

            # Start watchdog after the native chooser is requested.  It does not
            # restore anything by itself; it only proves that the click handler is
            # alive and gives the user a deterministic fallback if on_result is
            # lost by the Android runtime.
            run_async_task(self._page, self._restore_picker_watchdog)

            try:
                FileExportService.log_restore_event("opening native picker with_data=True")
                picker.pick_files(with_data=True, **pick_kwargs)
            except TypeError:
                FileExportService.log_restore_event("with_data unsupported; opening picker without bytes")
                picker.pick_files(**pick_kwargs)
        except Exception as ex:
            try:
                from services.file_export_service import FileExportService
                FileExportService.log_restore_event(f"restore picker open failed: {ex}")
            except Exception:
                pass
            self._show_snackbar(f"تعذر فتح اختيار النسخة: {ex}", True)

    async def _restore_picker_watchdog(self):
        try:
            await asyncio.sleep(18)
            if bool(getattr(self, "_restore_picker_result_seen", False)):
                return
            from services.file_export_service import FileExportService
            FileExportService.log_restore_event("restore picker watchdog: no on_result after timeout")
            self._open_restore_fallback_dialog(
                "تم فتح منتقي الملفات، لكن لم يرجع أي نتيجة إلى التطبيق خلال المهلة. "
                "هذا يعني أن المشكلة في callback الخاص بـ Flet/Android وليس في قاعدة البيانات. "
                "ضع ملف النسخة في Download/Hawaa ثم اضغط زر: استيراد من Download/Hawaa.\n\n"
                f"سجل التشخيص: {FileExportService.restore_log_path()}"
            )
        except Exception as ex:
            try:
                self._show_snackbar(f"تعذر تشغيل تشخيص المنتقي: {ex}", True)
            except Exception:
                pass

    def _restore_from_public_downloads(self, e=None):
        if not self._require_admin():
            return
        """Start public-folder import scan in the background.

        The old implementation scanned Downloads synchronously and also tried to
        request runtime storage permission inside the click event.  On Android
        this can make the button look unresponsive.  Now the button immediately
        shows feedback, then scans in a task/thread.
        """
        self._show_snackbar("جاري البحث عن نسخ في Download/Hawaa...", False, duration=2000)
        run_async_task(self._page, self._restore_from_public_downloads_async)

    async def _restore_from_public_downloads_async(self):
        try:
            from database.connection import DatabaseConnection
            if DatabaseConnection().is_remote():
                self._show_snackbar("أنت في وضع العميل. الاستعادة تتم من نسخة Windows فقط. غيّر الوضع إلى محلي أولاً.", True)
                return
            from services.file_export_service import FileExportService
            FileExportService.log_restore_event("scan external downloads requested")

            # Do the filesystem walk/ZIP validation away from the UI callback.
            try:
                found = await asyncio.to_thread(FileExportService.find_external_backup_archives, 8, validate=True)
            except AttributeError:
                found = FileExportService.find_external_backup_archives(limit=8, validate=True)

            if not found:
                log_path = FileExportService.restore_log_path()
                self._show_snackbar("لم أجد نسخة صالحة في Download/Hawaa أو Download.", True)
                self._open_restore_fallback_dialog(
                    "لم يتم العثور على ZIP/DB صالح في المجلدات العامة. "
                    "انقل النسخة إلى Download/Hawaa ثم اضغط زر: استيراد من Download/Hawaa.\n\n"
                    f"سجل التشخيص: {log_path}"
                )
                return
            controls = [
                info_banner("اختر النسخة الخارجية التي تريد استعادتها. سيتم عرض تأكيد قبل الاستيراد.", icon=ft.Icons.FOLDER_OPEN)
            ]
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("نسخ خارجية تم العثور عليها", weight=ft.FontWeight.BOLD),
                content=ft.Container(width=460, content=ft.Column(controls, tight=True, spacing=8, scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton("إغلاق", on_click=lambda ev: self._close_dialog(dlg))],
            )
            for path in found:
                try:
                    label = FileExportService.describe_backup_file(path)
                except Exception:
                    label = os.path.basename(path)
                controls.append(
                    ft.OutlinedButton(
                        content=ft.Row([ft.Icon(ft.Icons.ARCHIVE_OUTLINED), ft.Text(label, overflow=ft.TextOverflow.ELLIPSIS)], alignment=ft.MainAxisAlignment.START),
                        on_click=lambda ev, p=path, d=dlg: self._restore_from_fallback_path(p, d),
                    )
                )
            open_control(self._page, dlg)
        except Exception as ex:
            try:
                from services.file_export_service import FileExportService
                FileExportService.log_restore_event(f"scan external downloads failed: {ex}")
            except Exception:
                pass
            self._show_snackbar(f"فشل فحص النسخ الخارجية: {ex}", True)

    def _restore_latest_internal_backup(self, e=None):
        if not self._require_admin():
            return
        try:
            from database.connection import DatabaseConnection
            if DatabaseConnection().is_remote():
                self._show_snackbar("أنت في وضع العميل. الاستعادة تتم من نسخة Windows فقط. غيّر الوضع إلى محلي لاستعادة نسخة داخل الهاتف.", True)
                return
            from services.file_export_service import FileExportService
            recent = FileExportService.find_recent_backup_archives(limit=1)
            if not recent:
                self._show_snackbar("لا توجد نسخة محفوظة داخليًا. أنشئ نسخة احتياطية أولًا أو اختر ملف ZIP/DB من منتقي الملفات.", True)
                return
            path = recent[0]
            info = FileExportService.inspect_backup_archive(path)
            counts = info.get('counts', {})
            msg = (
                "سيتم استيراد آخر نسخة محفوظة داخل التطبيق واستبدال البيانات الحالية. سيتم إنشاء نسخة أمان قبل الاستعادة.\n\n"
                f"المصدر: {os.path.basename(path)}\n"
                f"المستخدمون: {counts.get('users', 0)} | القيود: {counts.get('expenses', 0)} | سجل التدقيق: {counts.get('audit_log', 0)}"
            )
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("استيراد آخر نسخة محفوظة", weight=ft.FontWeight.BOLD),
                content=ft.Text(msg, selectable=True),
                actions=[
                    ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg)),
                    ft.FilledButton("استيراد الآن", bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=lambda ev, p=path, d=dlg: self._confirm_restore_backup(p, d)),
                ],
            )
            open_control(self._page, dlg)
        except Exception as ex:
            self._show_snackbar(f"تعذر استيراد آخر نسخة محفوظة: {ex}", True)


    def _open_restore_fallback_dialog(self, reason: str = ""):
        """Fallback restore path when Flet FilePicker is not available on APK."""
        try:
            from services.file_export_service import FileExportService
            recent = FileExportService.find_recent_backup_archives(limit=6)
        except Exception:
            recent = []
        path_field = ft.TextField(
            label="مسار ملف النسخة داخل تخزين التطبيق",
            hint_text="مثال: /data/user/0/.../hawaa_backup_....zip",
            multiline=True,
            min_lines=1,
            max_lines=3,
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            expand=True,
        )
        recent_controls = []
        if recent:
            recent_controls.append(ft.Text("نسخ أنشأها التطبيق مؤخرًا:", size=12, weight=ft.FontWeight.BOLD))
            for path in recent:
                try:
                    label = FileExportService.describe_backup_file(path)
                except Exception:
                    label = os.path.basename(path)
                recent_controls.append(
                    ft.OutlinedButton(
                        content=ft.Row([ft.Icon(ft.Icons.ARCHIVE_OUTLINED), ft.Text(label, overflow=ft.TextOverflow.ELLIPSIS)], alignment=ft.MainAxisAlignment.START),
                        on_click=lambda ev, p=path: self._restore_from_fallback_path(p, dlg),
                    )
                )
        else:
            recent_controls.append(ft.Text("لم يتم العثور على نسخ احتياطية داخل تخزين التطبيق. أنشئ نسخة أولًا أو الصق مسار ملف ZIP/DB يدويًا.", size=11, color=ft.Colors.GREY_700))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("استيراد نسخة احتياطية بدون FilePicker", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=430,
                content=ft.Column([
                    info_banner("نسخة Flet/Android الحالية لا تدعم منتقي الملفات. يمكنك استيراد آخر نسخة أنشأها التطبيق أو لصق مسار ملف ZIP/DB داخل تخزين التطبيق.", icon=ft.Icons.INFO),
                    ft.Text(reason or "", size=10, color=ft.Colors.GREY_600, selectable=True),
                    *recent_controls,
                    ft.Divider(),
                    path_field,
                ], tight=True, spacing=10),
            ),
            actions=[
                ft.FilledButton("استيراد من المسار", on_click=lambda ev: self._restore_from_fallback_path(path_field.value or "", dlg)),
                ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg)),
            ],
        )
        open_control(self._page, dlg)

    def _restore_from_fallback_path(self, path: str, dialog=None):
        path = (path or "").strip().strip('"').strip("'")
        if not path:
            self._show_snackbar("أدخل مسار النسخة أو اختر واحدة من القائمة", True)
            return
        try:
            if dialog is not None:
                self._close_dialog(dialog)
        except Exception:
            pass
        # Android/Flet dialog routing proved unreliable for restore confirmation:
        # the native picker can return a readable cache path, then the confirm
        # dialog may not appear to the user.  Because the user already pressed
        # an explicit restore action and selected/provided a backup, restore
        # directly with an automatic safety backup and full diagnostic logging.
        self._restore_selected_backup_path(path, origin="fallback-path")

    def _restore_selected_backup_path(self, path: str, *, origin: str = "unknown"):
        """Restore a selected backup directly and non-blockingly.

        Phase 61 intentionally removes the extra confirmation dialog from the
        Android path.  Diagnostics showed that FilePicker returned a readable
        cache file, but execution stopped before any import reached
        restore_backup_archive().  Direct restore gives deterministic behaviour:
        pick file -> validate/restore -> success/error dialog.  A safety backup
        of the current DB is created inside restore_backup_archive().
        """
        path = (path or "").strip().strip('"').strip("'")
        if not path:
            self._show_snackbar("لم يتم تحديد مسار نسخة احتياطية", True)
            return
        if self._restore_operation_busy:
            self._show_snackbar("توجد عملية استيراد قيد التنفيذ. انتظر حتى تنتهي.", True)
            return
        self._restore_operation_busy = True
        try:
            from services.file_export_service import FileExportService
            FileExportService.log_restore_event(f"direct restore requested from {origin}: {path}")
        except Exception:
            pass
        self._show_snackbar("تم اختيار النسخة. جاري التحقق والاستيراد الآن...", False, duration=2500)
        run_async_task(self._page, self._restore_selected_backup_path_async, path, origin)

    async def _restore_selected_backup_path_async(self, path: str, origin: str = "unknown"):
        try:
            from services.file_export_service import FileExportService
            from database.connection import DatabaseConnection
            try:
                FileExportService.log_restore_event(f"restore async start origin={origin} path={path}")
                inspected = await asyncio.to_thread(FileExportService.inspect_backup_archive, path)
                FileExportService.log_restore_event(f"restore inspect ok origin={origin} info={inspected}")
                result = await asyncio.to_thread(FileExportService.restore_backup_archive, path)
            except AttributeError:
                FileExportService.log_restore_event(f"restore async fallback sync origin={origin} path={path}")
                inspected = FileExportService.inspect_backup_archive(path)
                FileExportService.log_restore_event(f"restore inspect ok origin={origin} info={inspected}")
                result = FileExportService.restore_backup_archive(path)
            safety = result.get('safety_backup')
            counts = result.get('verified_counts') or (result.get('inspected') or {}).get('counts', {})
            try:
                DatabaseConnection.reset_after_restore()
            except Exception:
                pass
            try:
                FileExportService.log_restore_event(f"restore ui refresh start counts={counts}")
            except Exception:
                pass
            self._refresh_after_restore()
            self._show_restore_success_dialog(counts, safety)
        except Exception as ex:
            try:
                from services.file_export_service import FileExportService
                FileExportService.log_restore_event(f"direct restore failed origin={origin} path={path}: {ex}")
            except Exception:
                pass
            self._open_restore_error_dialog(path, ex)
        finally:
            self._restore_operation_busy = False

    def _open_restore_error_dialog(self, path: str, error: Exception):
        try:
            from services.file_export_service import FileExportService
            log_tail = "\n".join(FileExportService.read_restore_log_tail(30))
            log_path = FileExportService.restore_log_path()
        except Exception:
            log_tail = ""
            log_path = ""
        msg = (
            "فشل استيراد النسخة الاحتياطية. لم يتم استبدال قاعدة البيانات الحالية.\n\n"
            f"المسار: {path}\n"
            f"الخطأ: {error}\n\n"
            f"سجل التشخيص: {log_path}\n\n"
            f"آخر السجل:\n{log_tail}"
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("فشل استيراد النسخة", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=430, content=ft.Text(msg, selectable=True, size=11)),
            actions=[ft.TextButton("إغلاق", on_click=lambda ev: self._close_dialog(dlg))],
        )
        try:
            open_control(self._page, dlg)
        except Exception:
            self._show_snackbar(f"فشل استيراد النسخة: {error}", True)

    def _open_logo_path_fallback_dialog(self, reason: str = ""):
        path_field = ft.TextField(
            label="مسار صورة الشعار داخل تخزين التطبيق",
            hint_text="PNG / JPG / WEBP",
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("اختيار شعار بدون FilePicker", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column([
                    info_banner("نسخة Flet/Android الحالية لا تدعم منتقي الملفات. انسخ صورة الشعار إلى تخزين التطبيق أو أدخل مسارًا قابلًا للقراءة.", icon=ft.Icons.IMAGE),
                    ft.Text(reason or "", size=10, color=ft.Colors.GREY_600, selectable=True),
                    path_field,
                ], tight=True, spacing=10),
            ),
            actions=[
                ft.FilledButton("استخدام هذا الشعار", on_click=lambda ev: self._import_logo_from_path(path_field.value or "", dlg)),
                ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg)),
            ],
        )
        open_control(self._page, dlg)

    def _import_logo_from_path(self, source_path: str, dialog=None):
        source_path = (source_path or "").strip().strip('"').strip("'")
        if not source_path:
            self._show_snackbar("أدخل مسار صورة الشعار", True)
            return
        try:
            if dialog is not None:
                self._close_dialog(dialog)
            from services.company_logo_service import import_logo
            stored = import_logo(source_path)
            self.company_logo.value = stored
            self.logo_preview.content = self._logo_preview_control(stored)
            self._show_snackbar("تم اختيار الشعار وسيُستخدم في الطباعة", False)
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"فشل اختيار الشعار من المسار: {ex}", True)

    def _on_restore_backup_picked(self, e):
        try:
            self._restore_picker_result_seen = True
            self._show_snackbar("تم استلام الملف من Android، جاري فحص النسخة...", False, duration=1800)
            from services.file_export_service import FileExportService
            try:
                FileExportService.log_restore_event("on_result received: " + str(e))
            except Exception:
                pass
            files = getattr(e, 'files', None) or []
            if not files:
                FileExportService.log_restore_event("on_result without files")
                self._show_snackbar("لم يتم اختيار ملف", False)
                return
            selected = files[0]
            path = FileExportService.resolve_picker_file_path(selected)
            if not path:
                details = FileExportService.describe_picker_file(selected)
                # Last automatic fallback: maybe the picker returned only a
                # display name and the file is readable in Download/Hawaa after
                # storage permission.
                try:
                    external = FileExportService.find_external_backup_archives(limit=1, validate=True)
                except Exception:
                    external = []
                if external:
                    path = external[0]
                    FileExportService.log_restore_event("using external scan fallback: " + path)
                else:
                    self._open_restore_fallback_dialog(
                        "فتح Android منتقي الملفات، لكن Runtime لم يعطِ التطبيق مسارًا ولا bytes قابلة للاستيراد. "
                        "هذا يحدث غالبًا بسبب صلاحيات/Scoped Storage أو بسبب أن FilePicker في Flet فتح النافذة ولم يسلّم الملف إلى Python. "
                        "كحل ثابت: ضع الملف في Download/Hawaa ثم اضغط زر: استيراد من Download/Hawaa.\n\n"
                        f"تشخيص الملف المختار: {details}\n"
                        f"سجل التشخيص: {FileExportService.restore_log_path()}"
                    )
                    return
            FileExportService.log_restore_event(f"resolved picker backup path: {path}")
            self._restore_selected_backup_path(path, origin="filepicker")
        except Exception as ex:
            try:
                from services.file_export_service import FileExportService
                FileExportService.log_restore_event(f"restore picker handler failed: {ex}")
            except Exception:
                pass
            self._open_restore_error_dialog("FilePicker", ex)

    def _confirm_restore_backup(self, path: str, dialog):
        try:
            self._close_dialog(dialog)
        except Exception:
            pass
        self._show_snackbar("جاري استيراد النسخة الاحتياطية...", False, duration=2500)
        run_async_task(self._page, self._confirm_restore_backup_async, path)

    async def _confirm_restore_backup_async(self, path: str):
        try:
            from services.file_export_service import FileExportService
            from database.connection import DatabaseConnection
            try:
                result = await asyncio.to_thread(FileExportService.restore_backup_archive, path)
            except AttributeError:
                result = FileExportService.restore_backup_archive(path)
            safety = result.get('safety_backup')
            counts = result.get('verified_counts') or (result.get('inspected') or {}).get('counts', {})
            try:
                DatabaseConnection.reset_after_restore()
            except Exception:
                pass
            self._refresh_after_restore()
            self._show_restore_success_dialog(counts, safety)
        except Exception as ex:
            try:
                from services.file_export_service import FileExportService
                FileExportService.log_restore_event(f"restore failed in async confirm: {ex}")
            except Exception:
                pass
            self._show_snackbar(f"فشل استيراد النسخة: {ex}", True)

    def _show_restore_success_dialog(self, counts: dict, safety_backup: str | None = None):
        try:
            msg = (
                "تم استيراد النسخة الاحتياطية والتحقق من قاعدة البيانات.\n\n"
                f"المستخدمون: {int((counts or {}).get('users', 0))}\n"
                f"القيود: {int((counts or {}).get('expenses', 0))}\n"
                f"سجل التدقيق: {int((counts or {}).get('audit_log', 0))}\n"
                f"سداد بالنيابة: {int((counts or {}).get('third_party_payments', 0))}"
            )
            if safety_backup:
                msg += f"\n\nتم حفظ نسخة أمان من البيانات السابقة: {os.path.basename(safety_backup)}"
            dlg = ft.AlertDialog(
                title=ft.Text("تم الاستيراد بنجاح", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN),
                content=ft.Text(msg, selectable=True),
                actions=[
                    ft.FilledButton("فتح حسابات هوى الشام", on_click=lambda ev: self._after_restore_open_accounts(dlg)),
                    ft.TextButton("إغلاق", on_click=lambda ev: self._close_dialog(dlg)),
                ],
            )
            open_control(self._page, dlg)
        except Exception:
            self._show_snackbar("تم استيراد النسخة الاحتياطية بنجاح", False)

    def _refresh_after_restore(self):
        try:
            clear_transient_ui(self._page, clear_fab=True)
        except Exception:
            pass
        try:
            rebuild = getattr(self._page, '_hawaa_rebuild_main', None)
            if callable(rebuild):
                rebuild()
                return
        except Exception:
            pass
        try:
            refresh = getattr(self._page, '_hawaa_refresh_current_page', None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    def _after_restore_open_accounts(self, dialog):
        try:
            self._close_dialog(dialog)
        except Exception:
            pass
        try:
            open_page = getattr(self._page, '_hawaa_open_page', None)
            if callable(open_page):
                open_page('accounts')
                return
        except Exception:
            pass
        self._refresh_after_restore()

    def _show_restore_diagnostics(self, e=None):
        if not self._require_admin():
            return
        try:
            from services.file_export_service import FileExportService
            log_path = FileExportService.restore_log_path()
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()[-25:]
                log_text = "\n".join(lines) or "لا يوجد سجل بعد."
            except Exception as ex:
                log_text = f"تعذر قراءة السجل: {ex}"
            roots = "\n".join(FileExportService._public_import_roots())
            msg = (
                "تشخيص استيراد النسخ الاحتياطية\n\n"
                f"آخر فتح للمنتقي: {self._restore_picker_opened_at or 'لم يفتح بعد'}\n"
                f"وصلت نتيجة من المنتقي: {'نعم' if self._restore_picker_result_seen else 'لا'}\n"
                f"مسار السجل: {log_path}\n\n"
                "مجلدات البحث:\n"
                f"{roots}\n\n"
                "آخر السجل:\n"
                f"{log_text}"
            )
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("تشخيص الاستيراد", weight=ft.FontWeight.BOLD),
                content=ft.Container(width=480, height=520, content=ft.Column([ft.Text(msg, selectable=True, size=11)], scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton("إغلاق", on_click=lambda ev: self._close_dialog(dlg))],
            )
            open_control(self._page, dlg)
        except Exception as ex:
            self._show_snackbar(f"تعذر عرض التشخيص: {ex}", True)

    def _vacuum_db(self, e):
        if not self._require_admin():
            return
        try:
            from database.connection import DatabaseConnection
            db = DatabaseConnection()
            if db.is_remote():
                self._show_snackbar("لا يمكن ضغط قاعدة البيانات في وضع العميل", True)
                return
            conn = db.get_connection()
            conn.execute("VACUUM")
            self._show_snackbar("تم ضغط قاعدة البيانات بنجاح", is_error=False)
        except Exception as ex:
            self._show_snackbar(f"فشل الضغط: {str(ex)}", True)

    def _reset_db_dialog(self, e):
        if not self._require_admin():
            return
        phrase = "حذف جميع بيانات هوى الشام"
        password = ft.TextField(
            label="كلمة مرور المدير الحالية", password=True, can_reveal_password=True,
            autofocus=True,
        )
        confirmation = ft.TextField(
            label="اكتب عبارة التأكيد", hint_text=phrase,
        )
        acknowledge = ft.Checkbox(
            label="أفهم أن العملية ستحذف القيود والمستخدمين والإعدادات المحلية",
            value=False,
        )
        progress = ft.Text("سيتم إنشاء نسخة أمان والتحقق منها قبل الحذف.", size=12, color=MUTED)

        def start_reset(ev):
            if confirmation.value.strip() != phrase:
                progress.value = "عبارة التأكيد غير مطابقة."
                progress.color = DANGER
                self._page.update()
                return
            if not acknowledge.value:
                progress.value = "يجب تأكيد فهم أثر العملية."
                progress.color = DANGER
                self._page.update()
                return
            if not (password.value or "").strip():
                progress.value = "كلمة مرور المدير مطلوبة."
                progress.color = DANGER
                self._page.update()
                return
            confirm_btn.disabled = True
            progress.value = "جاري التحقق وإنشاء نسخة الأمان..."
            progress.color = PRIMARY
            self._page.update()
            run_async_task(self._page, self._secure_reset_async, password.value, dlg)

        confirm_btn = ft.FilledButton(
            "إنشاء نسخة أمان ثم الحذف",
            bgcolor=DANGER, color=ft.Colors.WHITE, on_click=start_reset,
        )
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("إعادة تهيئة النظام", color=DANGER, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=500,
                content=ft.Column([
                    info_banner(
                        "هذه العملية محلية ونهائية. لن تبدأ قبل نجاح نسخة الأمان والتحقق من كلمة مرور المدير.",
                        icon=ft.Icons.GPP_MAYBE_OUTLINED, color=DANGER, bgcolor="#FDECEC",
                    ),
                    ft.Text(f"عبارة التأكيد المطلوبة: {phrase}", selectable=True, weight=ft.FontWeight.BOLD),
                    password, confirmation, acknowledge, progress,
                ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg)),
                confirm_btn,
            ],
        )
        open_control(self._page, dlg)

    async def _secure_reset_async(self, password_value, dialog):
        try:
            if not self._require_admin():
                return
            from database import UserRepository
            from services.file_export_service import FileExportService
            current = UserSession.get_current() or {}
            username = current.get("username") or ""
            try:
                verified = await asyncio.to_thread(UserRepository().authenticate, username, password_value)
            except AttributeError:
                verified = UserRepository().authenticate(username, password_value)
            if not verified:
                self._show_snackbar("كلمة مرور المدير غير صحيحة. لم يتم حذف أي بيانات.", True)
                return
            try:
                backup_path = await asyncio.to_thread(FileExportService.create_backup_archive)
                FileExportService.inspect_backup_archive(backup_path)
            except AttributeError:
                backup_path = FileExportService.create_backup_archive()
                FileExportService.inspect_backup_archive(backup_path)
            self._perform_reset(safety_backup=backup_path)
            self._close_dialog(dialog)
        except Exception as ex:
            self._show_snackbar(f"تم إيقاف إعادة التهيئة دون حذف البيانات: {ex}", True)

    def _perform_reset(self, safety_backup=None):
        if not self._require_admin():
            return
        if not safety_backup or not os.path.exists(safety_backup):
            self._show_snackbar("تعذر إثبات نسخة الأمان؛ تم إلغاء الحذف.", True)
            return
        try:
            from database.migrations import init_database
            from database.connection import DatabaseConnection
            db = DatabaseConnection()
            if db.is_remote():
                self._show_snackbar("لا يمكن إعادة التهيئة في وضع العميل", True)
                return
            conn = db.get_connection()
            conn.execute("BEGIN IMMEDIATE")
            for table in (
                "local_notification_schedule", "notification_state",
                "payment_allocations", "payments", "payment_batches", "payment_reminders",
                "service_case_components", "direct_services", "service_cases", "third_party_payments",
                "expenses", "exchange_rate_history", "users", "audit_log", "settings",
                "exchange_rates", "token_blacklist",
            ):
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            init_database()
            self._show_snackbar(
                f"تمت إعادة التهيئة بعد حفظ نسخة أمان: {os.path.basename(safety_backup)}",
                is_error=False, duration=6000,
            )
            run_async_task(self._page, self._restart_app)
        except Exception as ex:
            try:
                conn.rollback()
            except Exception:
                pass
            self._show_snackbar(f"فشل إعادة التهيئة: {str(ex)}", True)

    async def _restart_app(self):
        await asyncio.sleep(2)
        self._page.window.close()

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
