# -*- coding: utf-8 -*-
import flet as ft
from database import ExpenseRepository, UserRepository
from currency import currency
from i18n.translator import translate
from datetime import datetime, timedelta
from collections import defaultdict

class DashboardView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 20
        self.period_filter = ft.Dropdown(label="الفترة", value="الكل",
                                         options=[ft.dropdown.Option("الكل"), ft.dropdown.Option("الشهر الحالي"),
                                                  ft.dropdown.Option("الشهر الماضي"), ft.dropdown.Option("السنة الحالية")],
                                         width=200)
        self.period_filter.on_change = self._refresh
        self.cards_row1 = ft.Row(spacing=15, expand=True)
        self.cards_row2 = ft.Row(spacing=15, expand=True)
        self.cards_row3 = ft.Row(spacing=15, expand=True)

        border_side = ft.BorderSide(1, ft.Colors.GREY_300)
        table_border = ft.Border(top=border_side, bottom=border_side, left=border_side, right=border_side)
        self.recent_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(translate('date'))), ft.DataColumn(ft.Text(translate('company_name'))),
                     ft.DataColumn(ft.Text(translate('amount'))), ft.DataColumn(ft.Text("النوع"))],
            rows=[], border=table_border, border_radius=10,
            heading_row_color=ft.Colors.INDIGO_50, data_row_min_height=40
        )
        self.controls = [ft.Row([ft.Text(translate('dashboard'), size=24, weight=ft.FontWeight.BOLD), self.period_filter],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                         self.cards_row1, self.cards_row2, self.cards_row3,
                         ft.Text("آخر 5 قيود:", size=16, weight=ft.FontWeight.BOLD),
                         ft.Container(content=self.recent_table, expand=True, border_radius=10, padding=10)]
        self._refresh(None)

    def _create_card(self, title, value, color=ft.Colors.INDIGO):
        return ft.Card(content=ft.Container(content=ft.Column([ft.Text(title, size=14, color=ft.Colors.GREY_600),
                                                               ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color)], spacing=5),
                                            padding=20, alignment=ft.Alignment.CENTER), expand=True, elevation=2)

    def _get_date_filter(self):
        today = datetime.now()
        period = self.period_filter.value
        if period == "الشهر الحالي":
            start = datetime(today.year, today.month, 1)
            end = datetime(today.year, today.month, 1) + timedelta(days=32)
            end = datetime(end.year, end.month, 1) - timedelta(days=1)
        elif period == "الشهر الماضي":
            if today.month == 1:
                start = datetime(today.year - 1, 12, 1)
                end = datetime(today.year, 1, 1) - timedelta(days=1)
            else:
                start = datetime(today.year, today.month - 1, 1)
                end = datetime(today.year, today.month, 1) - timedelta(days=1)
        elif period == "السنة الحالية":
            start = datetime(today.year, 1, 1)
            end = datetime(today.year, 12, 31)
        else:
            return None, None
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN)
        self._page.snack_bar = snack
        snack.open = True
        self._page.update()

    def _refresh(self, e):
        try:
            expense_repo = ExpenseRepository()
            user_repo = UserRepository()
            all_expenses = expense_repo.get_all(convert_to_display=False)
            start_date, end_date = self._get_date_filter()
            filtered = []
            for ex in all_expenses:
                if start_date and ex['date'] < start_date: continue
                if end_date and ex['date'] > end_date: continue
                filtered.append(ex)
            total_in_usd = sum(e['amount'] for e in filtered if e['type'] == 'incoming')
            total_out_usd = sum(e['amount'] for e in filtered if e['type'] == 'outgoing')
            net_usd = total_in_usd - total_out_usd
            display_curr = currency.get_display_currency()
            total_in = currency.convert(total_in_usd, 'USD', display_curr)
            total_out = currency.convert(total_out_usd, 'USD', display_curr)
            net = currency.convert(net_usd, 'USD', display_curr)
            companies = set(e['company_name'] for e in filtered)
            users = user_repo.get_all()
            avg = sum(e['amount'] for e in filtered) / len(filtered) if filtered else 0
            avg_display = currency.convert(avg, 'USD', display_curr)
            company_net = defaultdict(float)
            for e in filtered:
                val = e['amount'] if e['type'] == 'incoming' else -e['amount']
                company_net[e['company_name']] += val
            top_company = max(company_net.items(), key=lambda x: x[1]) if company_net else ("—", 0)
            top_display = currency.convert(top_company[1], 'USD', display_curr)
            rate = currency.get_rate_to_usd(display_curr)
            rate_text = f"1 {display_curr} = {rate:.4f} USD" if display_curr != 'USD' else "1 USD = 1.00 USD"
            self.cards_row1.controls = [
                self._create_card(translate('total_incoming'), currency.format_amount(total_in, display_curr), ft.Colors.GREEN),
                self._create_card(translate('total_outgoing'), currency.format_amount(total_out, display_curr), ft.Colors.RED),
                self._create_card(translate('net_profit'), currency.format_amount(net, display_curr), ft.Colors.GREEN if net >= 0 else ft.Colors.RED)
            ]
            self.cards_row2.controls = [
                self._create_card("عدد الشركات", str(len(companies)), ft.Colors.BLUE),
                self._create_card("عدد المستخدمين", str(len(users)), ft.Colors.ORANGE),
                self._create_card("متوسط القيد", currency.format_amount(avg_display, display_curr), ft.Colors.PURPLE)
            ]
            self.cards_row3.controls = [
                self._create_card("أعلى شركة", f"{top_company[0]}\n({currency.format_amount(top_display, display_curr)})", ft.Colors.TEAL),
                self._create_card("سعر الصرف", rate_text, ft.Colors.INDIGO)
            ]
            recent = sorted(all_expenses, key=lambda x: x['id'], reverse=True)[:5]
            rows = []
            for r in recent:
                amount_str = f"{r['amount_original']:,.2f} {r['currency_original']}"
                type_text = "لنا" if r['type'] == 'incoming' else "له"
                type_color = ft.Colors.GREEN if r['type'] == 'incoming' else ft.Colors.RED
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r['date'])), ft.DataCell(ft.Text(r['company_name'])),
                    ft.DataCell(ft.Text(amount_str)), ft.DataCell(ft.Text(type_text, color=type_color))
                ]))
            self.recent_table.rows = rows
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحديث لوحة التحكم: {str(ex)}", True)
