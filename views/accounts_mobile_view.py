# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, make_floating_action_button
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from collections import defaultdict
from views.ui_kit import show_snackbar, page_header, search_field, summary_bar, metric_tile, empty_state, action_text_button, data_card, amount_pill, key_value_tile, pill, info_banner, PRIMARY, PRIMARY_SOFT, SUCCESS, DANGER, WARNING, TEXT, MUTED, money_text, modern_action_button
from services.company_search_service import normalize_search_text


class AccountsMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO
        self._last_search_results = []

        self.search_field = search_field(translate('company_deep_search_hint'), self._refresh_cards)
        self.search_status = ft.Container(visible=False)

        self.net_text = money_text("0", size=24, color=PRIMARY)
        self.companies_count_text = money_text("0", size=23, color=PRIMARY)
        self.records_count_text = money_text("0", size=23, color=WARNING)

        self.summary_bar = summary_bar([
            metric_tile("صافي", self.net_text),
            metric_tile("الشركات", self.companies_count_text),
            metric_tile("القيود", self.records_count_text),
        ], visible=False)

        self.cards_container = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.fab = make_floating_action_button(
            icon=ft.Icons.ADD,
            bgcolor=SUCCESS,
            foreground_color=ft.Colors.WHITE,
            on_click=self._open_add_menu,
            tooltip=translate('add'),
            mini=False,
            elevation=6,
            shape=ft.CircleBorder()
        )

        self.controls = [
            page_header(translate('accounts'), icon=ft.Icons.ACCOUNT_BALANCE, subtitle=translate('accounts_search_subtitle')),
            ft.Container(content=ft.Row([
                ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.INSIGHTS, color=PRIMARY), ft.Text('تقرير أرباح الخدمات', color=PRIMARY, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._export_service_profit_report),
            ], alignment=ft.MainAxisAlignment.END), padding=ft.Padding(left=10, right=10, top=0, bottom=0)),
            ft.Container(content=self.search_field, padding=ft.Padding(left=10, right=10, top=0, bottom=0)),
            self.search_status,
            self.summary_bar,
            self.cards_container
        ]

        self._page.floating_action_button = self.fab
        self._refresh_cards(None)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _current_search(self) -> str:
        return (self.search_field.value or "").strip()

    def _search_banner(self, query: str, result_count: int):
        if not query:
            self.search_status.visible = False
            self.search_status.content = None
            return
        self.search_status.visible = True
        self.search_status.content = info_banner(
            f"🔎 {translate('deep_search_results')}: {result_count} — {translate('deep_search_scope')}",
            icon=ft.Icons.MANAGE_SEARCH,
            color=PRIMARY,
            bgcolor=PRIMARY_SOFT,
        )

    def _entry_amount_text(self, row):
        display_curr = currency.get_display_currency()
        original = currency.format_amount(float(row.get('amount_original') or row.get('amount') or 0), row.get('currency_original') or row.get('currency') or display_curr)
        try:
            amount_base = float(row.get('amount_base', row.get('amount', 0)) or 0)
            display_amount = currency.convert(amount_base, 'USD', display_curr)
            display = currency.format_amount(display_amount, display_curr)
        except Exception:
            display = original
        if (row.get('currency_original') or display_curr) == display_curr:
            return original
        return f"{original} · {display}"

    def _match_preview_controls(self, company, matches, query):
        if not query or not matches:
            return []
        controls = [
            ft.Divider(height=1, color=ft.Colors.GREY_200),
            ft.Row([
                ft.Icon(ft.Icons.SEARCH, color=PRIMARY, size=16),
                ft.Text(f"{translate('matches_inside_company')}: {len(matches)}", size=12, weight=ft.FontWeight.BOLD, color=PRIMARY, expand=True),
            ], spacing=6),
        ]
        for m in matches[:3]:
            direction = "لنا" if m.get('type') == 'incoming' else "له"
            label = m.get('matched_label') or translate('match')
            snippet = m.get('snippet') or (m.get('notes') or m.get('company_name') or '')
            controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            pill(label, color=PRIMARY, bgcolor=PRIMARY_SOFT, size=10),
                            ft.Text(str(m.get('date') or ''), size=11, color=ft.Colors.GREY_600, expand=True),
                            ft.Text(direction, size=11, color=SUCCESS if m.get('type') == 'incoming' else DANGER, weight=ft.FontWeight.BOLD),
                        ], spacing=5),
                        ft.Text(str(snippet), size=11, color=ft.Colors.GREY_700, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(self._entry_amount_text(m), size=11, color=ft.Colors.GREY_600),
                    ], spacing=4),
                    bgcolor=ft.Colors.GREY_50,
                    border_radius=12,
                    padding=8,
                )
            )
        if len(matches) > 3:
            controls.append(ft.Text(f"+ {len(matches)-3} {translate('more_matches')}", size=11, color=ft.Colors.GREY_600))
        return controls

    def _refresh_cards(self, e):
        try:
            repo = ExpenseRepository()
            expenses = repo.get_all(convert_to_display=False)
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل البيانات: {str(ex)}", True)
            return

        raw_search = self._current_search()
        normalized_query = normalize_search_text(raw_search)
        matching_by_company = defaultdict(list)
        visible_companies = None
        if normalized_query:
            try:
                self._last_search_results = repo.search_company_ledger(raw_search, limit=150)
            except Exception as ex:
                self._show_snackbar(f"تعذر البحث داخل القيود: {str(ex)}", True)
                self._last_search_results = []
            for item in self._last_search_results:
                company = item.get('company_name') or ''
                if company:
                    matching_by_company[company].append(item)
            visible_companies = set(matching_by_company.keys())
            self._search_banner(raw_search, len(self._last_search_results))
        else:
            self._last_search_results = []
            self._search_banner('', 0)

        groups = defaultdict(lambda: {'incoming': 0.0, 'outgoing': 0.0, 'records': [], 'waiting_payment': 0, 'persons': set()})
        for ex in expenses:
            company = ex.get('company_name') or ''
            if visible_companies is not None and company not in visible_companies:
                continue
            if ex.get('status') == 'waiting_payment':
                groups[company]['waiting_payment'] += 1
            else:
                groups[company][ex.get('type') or 'incoming'] += float(ex.get('amount') or ex.get('amount_base') or 0)
            if (ex.get('person_name') or '').strip():
                groups[company]['persons'].add((ex.get('person_name') or '').strip())
            groups[company]['records'].append(ex)

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
            matches = matching_by_company.get(company, [])

            net_color = SUCCESS if net >= 0 else DANGER
            details_query = raw_search if normalized_query else None
            content_controls = [
                ft.Row([
                    ft.Icon(ft.Icons.BUSINESS, color=PRIMARY, size=24),
                    ft.Text(company, size=16, weight=ft.FontWeight.BOLD, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.TOUCH_APP, color=PRIMARY, size=14),
                            ft.Text('اضغط للتفاصيل', size=10, color=PRIMARY, weight=ft.FontWeight.BOLD),
                        ], spacing=3, tight=True),
                        bgcolor=PRIMARY_SOFT,
                        border_radius=999,
                        padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                    ),
                    amount_pill(currency.format_amount(net, display_curr), net_color),
                ], spacing=6),
                ft.Divider(height=1, color=ft.Colors.GREY_200),
                ft.Row([
                    key_value_tile("📥 لنا", currency.format_amount(inc, display_curr), SUCCESS),
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_200),
                    key_value_tile("📤 له", currency.format_amount(out, display_curr), DANGER),
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_200),
                    key_value_tile("📋 عدد", str(len(vals['records']))),
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_200),
                    key_value_tile("👥 أشخاص", str(len(vals.get('persons') or []))),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                pill(
                    f"⏳ بانتظار الدفع: {vals['waiting_payment']}",
                    color=WARNING,
                    bgcolor="#FFF7E3",
                ) if vals['waiting_payment'] > 0 else ft.Container(width=0, height=0),
            ]
            content_controls.extend(self._match_preview_controls(company, matches, raw_search))
            content_controls.append(
                ft.Row([
                    action_text_button("قيد", ft.Icons.ADD, lambda e, c=company: self._add_record(c), color=SUCCESS),
                    action_text_button("سداد عني", ft.Icons.SWAP_HORIZ, lambda e, c=company: self._add_third_party_payment(paid_to_company=c), color=PRIMARY),
                    action_text_button("خدمة", ft.Icons.TRAVEL_EXPLORE, lambda e, c=company: self._add_service_case(client_company=c), color=PRIMARY),
                    action_text_button("مباشرة", ft.Icons.PERSON_ADD_ALT, lambda e, c=company: self._add_direct_service(company_name=c), color=WARNING),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND, wrap=True)
            )
            card = data_card(
                ft.Column(content_controls, spacing=10),
                padding=15,
                elevation=2,
                margin=ft.Margin(left=10, right=10, top=5, bottom=5),
                on_click=lambda e, c=company, r=vals['records'], q=details_query: self._show_details(c, r, q),
            )
            cards.append(card)

        if cards:
            self.net_text.value = currency.format_amount(total_net, display_curr)
            self.net_text.color = SUCCESS if total_net >= 0 else DANGER
            self.companies_count_text.value = str(len(cards))
            self.records_count_text.value = str(total_records)
            self.summary_bar.visible = True
        else:
            self.summary_bar.visible = False
            title = "لا توجد نتائج" if normalized_query else "لا توجد بيانات"
            subtitle = "جرّب اسمًا آخر أو كلمة من الملاحظات" if normalized_query else "اضغط + لإضافة قيد جديد"
            cards.append(empty_state(title, subtitle, icon=ft.Icons.SEARCH_OFF))

        self.cards_container.controls = cards
        self._page.update()

    async def _export_service_profit_report(self, e):
        try:
            from reports.reporting_center import PERIOD_ALL, REPORT_PROFIT, ReportingCenterService, export_report_html
            from services.file_export_service import FileExportService
            report = ReportingCenterService().build_report(REPORT_PROFIT, period=PERIOD_ALL)
            path = export_report_html(report)
            result = await FileExportService.open_file_async(self._page, path, title="تقرير أرباح الخدمات الداخلي")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء تقرير الأرباح: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في تقرير أرباح الخدمات: {str(ex)}", True)

    def _show_details(self, company_name, records, search_query=None):
        # Company details is a full screen workflow, not a modal dialog.
        # It contains reports, sharing, editing and a long ledger list; using an
        # AlertDialog for it on Android/Flet leaves a blank white dialog shell
        # after close.  Route it through AppLayout instead.
        layout = getattr(self._page, '_hawaa_app_layout', None)
        if layout is not None and hasattr(layout, 'open_company_details'):
            layout.open_company_details(company_name, records=records, search_query=search_query)
            return
        # Very old fallback: keep behavior functional if AppLayout is not present.
        from views.company_details_mobile_view import CompanyDetailsMobileView
        dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.BUSINESS, color=PRIMARY), ft.Text(company_name, size=18, weight=ft.FontWeight.BOLD, expand=True)]),
            content=ft.Container(content=CompanyDetailsMobileView(self._page, company_name, records, on_changed=lambda: self._refresh_cards(None), search_query=search_query), height=500, width=400),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: self._close_dialog(dialog))],
            inset_padding=20,
            scrollable=True
        )
        open_control(self._page, dialog)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)

    def _open_add_menu(self, e):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)
            return
        dlg = None

        def open_normal(_):
            self._close_dialog(dlg)
            self._add_record()

        def open_third_party(_):
            self._close_dialog(dlg)
            self._add_third_party_payment()

        def open_service_case(_):
            self._close_dialog(dlg)
            self._add_service_case()

        def open_direct_service(_):
            self._close_dialog(dlg)
            self._add_direct_service()

        dlg = ft.AlertDialog(
            title=ft.Text(translate('choose_operation'), weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.ADD), ft.Text(translate('normal_entry'))], tight=True),
                    on_click=open_normal,
                    bgcolor=SUCCESS,
                    color=ft.Colors.WHITE,
                ),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.TRAVEL_EXPLORE), ft.Text("خدمة لعميل عبر مورد")], tight=True),
                    on_click=open_service_case,
                    bgcolor=PRIMARY,
                    color=ft.Colors.WHITE,
                ),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_ALT), ft.Text("خدمة مباشرة / ربح زبون")], tight=True),
                    on_click=open_direct_service,
                    bgcolor=WARNING,
                    color=ft.Colors.WHITE,
                ),
                ft.FilledButton(
                    content=ft.Row([ft.Icon(ft.Icons.SWAP_HORIZ), ft.Text(translate('third_party_payment'))], tight=True),
                    on_click=open_third_party,
                    bgcolor=PRIMARY,
                    color=ft.Colors.WHITE,
                ),
            ], spacing=12, tight=True),
            actions=[ft.TextButton(translate('cancel'), on_click=lambda _: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)


    def _add_direct_service(self, company_name=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة خدمات مباشرة", True)
            return
        from views.dialogs.direct_service_dialog import DirectServiceDialog
        dialog = DirectServiceDialog(
            page=self._page,
            on_save=lambda _: self._refresh_cards(None),
            company_name=company_name,
        )
        open_control(self._page, dialog)

    def _add_service_case(self, client_company=None, supplier_company=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة ملفات خدمات", True)
            return
        from views.dialogs.service_case_dialog import ServiceCaseDialog
        dialog = ServiceCaseDialog(
            page=self._page,
            on_save=lambda _: self._refresh_cards(None),
            client_company_name=client_company,
            supplier_company_name=supplier_company,
        )
        open_control(self._page, dialog)

    def _add_third_party_payment(self, payer_company=None, paid_to_company=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)
            return
        from views.dialogs.third_party_payment_dialog import ThirdPartyPaymentDialog
        dialog = ThirdPartyPaymentDialog(
            page=self._page,
            on_save=lambda _: self._refresh_cards(None),
            payer_company_name=payer_company,
            paid_to_company_name=paid_to_company,
        )
        open_control(self._page, dialog)

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
