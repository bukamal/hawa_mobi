# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control
from views.ui_kit import page_header, data_card, show_snackbar, empty_state, info_banner, responsive_wrap
from database import SettingsRepository
from currency import currency
from i18n.translator import translate, set_language, language_code_from_label, language_label, is_rtl
from config import get_company_info, save_company_info
from database.connection import DatabaseConnection
from views.ui_runtime import network_status_chip
import datetime
import os
import shutil
import csv
import asyncio

class SettingsMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15
        self.scroll = ft.ScrollMode.AUTO
        self.repo = SettingsRepository()
        self.rate_fields = {}

        self.controls = [
            page_header(translate('settings'), ft.Icons.SETTINGS, subtitle="إعدادات النظام، الشبكة، النسخ الاحتياطي والعملات"),
            self._settings_tile("💰 العملات", self._currency_tab(), expanded=True),
            self._settings_tile("💱 أسعار الصرف", self._rates_tab()),
            self._settings_tile("🏢 الشركة", self._company_tab()),
            self._settings_tile("🖨️ التقارير والطباعة", self._reports_tab()),
            self._settings_tile("🌐 اللغة والمظهر", self._lang_theme_tab()),
            self._settings_tile("🌐 الشبكة", self._network_tab()),
            self._settings_tile("🔄 النسخ الاحتياطي", self._backup_tab()),
        ]

    def _settings_tile(self, title, content, expanded=False):
        return data_card(
            ft.ExpansionTile(
                title=ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                expanded=expanded,
                controls=[ft.Container(content=content, padding=ft.Padding(left=4, right=4, top=6, bottom=4))],
            ),
            padding=0,
            elevation=1,
        )

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

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
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_currency
        )
        return ft.Column([
            self.base_curr, self.display_curr, self.decimals,
            self.format_dropdown, self.abbreviate, save_btn
        ], spacing=15)

    def _save_currency(self, e):
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
        self.rates_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        refresh_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.REFRESH), ft.Text("تحديث من الإنترنت")]),
            on_click=self._fetch_online_rates
        )
        save_all_btn = ft.FilledButton(
            content=ft.Text("حفظ جميع الأسعار", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
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
                                    bgcolor=ft.Colors.INDIGO,
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
        remove_logo_btn = ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE), ft.Text("إزالة الشعار")]), on_click=self._remove_company_logo)
        save_btn = ft.FilledButton(content=ft.Text("حفظ"), bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._save_company)
        return ft.Column([
            self.company_name,
            self.company_address,
            self.company_phone,
            self.company_email,
            info_banner("يتم نسخ الشعار إلى تخزين التطبيق وإدخاله داخل تقارير HTML كصورة Base64 حتى يظهر عند الطباعة والمشاركة.", icon=ft.Icons.IMAGE),
            self.logo_preview,
            self.company_logo,
            responsive_wrap([logo_btn, remove_logo_btn, save_btn], spacing=10),
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
            ft.Text("لم يتم اختيار شعار بعد", size=12, color=ft.Colors.GREY_600),
        ], alignment=ft.MainAxisAlignment.START)

    def _save_company(self, e):
        info = {
            'name': self.company_name.value,
            'address': self.company_address.value,
            'phone': self.company_phone.value,
            'email': self.company_email.value,
            'logo_path': self.company_logo.value,
        }
        save_company_info(info)
        self._show_snackbar("تم حفظ معلومات الشركة", is_error=False)

    def _browse_logo(self, e):
        picker = ft.FilePicker(on_result=self._on_logo_picked)
        try:
            self._page.overlay.append(picker)
            self._page.update()
        except Exception:
            pass
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
        try:
            from services.company_logo_service import remove_logo
            remove_logo(self.company_logo.value)
        except Exception:
            pass
        self.company_logo.value = ""
        self.logo_preview.content = self._logo_preview_control("")
        self._show_snackbar("تم إزالة الشعار", False)
        self._page.update()


    def _reports_tab(self):
        from reports.config import get_report_settings
        settings = get_report_settings()
        self.report_header_note = ft.TextField(label="نص الرأس", value=settings.get('header_note', ''), width=350)
        self.report_footer_note = ft.TextField(label="نص التذييل", value=settings.get('footer_note', ''), width=350, multiline=True, min_lines=2, max_lines=3)
        self.report_show_logo = ft.Checkbox(label="إظهار شعار الشركة في الطباعة", value=bool(settings.get('show_company_logo', True)))
        self.report_show_generated_at = ft.Checkbox(label="إظهار تاريخ إنشاء التقرير", value=bool(settings.get('show_generated_at', True)))
        self.report_columns = []
        column_controls = []
        for col in settings.get('account_statement_columns', []):
            checkbox = ft.Checkbox(label=str(col.get('label', col.get('key'))), value=bool(col.get('visible', True)))
            label_field = ft.TextField(label="اسم العمود", value=str(col.get('label', '')), width=180)
            self.report_columns.append((str(col.get('key')), checkbox, label_field))
            column_controls.append(ft.Row([checkbox, label_field], spacing=8, wrap=True))
        save_btn = ft.FilledButton(content=ft.Text("حفظ إعدادات التقارير"), bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._save_reports)
        return ft.Column([
            info_banner("ترتيب كشف الحساب الافتراضي: التاريخ، الملاحظات، لنا، له، التراكمي. يمكن إظهار أعمدة إضافية مثل القيمة التاريخية للعملة."),
            self.report_header_note,
            self.report_footer_note,
            self.report_show_logo,
            self.report_show_generated_at,
            ft.Text("أعمدة كشف الحساب", size=14, weight=ft.FontWeight.BOLD),
            ft.Column(column_controls, spacing=4),
            save_btn,
        ], spacing=12)

    def _save_reports(self, e):
        from reports.config import get_report_settings, save_report_settings
        settings = get_report_settings()
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
            'show_generated_at': bool(self.report_show_generated_at.value),
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
        lang_btn = ft.FilledButton(content=ft.Text("تغيير اللغة"), bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._save_language)
        theme_btn = ft.FilledButton(content=ft.Text("تطبيق المظهر"), bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._save_theme)
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
            bgcolor=ft.Colors.INDIGO,
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
            content=ft.Row([ft.Icon(ft.Icons.RESTORE), ft.Text("استيراد نسخة احتياطية")]),
            on_click=self._pick_backup_to_restore
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
                "على Android لا يتم الحفظ في مسار ثابت. يتم إنشاء الملف داخل تخزين التطبيق ثم تفتح نافذة المشاركة لاختيار Files / Drive / WhatsApp / Telegram.",
                icon=ft.Icons.FOLDER_SHARED,
            ),
            backup_btn,
            export_btn,
            import_btn,
            vacuum_btn,
            ft.Divider(),
            ft.Text("⚠️ إعادة التهيئة تحذف جميع البيانات نهائياً", color=ft.Colors.RED, size=12),
            reset_btn
        ], spacing=15)

    async def _perform_backup(self, e):
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
        try:
            from database.connection import DatabaseConnection
            if DatabaseConnection().is_remote():
                self._show_snackbar("أنت في وضع العميل. الاستعادة تتم من نسخة Windows فقط. غيّر الوضع إلى محلي لاستعادة نسخة داخل الهاتف.", True)
                return
            picker = ft.FilePicker(on_result=self._on_restore_backup_picked)
            self._page.overlay.append(picker)
            self._page.update()
            picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["zip", "db", "sqlite", "sqlite3"],
                dialog_title="اختيار نسخة هوى الشام الاحتياطية",
            )
        except Exception as ex:
            self._show_snackbar(f"تعذر فتح اختيار النسخة: {ex}", True)

    def _on_restore_backup_picked(self, e):
        try:
            files = getattr(e, 'files', None) or []
            if not files:
                self._show_snackbar("لم يتم اختيار ملف", False)
                return
            selected = files[0]
            path = getattr(selected, 'path', None) or getattr(selected, 'name', None)
            if not path or not os.path.exists(path):
                self._show_snackbar("لم يستطع Android إعطاء مسار قابل للقراءة. احفظ النسخة في Files ثم أعد المحاولة.", True)
                return
            from services.file_export_service import FileExportService
            info = FileExportService.inspect_backup_archive(path)
            counts = info.get('counts', {})
            msg = (
                "سيتم استبدال قاعدة البيانات الحالية. سيتم إنشاء نسخة أمان قبل الاستعادة.\n\n"
                f"النوع: {info.get('format')}\n"
                f"إصدار المخطط: {info.get('schema_version') or 'غير محدد'}\n"
                f"المستخدمون: {counts.get('users', 0)} | القيود: {counts.get('expenses', 0)}"
            )
            dlg = ft.AlertDialog(
                title=ft.Text("تأكيد استيراد النسخة الاحتياطية", weight=ft.FontWeight.BOLD),
                content=ft.Text(msg),
                actions=[
                    ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg)),
                    ft.FilledButton("استيراد الآن", bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=lambda ev, p=path, d=dlg: self._confirm_restore_backup(p, d)),
                ],
            )
            open_control(self._page, dlg)
        except Exception as ex:
            self._show_snackbar(f"النسخة غير صالحة: {ex}", True)

    def _confirm_restore_backup(self, path: str, dialog):
        try:
            self._close_dialog(dialog)
            from services.file_export_service import FileExportService
            result = FileExportService.restore_backup_archive(path)
            safety = result.get('safety_backup')
            suffix = f" نسخة الأمان: {os.path.basename(safety)}" if safety else ""
            self._show_snackbar("تم استيراد النسخة الاحتياطية. أعد تشغيل التطبيق لتحديث كل الشاشات." + suffix, False)
            # Rebuild current page as much as possible; a full restart remains safest.
            refresh = getattr(self._page, '_hawaa_refresh_current_page', None)
            if callable(refresh):
                refresh()
        except Exception as ex:
            self._show_snackbar(f"فشل استيراد النسخة: {ex}", True)

    def _vacuum_db(self, e):
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
        def confirm_reset(e):
            self._perform_reset()
            self._close_dialog(dlg)
        dlg = ft.AlertDialog(
            title=ft.Text("⚠️ تحذير نهائي", color=ft.Colors.RED),
            content=ft.Text("سيتم حذف جميع القيود والمستخدمين وسجل التدقيق.\nلا يمكن التراجع عن هذا الإجراء.\nهل أنت متأكد؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm_reset),
                ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))
            ]
        )
        open_control(self._page, dlg)

    def _perform_reset(self):
        try:
            from database.migrations import init_database
            from database.connection import DatabaseConnection
            db = DatabaseConnection()
            if db.is_remote():
                self._show_snackbar("لا يمكن إعادة التهيئة في وضع العميل", True)
                return
            conn = db.get_connection()
            conn.execute("DROP TABLE IF EXISTS expenses")
            conn.execute("DROP TABLE IF EXISTS users")
            conn.execute("DROP TABLE IF EXISTS audit_log")
            conn.execute("DROP TABLE IF EXISTS settings")
            conn.execute("DROP TABLE IF EXISTS exchange_rates")
            conn.execute("DROP TABLE IF EXISTS token_blacklist")
            conn.commit()
            init_database()
            self._show_snackbar("تم إعادة تهيئة النظام بنجاح. يرجى إعادة تشغيل التطبيق.", is_error=False)
            asyncio.create_task(self._restart_app())
        except Exception as ex:
            self._show_snackbar(f"فشل إعادة التهيئة: {str(ex)}", True)

    async def _restart_app(self):
        await asyncio.sleep(2)
        self._page.window.close()

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
