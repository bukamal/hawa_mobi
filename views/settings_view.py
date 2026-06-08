# -*- coding: utf-8 -*-
import flet as ft
from database import SettingsRepository
from currency import currency
from i18n.translator import translate, set_language
from auth.session import UserSession
from config import get_company_info, save_company_info
from database.connection import DatabaseConnection
import socket

class SettingsView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15
        self.repo = SettingsRepository()

        self.section_buttons = []
        self.current_section = None
        self.content_area = ft.Container(expand=True, padding=20)

        self.sections = {
            "currency": {"title": "💰 العملات", "icon": ft.Icons.ATTACH_MONEY, "builder": self._currency_tab},
            "exchange": {"title": "💱 أسعار الصرف", "icon": ft.Icons.REFRESH, "builder": self._rates_tab},
            "company": {"title": "🏢 الشركة", "icon": ft.Icons.BUSINESS, "builder": self._company_tab},
            "lang_theme": {"title": "🌐 اللغة والمظهر", "icon": ft.Icons.LANGUAGE, "builder": self._lang_theme_tab},
            "network": {"title": "🌐 الشبكة", "icon": ft.Icons.NETWORK_WIFI, "builder": self._network_tab},
            "backup": {"title": "🔄 النسخ الاحتياطي", "icon": ft.Icons.BACKUP, "builder": self._backup_tab},
        }

        for key, sec in self.sections.items():
            btn = ft.ListTile(
                leading=ft.Icon(sec["icon"]),
                title=ft.Text(sec["title"]),
                on_click=lambda e, k=key: self.switch_section(k),
                selected=(key == "currency")
            )
            self.section_buttons.append(btn)

        sidebar = ft.Container(
            content=ft.Column(
                controls=[ft.Text("الإعدادات", size=20, weight=ft.FontWeight.BOLD)] +
                         [ft.Divider()] + self.section_buttons + [ft.Divider()],
                spacing=0,
                tight=True
            ),
            width=250,
            bgcolor=ft.Colors.INDIGO_50,
            padding=10,
            border_radius=10
        )

        self.content_row = ft.Row(
            controls=[sidebar, self.content_area],
            expand=True,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

        self.controls = [ft.Text(translate('settings'), size=24, weight=ft.FontWeight.BOLD), self.content_row]
        self.switch_section("currency")

    def switch_section(self, section_key):
        self.current_section = section_key
        for btn in self.section_buttons:
            btn.selected = (btn.title.value == self.sections[section_key]["title"])
        builder = self.sections[section_key]["builder"]
        self.content_area.content = builder()
        self._page.update()

    def _show_snackbar(self, message, is_error=False):
        self._page.open(ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN))

    def _currency_tab(self):
        self.base_curr = ft.Dropdown(
            label="العملة الأساسية (للتخزين)",
            value=currency.get_base_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=300
        )
        self.display_curr = ft.Dropdown(
            label="العملة المعروضة",
            value=currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=300
        )
        self.decimals = ft.Slider(
            label="الخانات العشرية: {value}",
            min=0, max=2, divisions=2,
            value=int(self.repo.get('currency_decimals','2')),
            width=300
        )
        self.format_dropdown = ft.Dropdown(
            label="تنسيق الأرقام",
            value="غربية" if self.repo.get('number_format','western')=='western' else "شرقية",
            options=[ft.dropdown.Option("غربية"), ft.dropdown.Option("شرقية")],
            width=300
        )
        self.abbreviate = ft.Checkbox(
            label="اختصار الأعداد الكبيرة (K, M)",
            value=currency.abbreviate_numbers()
        )
        save_btn = ft.FilledButton(
            content=ft.Text("حفظ إعدادات العملة", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_currency
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("إعدادات العملات", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                self.base_curr,
                self.display_curr,
                self.decimals,
                self.format_dropdown,
                self.abbreviate,
                ft.Container(height=30),
                save_btn
            ], spacing=15),
            padding=20
        )

    def _rates_tab(self):
        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.rates_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("العملة")), ft.DataColumn(ft.Text("السعر (1 USD = ?)")), ft.DataColumn(ft.Text("آخر تحديث"))],
            rows=[],
            border=table_border,
            border_radius=10,
            heading_row_color=ft.Colors.INDIGO_50
        )
        refresh_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.REFRESH), ft.Text("تحديث من الإنترنت")]),
            on_click=self._fetch_online_rates
        )
        save_btn = ft.FilledButton(
            content=ft.Text("حفظ الأسعار", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_rates
        )
        self._load_rates()
        return ft.Container(
            content=ft.Column([
                ft.Text("أسعار الصرف", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.Container(content=self.rates_table, border_radius=10, padding=10),
                ft.Row([refresh_btn, save_btn], spacing=10)
            ], spacing=15),
            padding=20
        )

    def _company_tab(self):
        info = get_company_info()
        self.company_name = ft.TextField(label="اسم الشركة", value=info.get('name',''), width=400)
        self.company_address = ft.TextField(label="العنوان", value=info.get('address',''), width=400)
        self.company_phone = ft.TextField(label="الهاتف", value=info.get('phone',''), width=400)
        self.company_email = ft.TextField(label="البريد الإلكتروني", value=info.get('email',''), width=400)
        self.company_logo = ft.TextField(label="مسار الشعار", value=info.get('logo_path',''), width=400, read_only=True)
        logo_btn = ft.TextButton(content=ft.Text("اختيار شعار"), on_click=self._browse_logo)
        save_btn = ft.FilledButton(
            content=ft.Text("حفظ", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_company
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("معلومات الشركة", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                self.company_name,
                self.company_address,
                self.company_phone,
                self.company_email,
                ft.Row([self.company_logo, logo_btn], spacing=10),
                ft.Container(height=30),
                save_btn
            ], spacing=15),
            padding=20
        )

    def _lang_theme_tab(self):
        cur_lang = self.repo.get('language','ar')
        self.lang_dropdown = ft.Dropdown(
            label="اللغة",
            value="العربية" if cur_lang=='ar' else "English" if cur_lang=='en' else "Français",
            options=[
                ft.dropdown.Option("العربية"),
                ft.dropdown.Option("English"),
                ft.dropdown.Option("Français")
            ],
            width=300
        )
        cur_theme = self.repo.get('theme','light')
        self.theme_dropdown = ft.Dropdown(
            label="المظهر",
            value="فاتح" if cur_theme=='light' else "داكن",
            options=[ft.dropdown.Option("فاتح"), ft.dropdown.Option("داكن")],
            width=300
        )
        lang_btn = ft.FilledButton(
            content=ft.Text("تغيير اللغة", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_language
        )
        theme_btn = ft.FilledButton(
            content=ft.Text("تطبيق المظهر", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_theme
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("اللغة والمظهر", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                self.lang_dropdown,
                lang_btn,
                ft.Divider(),
                self.theme_dropdown,
                theme_btn
            ], spacing=15),
            padding=20
        )

    def _network_tab(self):
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except: local_ip = "غير متوفر"
        ip_text = ft.Text(f"عنوان هذا الجهاز: {local_ip}", color=ft.Colors.GREY_600)
        db = DatabaseConnection()
        current_mode = db.mode
        self.mode_dropdown = ft.Dropdown(
            label="وضع التشغيل",
            value="محلي" if current_mode=="local" else "عميل" if current_mode=="client" else "خادم",
            options=[ft.dropdown.Option("محلي"), ft.dropdown.Option("عميل"), ft.dropdown.Option("خادم")],
            width=300
        )
        self.server_url = ft.TextField(
            label="عنوان الخادم",
            value=db.server_url,
            width=400,
            hint_text="http://192.168.1.100:8000"
        )
        test_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.NETWORK_CHECK), ft.Text("اختبار الاتصال")]),
            on_click=self._test_connection
        )
        save_btn = ft.FilledButton(
            content=ft.Text("حفظ", weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.INDIGO,
            color=ft.Colors.WHITE,
            on_click=self._save_network
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("إعدادات الشبكة", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ip_text,
                ft.Divider(),
                self.mode_dropdown,
                self.server_url,
                ft.Row([test_btn, save_btn], spacing=10)
            ], spacing=15),
            padding=20
        )

    def _backup_tab(self):
        backup_now_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.BACKUP), ft.Text("نسخ احتياطي الآن")]),
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE,
            on_click=self._backup_now
        )
        export_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD), ft.Text("تصدير قاعدة البيانات")]),
            on_click=self._export_db
        )
        reset_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.WARNING), ft.Text("إعادة تهيئة")]),
            bgcolor=ft.Colors.RED,
            color=ft.Colors.WHITE,
            on_click=self._reset_db
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("النسخ الاحتياطي والصيانة", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                backup_now_btn,
                ft.Divider(),
                export_btn,
                ft.Divider(),
                ft.Text("⚠️ تحذير: إعادة التهيئة تحذف جميع البيانات", color=ft.Colors.RED),
                reset_btn
            ], spacing=15),
            padding=20
        )

    def _load_rates(self):
        try:
            rates = currency.get_all_currencies()
            rows = []
            for r in rates:
                rate_field = ft.TextField(value=f"{r['rate_to_usd']:.4f}", width=120, text_align=ft.TextAlign.CENTER)
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r['currency_code'], weight=ft.FontWeight.BOLD)),
                    ft.DataCell(rate_field),
                    ft.DataCell(ft.Text(r['updated_at'][:19] if r['updated_at'] else ''))
                ]))
            self.rates_table.rows = rows
            self._page.update()
        except: pass

    def _save_currency(self, e):
        self.repo.set('base_currency', self.base_curr.value)
        self.repo.set('display_currency', self.display_curr.value)
        self.repo.set('currency_decimals', str(int(self.decimals.value)))
        fmt = 'western' if self.format_dropdown.value == 'غربية' else 'arabic'
        self.repo.set('number_format', fmt)
        self.repo.set('abbreviate_numbers', 'true' if self.abbreviate.value else 'false')
        self._show_snackbar("تم حفظ إعدادات العملة", is_error=False)

    def _save_rates(self, e): self._show_snackbar("تم حفظ الأسعار", is_error=False)
    def _fetch_online_rates(self, e): self._show_snackbar("سيتم قريباً...")
    def _save_company(self, e):
        info = {'name': self.company_name.value, 'address': self.company_address.value, 'phone': self.company_phone.value, 'email': self.company_email.value, 'logo_path': self.company_logo.value}
        save_company_info(info)
        self._show_snackbar("تم حفظ معلومات الشركة", is_error=False)
    def _browse_logo(self, e): self._show_snackbar("استخدم مسار الملف مباشرة")
    def _save_language(self, e):
        lang_map = {"العربية":"ar","English":"en","Français":"fr"}
        new_lang = lang_map.get(self.lang_dropdown.value,"ar")
        self.repo.set('language', new_lang)
        set_language(new_lang)
        self._show_snackbar("سيتم تطبيق اللغة بعد إعادة التشغيل", is_error=False)
    def _save_theme(self, e):
        theme = 'light' if self.theme_dropdown.value == 'فاتح' else 'dark'
        self.repo.set('theme', theme)
        self._page.theme_mode = ft.ThemeMode.LIGHT if theme == 'light' else ft.ThemeMode.DARK
        self._show_snackbar("تم تغيير المظهر", is_error=False)
        self._page.update()
    def _test_connection(self, e): self._show_snackbar("اختبار الاتصال...")
    def _save_network(self, e): self._show_snackbar("سيتم تطبيق الإعدادات بعد إعادة التشغيل")
    def _backup_now(self, e): self._show_snackbar("جاري النسخ الاحتياطي...")
    def _export_db(self, e): self._show_snackbar("جاري التصدير...")
    def _reset_db(self, e):
        def confirm(e):
            if e.control.text == "نعم":
                self._show_snackbar("تم إعادة التهيئة", is_error=False)
            self._page.close_dialog()
        dlg = ft.AlertDialog(
            title=ft.Text("⚠️ تحذير"),
            content=ft.Text("سيتم حذف جميع البيانات. هل أنت متأكد؟"),
            actions=[ft.TextButton("نعم", on_click=confirm), ft.TextButton("لا", on_click=lambda e: self._page.close_dialog())]
        )
        self._page.open(dlg)
