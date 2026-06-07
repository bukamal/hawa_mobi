# -*- coding: utf-8 -*-
import flet as ft
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from collections import defaultdict

class AccountsView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15

        self.search_field = ft.TextField(label=translate('search'), prefix_icon=ft.Icons.SEARCH, width=300)
        self.search_field.on_change = self._refresh_table

        self.add_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD), ft.Text(translate('add'))], spacing=5),
            bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE,
            on_click=self._add_record,
            visible=UserSession.get_current().get('role') != 'viewer' if UserSession.get_current() else True
        )
        self.print_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.PRINT), ft.Text(translate('print_report'))], spacing=5),
            on_click=self._print_report
        )
        top_bar = ft.Row([self.search_field, self.add_btn, self.print_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(translate('company_name'))),
                ft.DataColumn(ft.Text(translate('total_incoming'))),
                ft.DataColumn(ft.Text(translate('total_outgoing'))),
                ft.DataColumn(ft.Text(translate('net')))
            ],
            rows=[],
            border=table_border,
            border_radius=10,
            vertical_lines=border_side,
            horizontal_lines=border_side,
            heading_row_color=ft.Colors.INDIGO_50,
            data_row_min_height=50,
            expand=True
        )

        self.controls = [
            ft.Text(translate('accounts'), size=24, weight=ft.FontWeight.BOLD),
            top_bar,
            ft.Container(content=self.data_table, expand=True, border_radius=10, padding=10, bgcolor=ft.Colors.WHITE)
        ]
        self._refresh_table(None)

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _refresh_table(self, e):
        try:
            repo = ExpenseRepository()
            expenses = repo.get_all(convert_to_display=False)
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل البيانات: {str(ex)}", True)
            return

        search = self.search_field.value.strip().lower() if self.search_field.value else ""
        groups = defaultdict(lambda: {'incoming':0.0, 'outgoing':0.0})
        for ex in expenses:
            if search and search not in ex['company_name'].lower(): continue
            groups[ex['company_name']][ex['type']] += ex['amount']

        display_curr = currency.get_display_currency()
        rows = []
        for company, vals in sorted(groups.items()):
            inc = currency.convert(vals['incoming'], 'USD', display_curr)
            out = currency.convert(vals['outgoing'], 'USD', display_curr)
            net = inc - out
            net_color = ft.Colors.GREEN if net >= 0 else ft.Colors.RED
            row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(company, weight=ft.FontWeight.BOLD)),
                ft.DataCell(ft.Text(currency.format_amount(inc, display_curr), color=ft.Colors.GREEN)),
                ft.DataCell(ft.Text(currency.format_amount(out, display_curr), color=ft.Colors.RED)),
                ft.DataCell(ft.Text(currency.format_amount(net, display_curr), color=net_color, weight=ft.FontWeight.BOLD))
            ])
            row.on_select_changed = lambda e, c=company: self._show_details(c)
            rows.append(row)
        self.data_table.rows = rows
        self._page.update()

    def _show_details(self, company_name):
        from views.company_details_view import CompanyDetailsView
        dialog = ft.AlertDialog(
            title=ft.Text(f"تفاصيل: {company_name}"),
            content=CompanyDetailsView(self._page, company_name),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: self._close_dialog(dialog))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dialog)

    def _close_dialog(self, dialog):
        dialog.open = False
        self._page.update()

    def _add_record(self, e):
        if UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)
            return
        from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
        dialog = AddEditExpenseDialog(page=self._page, on_save=self._refresh_table)
        self._page.show_dialog(dialog)

    def _print_report(self, e):
        self._show_snackbar("جاري إعداد التقرير...", is_error=False)
