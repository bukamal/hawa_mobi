# -*- coding: utf-8 -*-
import flet as ft
from database import ExpenseRepository, UserRepository
from currency import currency
from i18n.translator import translate
from datetime import datetime, timedelta
from collections import defaultdict
from views.flet_compat import open_control
from views.ui_kit import show_snackbar, page_header, stat_card


class DashboardMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 15
        self.scroll = ft.ScrollMode.AUTO

        self.period_filter = ft.Dropdown(
            label="الفترة",
            value="الكل",
            options=[
                ft.dropdown.Option("الكل"),
                ft.dropdown.Option("الشهر الحالي"),
                ft.dropdown.Option("الشهر الماضي"),
                ft.dropdown.Option("السنة الحالية"),
                ft.dropdown.Option("مخصص"),
            ],
            width=180,
        )
        self.period_filter.on_change = self._on_period_change

        self.start_date_picker = ft.TextField(
            label="من تاريخ",
            hint_text="YYYY-MM-DD",
            width=130,
            read_only=True,
            suffix=ft.IconButton(
                ft.Icons.CALENDAR_MONTH, on_click=self._open_start_date_picker
            ),
        )
        self.end_date_picker = ft.TextField(
            label="إلى تاريخ",
            hint_text="YYYY-MM-DD",
            width=130,
            read_only=True,
            suffix=ft.IconButton(
                ft.Icons.CALENDAR_MONTH, on_click=self._open_end_date_picker
            ),
        )
        self.custom_date_row = ft.Row(
            [self.start_date_picker, self.end_date_picker], spacing=10, visible=False
        )

        self.refresh_btn = ft.IconButton(
            ft.Icons.REFRESH, on_click=self._refresh, tooltip="تحديث"
        )
        self.transactions_count_text = ft.Text("", size=12, color=ft.Colors.GREY_600)

        self.start_date_picker_obj = ft.DatePicker(on_change=self._on_start_date_change)
        self.end_date_picker_obj = ft.DatePicker(on_change=self._on_end_date_change)
        self._page.overlay.append(self.start_date_picker_obj)
        self._page.overlay.append(self.end_date_picker_obj)

        self.cards_container = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

        self.controls = [
            page_header(
                translate("dashboard"),
                icon=ft.Icons.DASHBOARD,
                trailing=self.refresh_btn,
            ),
            ft.Container(
                content=self.period_filter,
                padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            ),
            ft.Container(
                content=self.custom_date_row,
                padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            ),
            ft.Row(
                [self.transactions_count_text], alignment=ft.MainAxisAlignment.CENTER
            ),
            ft.Divider(),
            self.cards_container,
        ]

        self._load_data()

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _open_start_date_picker(self, e):
        open_control(self._page, self.start_date_picker_obj)

    def _open_end_date_picker(self, e):
        open_control(self._page, self.end_date_picker_obj)

    def _on_start_date_change(self, e):
        if self.start_date_picker_obj.value:
            self.start_date_picker.value = self.start_date_picker_obj.value.strftime(
                "%Y-%m-%d"
            )
            self._refresh(None)

    def _on_end_date_change(self, e):
        if self.end_date_picker_obj.value:
            self.end_date_picker.value = self.end_date_picker_obj.value.strftime(
                "%Y-%m-%d"
            )
            self._refresh(None)

    def _on_period_change(self, e):
        if self.period_filter.value == "مخصص":
            self.custom_date_row.visible = True
            if not self.start_date_picker.value:
                self.start_date_picker.value = (
                    datetime.now() - timedelta(days=30)
                ).strftime("%Y-%m-%d")
            if not self.end_date_picker.value:
                self.end_date_picker.value = datetime.now().strftime("%Y-%m-%d")
        else:
            self.custom_date_row.visible = False
        self._refresh(None)

    def _get_date_filter(self):
        period = self.period_filter.value
        if period == "الشهر الحالي":
            today = datetime.now()
            start = datetime(today.year, today.month, 1)
            end = datetime(today.year, today.month, 1) + timedelta(days=32)
            end = datetime(end.year, end.month, 1) - timedelta(days=1)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        elif period == "الشهر الماضي":
            today = datetime.now()
            if today.month == 1:
                start = datetime(today.year - 1, 12, 1)
                end = datetime(today.year, 1, 1) - timedelta(days=1)
            else:
                start = datetime(today.year, today.month - 1, 1)
                end = datetime(today.year, today.month, 1) - timedelta(days=1)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        elif period == "السنة الحالية":
            today = datetime.now()
            start = datetime(today.year, 1, 1)
            end = datetime(today.year, 12, 31)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        elif period == "مخصص":
            return self.start_date_picker.value, self.end_date_picker.value
        else:
            return None, None

    def _create_card(self, title, value, color=ft.Colors.INDIGO, icon=None):
        resolved_icon = icon or (
            ft.Icons.TRENDING_UP if color == ft.Colors.GREEN else ft.Icons.TRENDING_DOWN
        )
        return stat_card(title, value, color=color, icon=resolved_icon)

    def _refresh(self, e):
        self._load_data()

    def _load_data(self):
        try:
            expense_repo = ExpenseRepository()
            user_repo = UserRepository()
            all_expenses = expense_repo.get_all(convert_to_display=False)

            start_date, end_date = self._get_date_filter()
            filtered = []
            for ex in all_expenses:
                if start_date and ex["date"] < start_date:
                    continue
                if end_date and ex["date"] > end_date:
                    continue
                filtered.append(ex)

            approved_filtered = [
                e for e in filtered if e.get("status", "approved") != "waiting_payment"
            ]
            waiting_payment = [
                e for e in filtered if e.get("status") == "waiting_payment"
            ]

            display_curr = currency.get_display_currency()

            def original_amount(e):
                return float(e.get("amount_original", e.get("amount", 0)) or 0)

            def original_currency(e):
                return (
                    e.get("currency_original") or e.get("currency") or "USD"
                ).upper()

            totals_by_currency = defaultdict(
                lambda: {"incoming": 0.0, "outgoing": 0.0, "net": 0.0, "count": 0}
            )
            historical_base = {"incoming": 0.0, "outgoing": 0.0, "net": 0.0}
            for e in approved_filtered:
                curr = original_currency(e)
                amount_orig = original_amount(e)
                amount_base = float(
                    e.get("amount", 0) or 0
                )  # محفوظ تاريخياً بالدولار عند إدخال القيد
                if e.get("type") == "incoming":
                    totals_by_currency[curr]["incoming"] += amount_orig
                    totals_by_currency[curr]["net"] += amount_orig
                    historical_base["incoming"] += amount_base
                    historical_base["net"] += amount_base
                else:
                    totals_by_currency[curr]["outgoing"] += amount_orig
                    totals_by_currency[curr]["net"] -= amount_orig
                    historical_base["outgoing"] += amount_base
                    historical_base["net"] -= amount_base
                totals_by_currency[curr]["count"] += 1

            def format_currency_lines(kind: str, with_direction: bool = False) -> str:
                if not totals_by_currency:
                    return "—"
                lines = []
                for curr in sorted(totals_by_currency):
                    val = totals_by_currency[curr][kind]
                    if abs(val) < 1e-9 and kind != "net":
                        continue
                    text = currency.format_amount(
                        abs(val) if kind == "net" else val, curr
                    )
                    if with_direction:
                        side = "لنا" if val >= 0 else "له"
                        text = f"{text} {side}"
                    lines.append(text)
                return "\n".join(lines) if lines else "—"

            base_in = currency.convert(historical_base["incoming"], "USD", display_curr)
            base_out = currency.convert(
                historical_base["outgoing"], "USD", display_curr
            )
            base_net = currency.convert(historical_base["net"], "USD", display_curr)

            companies = set(e["company_name"] for e in filtered)
            try:
                users = user_repo.get_all()
                users_count = len(users)
            except Exception as user_ex:
                users_count = "—"
                print(f"[WARN] تعذر تحميل المستخدمين في لوحة التحكم: {user_ex}")

            avg_base = (
                (historical_base["incoming"] + historical_base["outgoing"])
                / len(approved_filtered)
                if approved_filtered
                else 0
            )
            avg_display = currency.convert(avg_base, "USD", display_curr)

            company_net_base = defaultdict(float)
            for e in approved_filtered:
                val = float(e.get("amount", 0) or 0)
                company_net_base[e["company_name"]] += (
                    val if e.get("type") == "incoming" else -val
                )
            top_company = (
                max(company_net_base.items(), key=lambda x: x[1])
                if company_net_base
                else ("—", 0)
            )
            top_display = currency.convert(top_company[1], "USD", display_curr)

            rate = currency.get_rate_to_usd(display_curr)
            rate_text = (
                f"1 {display_curr} = {rate:.4f} USD"
                if display_curr != "USD"
                else "1 USD = 1.00 USD"
            )

            cards = [
                self._create_card(
                    "لنا حسب العملة", format_currency_lines("incoming"), ft.Colors.GREEN
                ),
                self._create_card(
                    "له حسب العملة", format_currency_lines("outgoing"), ft.Colors.RED
                ),
                self._create_card(
                    "الصافي حسب العملة",
                    format_currency_lines("net", with_direction=True),
                    ft.Colors.GREEN if historical_base["net"] >= 0 else ft.Colors.RED,
                ),
                self._create_card(
                    f"إجمالي تقريبي بـ {display_curr}",
                    f"لنا: {currency.format_amount(base_in, display_curr)}\nله: {currency.format_amount(base_out, display_curr)}\nالصافي: {currency.format_amount(base_net, display_curr)}\nمحسوب حسب أسعار الصرف التاريخية",
                    ft.Colors.INDIGO,
                    ft.Icons.CURRENCY_EXCHANGE,
                ),
                self._create_card(
                    "عدد الشركات",
                    str(len(companies)),
                    ft.Colors.BLUE,
                    ft.Icons.BUSINESS,
                ),
                self._create_card(
                    "عدد المستخدمين",
                    str(users_count),
                    ft.Colors.ORANGE,
                    ft.Icons.PEOPLE,
                ),
                self._create_card(
                    "متوسط القيد التقريبي",
                    currency.format_amount(avg_display, display_curr),
                    ft.Colors.PURPLE,
                    ft.Icons.CALCULATE,
                ),
                self._create_card(
                    "أعلى شركة تقريبياً",
                    f"{top_company[0]}\n({currency.format_amount(top_display, display_curr)})",
                    ft.Colors.TEAL,
                    ft.Icons.EMOJI_EVENTS,
                ),
                self._create_card(
                    "سعر الصرف الحالي", rate_text, ft.Colors.INDIGO, ft.Icons.MONEY
                ),
                self._create_card(
                    "بانتظار الدفع",
                    str(len(waiting_payment)),
                    ft.Colors.ORANGE,
                    ft.Icons.PAYMENTS,
                ),
            ]
            self.cards_container.controls = cards

            self.transactions_count_text.value = f"📊 عدد القيود في هذه الفترة: {len(filtered)} | ⏳ بانتظار الدفع: {len(waiting_payment)}"
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحديث لوحة التحكم: {str(ex)}", True)
