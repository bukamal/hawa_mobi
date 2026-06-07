# -*- coding: utf-8 -*-
import flet as ft
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency

class CompanyDetailsMobileView(ft.Column):
    def __init__(self, page, company_name, records=None):
        super().__init__()
        self._page = page
        self.company_name = company_name
        if records is None:
            repo = ExpenseRepository()
            self.records = repo.get_by_company(company_name, convert_to_display=False)
        else:
            self.records = records
        self.records = sorted(self.records, key=lambda x: x['date'])
        self.spacing = 10
        self.expand = True
        self.scroll = ft.ScrollMode.AUTO

        self.summary_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.records_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        self.controls = [self.summary_text, ft.Divider(height=1), self.records_list]
        self._load_data()

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message, size=13), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN, duration=3000)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _load_data(self):
        display_curr = currency.get_display_currency()
        total_in_usd = sum(r['amount'] for r in self.records if r['type'] == 'incoming')
        total_out_usd = sum(r['amount'] for r in self.records if r['type'] == 'outgoing')
        net_usd = total_in_usd - total_out_usd
        total_in = currency.convert(total_in_usd, 'USD', display_curr)
        total_out = currency.convert(total_out_usd, 'USD', display_curr)
        net = currency.convert(net_usd, 'USD', display_curr)

        self.summary_text.value = f"📥 {currency.format_amount(total_in, display_curr)}   📤 {currency.format_amount(total_out, display_curr)}   💰 {currency.format_amount(net, display_curr)}"

        cards = []
        running_usd = 0.0
        is_viewer = UserSession.get_current() and UserSession.get_current().get('role') == 'viewer'

        for idx, r in enumerate(self.records, 1):
            amount_str = f"{r['amount_original']:,.2f} {r['currency_original']}"
            if r['type'] == 'incoming':
                inc_out = amount_str
                out_txt = "—"
                running_usd += r['amount']
                amount_color = ft.Colors.GREEN
                icon = ft.Icons.ARROW_DOWNWARD
                amount_label = "لنا"
            else:
                inc_out = "—"
                out_txt = amount_str
                running_usd -= r['amount']
                amount_color = ft.Colors.RED
                icon = ft.Icons.ARROW_UPWARD
                amount_label = "له"

            running_display = currency.convert(running_usd, 'USD', display_curr)
            running_str = currency.format_amount(running_display, display_curr)
            running_color = ft.Colors.GREEN if running_usd >= 0 else ft.Colors.RED

            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"#{idx}", size=12, color=ft.Colors.GREY_500),
                            ft.Text(r['date'], size=12, color=ft.Colors.GREY_600),
                            ft.Icon(icon, color=amount_color, size=16)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Column([
                                ft.Text(amount_label, size=11, color=ft.Colors.GREY_500),
                                ft.Text(amount_str, size=14, color=amount_color, weight=ft.FontWeight.BOLD)
                            ], expand=True),
                            ft.Column([
                                ft.Text("تراكمي", size=11, color=ft.Colors.GREY_500),
                                ft.Text(running_str, size=14, color=running_color, weight=ft.FontWeight.BOLD)
                            ], horizontal_alignment=ft.CrossAxisAlignment.END)
                        ]),
                        ft.Text(r['notes'] or '', size=12, color=ft.Colors.GREY_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row([
                            ft.TextButton(
                                content=ft.Row([ft.Icon(ft.Icons.EDIT, size=16, color=ft.Colors.INDIGO), ft.Text("تعديل", size=11, color=ft.Colors.INDIGO)]),
                                on_click=lambda e, rec=r: self._edit_record(rec),
                                visible=not is_viewer
                            ),
                            ft.TextButton(
                                content=ft.Row([ft.Icon(ft.Icons.DELETE, size=16, color=ft.Colors.RED), ft.Text("حذف", size=11, color=ft.Colors.RED)]),
                                on_click=lambda e, rec=r: self._delete_record(rec),
                                visible=not is_viewer
                            )
                        ], alignment=ft.MainAxisAlignment.END)
                    ], spacing=8),
                    padding=12
                ),
                elevation=1,
                margin=ft.Margin(left=5, right=5, top=5, bottom=5)
            )
            cards.append(card)

        if not cards:
            cards.append(ft.Container(content=ft.Text("لا توجد قيود", color=ft.Colors.GREY_400), alignment=ft.Alignment.CENTER, padding=30))

        self.records_list.controls = cards
        self._page.update()

    def _edit_record(self, record):
        from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
        dialog = AddEditExpenseDialog(page=self._page, on_save=lambda _: self._reload(), expense=record)
        self._page.show_dialog(dialog)

    def _delete_record(self, record):
        def confirm(e):
            if e.control.data == "yes":
                try:
                    # محاولة الحذف عبر المستودع
                    repo = ExpenseRepository()
                    repo.delete(record['id'], UserSession.get_current().get('id') if UserSession.get_current() else None)
                    # إعادة تحميل البيانات
                    self._reload()
                    self._show_snackbar("تم الحذف بنجاح", is_error=False)
                except Exception as ex:
                    self._show_snackbar(f"فشل الحذف: {str(ex)}", True)
            self._close_dialog(dlg)

        # إنشاء الأزرار مع خاصية data
        btn_yes = ft.TextButton("نعم", on_click=confirm, data="yes")
        btn_no = ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg), data="no")

        dlg = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text(f"حذف قيد بمبلغ {record['amount_original']} {record['currency_original']}؟"),
            actions=[btn_yes, btn_no]
        )
        self._page.show_dialog(dlg)

    def _reload(self):
        """إعادة تحميل البيانات من قاعدة البيانات، مع إغلاق الاتصال القديم لضمان التحديث"""
        try:
            from database.connection import DatabaseConnection
            db = DatabaseConnection()
            if db._local_conn:
                db._local_conn.close()
                db._local_conn = None
            repo = ExpenseRepository()
            self.records = repo.get_by_company(self.company_name, convert_to_display=False)
            self.records = sorted(self.records, key=lambda x: x['date'])
            self._load_data()
        except Exception as ex:
            self._show_snackbar(f"خطأ في إعادة التحميل: {str(ex)}", True)

    def _close_dialog(self, dialog):
        dialog.open = False
        self._page.update()
