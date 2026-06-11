# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from collections import defaultdict
from views.ui_kit import show_snackbar, page_header, search_field, summary_bar, metric_tile, empty_state, action_text_button, data_card

class AccountsMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO

        self.search_field = search_field(translate('search'), self._refresh_cards)

        self.net_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)
        self.companies_count_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)
        self.records_count_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE)

        self.summary_bar = summary_bar([
            metric_tile("صافي", self.net_text),
            metric_tile("الشركات", self.companies_count_text),
            metric_tile("القيود", self.records_count_text),
        ], visible=False)

        self.cards_container = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=ft.Colors.GREEN,
            foreground_color=ft.Colors.WHITE,
            on_click=self._add_record,
            tooltip=translate('add'),
            mini=False,
            elevation=6,
            shape=ft.CircleBorder(),
            margin=ft.Margin(left=0, right=16, top=0, bottom=80)
        )

        self.controls = [
            page_header(translate('accounts'), icon=ft.Icons.ACCOUNT_BALANCE, subtitle="الشركات والقيود المالية"),
            ft.Container(content=self.search_field, padding=ft.Padding(left=10, right=10, top=0, bottom=0)),
            self.summary_bar,
            self.cards_container
        ]

        self._page.floating_action_button = self.fab
        self._refresh_cards(None)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _refresh_cards(self, e):
        try:
            repo = ExpenseRepository()
            expenses = repo.get_all(convert_to_display=False)
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل البيانات: {str(ex)}", True)
            return

        search = self.search_field.value.strip().lower() if self.search_field.value else ""
        groups = defaultdict(lambda: {'incoming':0.0, 'outgoing':0.0, 'records':[], 'waiting_payment':0})
        for ex in expenses:
            if search and search not in ex['company_name'].lower(): continue
            if ex.get('status') == 'waiting_payment':
                groups[ex['company_name']]['waiting_payment'] += 1
            else:
                groups[ex['company_name']][ex['type']] += float(ex.get('amount') or 0)
            groups[ex['company_name']]['records'].append(ex)

        display_curr = currency.get_display_currency()
        cards = []
        total_net = 0.0
        total_records = 0

        for company, vals in sorted(groups.items()):
            inc = currency.convert(vals['incoming'], 'USD', display_curr)
            out = currency.convert(vals['outgoing'], 'USD', display_curr)
            net = inc - out
            total_net += net
            total_records += len(vals['records'])

            net_color = ft.Colors.GREEN if net >= 0 else ft.Colors.RED
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.BUSINESS, color=ft.Colors.INDIGO, size=24),
                            ft.Text(company, size=16, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Container(
                                content=ft.Text(currency.format_amount(net, display_curr),
                                               size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=net_color,
                                border_radius=20,
                                padding=ft.Padding(left=12, right=12, top=6, bottom=6)
                            )
                        ]),
                        ft.Divider(height=1, color=ft.Colors.GREY_200),
                        ft.Row([
                            ft.Column([
                                ft.Text("📥 لنا", size=11, color=ft.Colors.GREY_600),
                                ft.Text(currency.format_amount(inc, display_curr),
                                       size=14, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                            ft.VerticalDivider(width=1, color=ft.Colors.GREY_200),
                            ft.Column([
                                ft.Text("📤 له", size=11, color=ft.Colors.GREY_600),
                                ft.Text(currency.format_amount(out, display_curr),
                                       size=14, color=ft.Colors.RED, weight=ft.FontWeight.BOLD)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                            ft.VerticalDivider(width=1, color=ft.Colors.GREY_200),
                            ft.Column([
                                ft.Text("📋 عدد", size=11, color=ft.Colors.GREY_600),
                                ft.Text(str(len(vals['records'])), size=14, weight=ft.FontWeight.BOLD)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                        ft.Container(
                            content=ft.Text(f"⏳ بانتظار الدفع: {vals['waiting_payment']}", size=12, color=ft.Colors.ORANGE_900),
                            bgcolor=ft.Colors.ORANGE_50,
                            border_radius=12,
                            padding=ft.Padding(left=10, right=10, top=6, bottom=6),
                            visible=vals['waiting_payment'] > 0,
                        ),
                        ft.Row([
                            ft.TextButton(
                                content=ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=18), ft.Text("تفاصيل", size=12)]),
                                on_click=lambda e, c=company, r=vals['records']: self._show_details(c, r)
                            ),
                            ft.TextButton(
                                content=ft.Row([ft.Icon(ft.Icons.ADD, size=18, color=ft.Colors.GREEN), ft.Text("قيد", size=12, color=ft.Colors.GREEN)]),
                                on_click=lambda e, c=company: self._add_record(c)
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
                    ], spacing=10),
                    padding=15
                ),
                elevation=2,
                margin=ft.Margin(left=10, right=10, top=5, bottom=5)
            )
            cards.append(card)

        if cards:
            self.net_text.value = currency.format_amount(total_net, display_curr)
            self.net_text.color = ft.Colors.GREEN if total_net >= 0 else ft.Colors.RED
            self.companies_count_text.value = str(len(cards))
            self.records_count_text.value = str(total_records)
            self.summary_bar.visible = True
        else:
            self.summary_bar.visible = False
            cards.append(empty_state("لا توجد بيانات", "اضغط + لإضافة قيد جديد", icon=ft.Icons.SEARCH_OFF))

        self.cards_container.controls = cards
        self._page.update()

    def _show_details(self, company_name, records):
        from views.company_details_mobile_view import CompanyDetailsMobileView
        dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.BUSINESS, color=ft.Colors.INDIGO), ft.Text(company_name, size=18, weight=ft.FontWeight.BOLD, expand=True)]),
            content=ft.Container(content=CompanyDetailsMobileView(self._page, company_name, records, on_changed=lambda: self._refresh_cards(None)), height=500, width=400),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: self._close_dialog(dialog))],
            inset_padding=20,
            scrollable=True
        )
        open_control(self._page, dialog)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)

    def _add_record(self, company_name=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)
            return
        from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
        try:
            dialog = AddEditExpenseDialog(page=self._page, on_save=lambda _: self._refresh_cards(None), company_name=company_name)
            open_control(self._page, dialog)
        except Exception as e:
            self._show_snackbar(f"خطأ في إنشاء الحوار: {str(e)}", True)
            import traceback
            traceback.print_exc()
