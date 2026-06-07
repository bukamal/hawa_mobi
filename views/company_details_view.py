# -*- coding: utf-8 -*-
import flet as ft
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency

class CompanyDetailsView(ft.Column):
    def __init__(self, page, company_name):
        super().__init__()
        self._page = page
        self.company_name = company_name
        self.spacing = 15
        self.expand = True
        self.summary_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD)

        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.details_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#")),
                ft.DataColumn(ft.Text(translate('date'))),
                ft.DataColumn(ft.Text(translate('notes'))),
                ft.DataColumn(ft.Text("لنا")),
                ft.DataColumn(ft.Text("له")),
                ft.DataColumn(ft.Text(translate('cumulative')))
            ],
            rows=[],
            border=table_border,
            border_radius=10,
            heading_row_color=ft.Colors.INDIGO_50,
            data_row_min_height=45,
            expand=True
        )
        is_viewer = UserSession.get_current().get('role') == 'viewer' if UserSession.get_current() else False
        self.add_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD), ft.Text(translate('add'))]),
            bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE,
            on_click=self._add_record, visible=not is_viewer
        )
        self.delete_btn = ft.FilledButton(
            content=ft.Row([ft.Icon(ft.Icons.DELETE), ft.Text(translate('delete'))]),
            bgcolor=ft.Colors.RED, color=ft.Colors.WHITE,
            on_click=self._delete_record, visible=not is_viewer
        )
        self.controls = [
            self.summary_text,
            ft.Row([self.add_btn, self.delete_btn], spacing=10),
            ft.Container(content=self.details_table, expand=True, border_radius=10, padding=10)
        ]
        self._load_data()

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _load_data(self):
        repo = ExpenseRepository()
        records = repo.get_by_company(self.company_name, convert_to_display=False)
        records = sorted(records, key=lambda x: x['date'])
        display_curr = currency.get_display_currency()
        total_in_usd = sum(r['amount'] for r in records if r['type'] == 'incoming')
        total_out_usd = sum(r['amount'] for r in records if r['type'] == 'outgoing')
        net_usd = total_in_usd - total_out_usd
        total_in = currency.convert(total_in_usd, 'USD', display_curr)
        total_out = currency.convert(total_out_usd, 'USD', display_curr)
        net = currency.convert(net_usd, 'USD', display_curr)
        self.summary_text.value = (
            f"📥 إجمالي وارد: {currency.format_amount(total_in, display_curr)}   |   "
            f"📤 إجمالي صادر: {currency.format_amount(total_out, display_curr)}   |   "
            f"💰 صافي: {currency.format_amount(net, display_curr)}"
        )
        rows = []
        running_usd = 0.0
        for idx, r in enumerate(records, 1):
            amount_str = f"{r['amount_original']:,.2f} {r['currency_original']}"
            if r['type'] == 'incoming':
                incoming = amount_str
                outgoing = "—"
                running_usd += r['amount']
            else:
                incoming = "—"
                outgoing = amount_str
                running_usd -= r['amount']
            running_display = currency.convert(running_usd, 'USD', display_curr)
            running_str = currency.format_amount(running_display, display_curr)
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(idx))),
                ft.DataCell(ft.Text(r['date'])),
                ft.DataCell(ft.Text(r['notes'] or '', size=12)),
                ft.DataCell(ft.Text(incoming, color=ft.Colors.GREEN)),
                ft.DataCell(ft.Text(outgoing, color=ft.Colors.RED)),
                ft.DataCell(ft.Text(running_str, weight=ft.FontWeight.BOLD))
            ]))
        self.details_table.rows = rows
        self._page.update()

    def _add_record(self, e):
        from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
        dialog = AddEditExpenseDialog(page=self._page, on_save=lambda _: self._load_data(), company_name=self.company_name)
        self._page.show_dialog(dialog)

    def _delete_record(self, e):
        self._show_snackbar("اختر قيداً من الجدول للحذف")
