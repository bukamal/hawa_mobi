# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, run_async_task
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from views.design_system.responsive import bottom_safe_spacer, page_width
from views.ui_kit import (
    show_snackbar, empty_state, data_card, amount_pill, key_value_tile, pill,
    summary_bar, metric_tile, info_banner, search_field, secondary_button,
    modern_action_button, operation_menu_button, PRIMARY, PRIMARY_SOFT,
    SUCCESS, DANGER, WARNING, MUTED, TEXT, BORDER,
)
from services.company_search_service import enrich_expense_match, normalize_search_text
from services.ledger_operation_service import operation_label

class CompanyDetailsMobileView(ft.Column):
    def __init__(self, page, company_name, records=None, on_changed=None, search_query=None):
        super().__init__()
        self._page = page
        self.company_name = company_name
        self.on_changed = on_changed
        self.search_query = (search_query or "").strip()
        # لا تستخدم القائمة الممرّرة كحقيقة بعد فتح النافذة؛ قد تكون snapshot قديمة
        # من شاشة الحسابات. اجلب دائماً من قاعدة البيانات عند بناء التفاصيل.
        repo = ExpenseRepository()
        self._all_records = sorted(repo.get_by_company(company_name, convert_to_display=False), key=lambda x: x['date'])
        self.records = list(self._all_records)
        self._page_size = 20
        self._visible_limit = self._page_size
        self._last_ledger_layout_mode = None
        self._mobile_ledger_rows = []
        self._desktop_ledger_table = None
        self.spacing = 10
        self.expand = True
        self.scroll = ft.ScrollMode.AUTO

        self.summary_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.total_in_text = ft.Text("0", size=15, weight=ft.FontWeight.BOLD, color=SUCCESS)
        self.total_out_text = ft.Text("0", size=15, weight=ft.FontWeight.BOLD, color=DANGER)
        self.net_text = ft.Text("0", size=15, weight=ft.FontWeight.BOLD, color=PRIMARY)
        self.waiting_text = ft.Text("0", size=15, weight=ft.FontWeight.BOLD, color=WARNING)
        self.summary_panel = summary_bar([
            metric_tile("لنا", self.total_in_text),
            metric_tile("له", self.total_out_text),
            metric_tile("الصافي", self.net_text),
            metric_tile("انتظار", self.waiting_text),
        ], visible=True, bgcolor=ft.Colors.GREY_100)
        self.people_summary = ft.Column(spacing=6, visible=False)
        self.records_list = ft.Column(spacing=8)
        self.local_search = search_field("ابحث داخل الحساب", self._on_filter_changed)
        self.local_search.value = self.search_query
        self.direction_filter = ft.Dropdown(
            label="نوع الحركة", value="الكل", width=170,
            options=[ft.dropdown.Option("الكل"), ft.dropdown.Option("لنا"), ft.dropdown.Option("له"), ft.dropdown.Option("انتظار")],
            on_change=self._on_filter_changed, border_radius=12, filled=True,
            border_color=BORDER, focused_border_color=PRIMARY,
        )
        persons = sorted({str(r.get('person_name') or '').strip() for r in self._all_records if str(r.get('person_name') or '').strip()})
        self.person_filter = ft.Dropdown(
            label="الشخص", value="الكل", width=190,
            options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(name) for name in persons],
            on_change=self._on_filter_changed, border_radius=12, filled=True,
            border_color=BORDER, focused_border_color=PRIMARY,
        )
        self.sort_filter = ft.Dropdown(
            label="الترتيب", value="الأحدث أولاً", width=170,
            options=[ft.dropdown.Option("الأحدث أولاً"), ft.dropdown.Option("الأقدم أولاً")],
            on_change=self._on_filter_changed, border_radius=12, filled=True,
            border_color=BORDER, focused_border_color=PRIMARY,
        )
        self.filter_surface = data_card(ft.Column([
            self.local_search,
            ft.Row([self.direction_filter, self.person_filter, self.sort_filter], spacing=8, run_spacing=8, wrap=True),
        ], spacing=10), elevation=0)
        self.pagination_text = ft.Text("", size=12, color=MUTED, text_align=ft.TextAlign.CENTER)
        self.load_more_button = secondary_button("عرض المزيد", ft.Icons.EXPAND_MORE, self._load_more)
        self.pagination_bar = ft.Container(
            content=ft.Column([self.pagination_text, self.load_more_button], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            visible=False,
            padding=ft.Padding(left=12, right=12, top=4, bottom=12),
        )

        self.report_actions = ft.Row([
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.ADD_CARD), ft.Text("إضافة قيد")], tight=True),
                on_click=self._add_record,
                bgcolor=SUCCESS,
                color=ft.Colors.WHITE,
                tooltip=f"إضافة قيد داخل حساب {company_name}",
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_ALT), ft.Text("خدمة مباشرة")], tight=True),
                on_click=self._add_direct_service,
                bgcolor=WARNING,
                color=ft.Colors.WHITE,
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED), ft.Text("دفعة مجمعة")], tight=True),
                on_click=self._add_batch_payment,
                bgcolor=PRIMARY,
                color=ft.Colors.WHITE,
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.PRINT), ft.Text("كشف الحساب")], tight=True),
                on_click=self._export_printable_statement,
                bgcolor=PRIMARY,
                color=ft.Colors.WHITE,
            ),
            ft.OutlinedButton(
                content=ft.Row([ft.Icon(ft.Icons.SHARE_OUTLINED), ft.Text("تصدير ومشاركة")], tight=True),
                on_click=self._open_export_menu,
            ),
        ], spacing=8, wrap=True)
        search_banner = info_banner(
            f"نتائج داخل {company_name} عن: {self.search_query}",
            icon=ft.Icons.MANAGE_SEARCH,
            color=PRIMARY,
            bgcolor=PRIMARY_SOFT,
        ) if normalize_search_text(self.search_query) else ft.Container(width=0, height=0)
        self.controls = [
            self.summary_panel, search_banner, self.report_actions, self.people_summary,
            self.filter_surface, ft.Divider(height=1), self.records_list,
            self.pagination_bar, bottom_safe_spacer(self._page),
        ]
        self._load_data()

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)


    def _on_filter_changed(self, e=None):
        self._visible_limit = self._page_size
        self.search_query = str(self.local_search.value or '').strip()
        self._load_data()

    def _load_more(self, e=None):
        self._visible_limit += self._page_size
        self._load_data()

    def _filtered_records(self):
        query = str(self.local_search.value or '').strip()
        direction = self.direction_filter.value or "الكل"
        person = self.person_filter.value or "الكل"
        rows = []
        normalized_query = normalize_search_text(query)
        company_query = normalized_query and normalized_query == normalize_search_text(self.company_name)
        for record in self._all_records:
            if normalized_query and not company_query and not enrich_expense_match(record, query):
                continue
            if person != "الكل" and str(record.get('person_name') or '').strip() != person:
                continue
            is_waiting = int(record.get('is_settleable') or 0) == 1 and float(record.get('remaining_amount_original') or 0) > 0.005
            if direction == "لنا" and (record.get('type') != 'incoming' or is_waiting):
                continue
            if direction == "له" and (record.get('type') != 'outgoing' or is_waiting):
                continue
            if direction == "انتظار" and not is_waiting:
                continue
            rows.append(record)
        rows.sort(key=lambda item: str(item.get('date') or ''), reverse=self.sort_filter.value != "الأقدم أولاً")
        return rows

    def _open_export_menu(self, e=None):
        dlg = None

        def run_and_close(callback):
            def handler(event=None):
                self._close_dialog(dlg)
                callback(event)
            return handler

        dlg = ft.AlertDialog(
            title=ft.Text("تصدير ومشاركة كشف الحساب", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                modern_action_button("كشف مطابقة", ft.Icons.FACT_CHECK, run_and_close(self._export_reconciliation_statement)),
                modern_action_button("مشاركة HTML", ft.Icons.SHARE, run_and_close(self._share_statement), color=SUCCESS, bgcolor="#E9F8F0"),
                modern_action_button("صورة PNG", ft.Icons.IMAGE, run_and_close(lambda ev: run_async_task(self._page, self._share_statement_image_async, ev))),
                modern_action_button("واتساب", ft.Icons.CHAT, run_and_close(self._share_statement_whatsapp), color=SUCCESS, bgcolor="#E9F8F0"),
                modern_action_button("ملف CSV", ft.Icons.TABLE_VIEW, run_and_close(self._export_csv_statement)),
            ], spacing=10, tight=True),
            actions=[ft.TextButton("إلغاء", on_click=lambda ev: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)

    def _open_record_actions(self, record):
        is_viewer = UserSession.get_current() and UserSession.get_current().get('role') == 'viewer'
        if is_viewer:
            self._show_snackbar("الحساب للعرض فقط", False)
            return
        source_type = record.get('source_type')
        locked = int(record.get('is_locked') or 0)
        actions = []
        dlg = None

        def add_action(label, icon, callback, color=PRIMARY, bgcolor=PRIMARY_SOFT):
            def handler(event=None):
                self._close_dialog(dlg)
                callback(record)
            actions.append(modern_action_button(label, icon, handler, color=color, bgcolor=bgcolor))

        payment_source = source_type in ('payment_received', 'payment_paid')
        settleable = int(record.get('is_settleable') or 0) == 1 and not payment_source
        remaining = float(record.get('remaining_amount_original') or 0)
        paid = float(record.get('paid_amount_original') or 0)
        if settleable and remaining > 0.005:
            add_action("تسجيل دفعة", ft.Icons.PAYMENTS_OUTLINED, self._open_payment_dialog, color=SUCCESS, bgcolor="#E9F8F0")
        if settleable and paid > 0.005 and remaining <= 0.005:
            add_action("عرض سجل الدفعات", ft.Icons.RECEIPT_LONG_OUTLINED, self._open_payment_dialog)

        if not source_type and not locked:
            add_action("تعديل القيد", ft.Icons.EDIT, self._edit_record)
            add_action("حذف القيد", ft.Icons.DELETE, self._delete_record, color=DANGER, bgcolor="#FDECEC")
        elif source_type in ('third_party_payment', 'third_party_payment_reversal'):
            if source_type == 'third_party_payment':
                add_action("تعديل العملية", ft.Icons.EDIT_NOTE, self._edit_third_party)
            add_action("حذف العملية كاملة", ft.Icons.DELETE_FOREVER, self._delete_third_party, color=DANGER, bgcolor="#FDECEC")
        elif source_type in ('service_case_client', 'service_case_supplier', 'service_case_reversal'):
            if source_type != 'service_case_reversal':
                add_action("تعديل ملف الخدمة", ft.Icons.EDIT_NOTE, self._edit_service_case)
            add_action("حذف ملف الخدمة كاملاً", ft.Icons.DELETE_FOREVER, self._delete_service_case, color=DANGER, bgcolor="#FDECEC")
        elif source_type in ('direct_service_client', 'direct_service_supplier', 'direct_service_reversal'):
            if source_type != 'direct_service_reversal':
                add_action("تعديل الخدمة", ft.Icons.EDIT_NOTE, self._edit_direct_service)
            add_action("حذف الخدمة كاملة", ft.Icons.DELETE_FOREVER, self._delete_direct_service, color=DANGER, bgcolor="#FDECEC")
        if not actions:
            self._show_snackbar("لا توجد إجراءات متاحة لهذا القيد", False)
            return
        dlg = ft.AlertDialog(
            title=ft.Text("إجراءات القيد", weight=ft.FontWeight.BOLD),
            content=ft.Column(actions, spacing=10, tight=True),
            actions=[ft.TextButton("إغلاق", on_click=lambda ev: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)

    def _match_chip(self, record):
        match = enrich_expense_match(record, self.search_query)
        if not match:
            return ft.Container(width=0, height=0)
        label = match.get('matched_label') or 'مطابقة'
        snippet = match.get('snippet') or ''
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SEARCH, color=PRIMARY, size=14),
                ft.Text(f"{label}: {snippet}", size=11, color=PRIMARY, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=5),
            bgcolor=PRIMARY_SOFT,
            border_radius=10,
            padding=ft.Padding(left=8, right=8, top=5, bottom=5),
        )

    @staticmethod
    def _record_sort_key(record):
        try:
            record_id = int(record.get("id") or 0)
        except Exception:
            record_id = 0
        return (
            str(record.get("date") or ""),
            str(record.get("created_at") or record.get("updated_at") or ""),
            record_id,
        )

    @staticmethod
    def _source_label(record):
        source_type = str(record.get("source_type") or "").strip()
        labels = {
            "third_party_payment": "سداد بالنيابة",
            "third_party_payment_reversal": "سداد بالنيابة قديم/معكوس",
            "service_case_client": "ملف خدمة · عميل",
            "service_case_supplier": "ملف خدمة · مورد",
            "service_case_reversal": "ملف خدمة قديم/معكوس",
            "direct_service_client": "خدمة مباشرة · عميل",
            "direct_service_supplier": "خدمة مباشرة · مورد",
            "direct_service_reversal": "خدمة مباشرة قديمة/معكوسة",
            "payment_received": "دفعة مستلمة",
            "payment_paid": "دفعة مدفوعة",
            "customer_credit": "رصيد دائن للعميل",
            "supplier_advance": "دفعة مقدمة للمورد",
        }
        return labels.get(source_type, operation_label(record.get("operation_type")))

    def _ledger_layout_mode(self):
        """Use compact ledger cards on narrow Android surfaces.

        Flutter/Flet DataTable is intentionally reserved for wide layouts.  On
        phones it can receive unbounded horizontal constraints when nested in
        the page's vertical scroller, which renders as a large grey ErrorWidget
        in release APKs.
        """
        return "compact" if page_width(self._page) < 720 else "table"

    def _on_responsive_resize(self):
        """Rebuild only when rotation crosses the compact/table breakpoint."""
        mode = self._ledger_layout_mode()
        if mode != self._last_ledger_layout_mode:
            self._load_data()

    @staticmethod
    def _payment_label_and_color(record):
        payment_status = str(record.get("payment_status") or "")
        labels = {
            "unpaid": "غير مدفوع",
            "partial": "مدفوع جزئيًا",
            "paid": "مدفوع بالكامل",
            "not_applicable": "حركة مالية",
        }
        color = SUCCESS if payment_status == "paid" else (
            WARNING if payment_status in ("partial", "unpaid") else MUTED
        )
        return labels.get(payment_status, payment_status or "حركة مالية"), color

    def _record_display_values(self, record, running_by_key, display_curr):
        original_currency = record.get("currency_original") or display_curr
        amount_value = float(record.get("amount_original") or 0)
        amount_str = currency.format_amount_ui(amount_value, original_currency)
        settleable = int(record.get("is_settleable") or 0) == 1
        remaining_amount = float(record.get("remaining_amount_original") or 0)
        paid_amount = float(record.get("paid_amount_original") or 0)
        is_waiting = settleable and remaining_amount > 0.005

        running_usd = float(running_by_key.get(record.get("id") or id(record), 0.0) or 0.0)
        running_display = currency.convert(abs(running_usd), "USD", display_curr)
        running_text = currency.format_amount_ui(running_display, display_curr)
        running_direction = "لنا" if running_usd >= 0 else "له"
        running_color = SUCCESS if running_usd >= 0 else DANGER

        description = (
            str(record.get("print_description") or "").strip()
            or str(record.get("notes") or "").strip()
            or operation_label(record.get("operation_type"))
        )
        person = str(record.get("person_name") or "").strip()
        service_type = str(record.get("service_type") or "غير محدد").strip()
        subtitle_parts = [part for part in (person, service_type) if part and part != "غير محدد"]

        payment_label, payment_color = self._payment_label_and_color(record)
        direction = "لنا" if record.get("type") == "incoming" else "له"
        direction_color = WARNING if is_waiting else (SUCCESS if direction == "لنا" else DANGER)
        direction_bg = "#FFF4DE" if is_waiting else ("#E9F8F0" if direction == "لنا" else "#FDECEC")

        return {
            "currency": original_currency,
            "amount": amount_str,
            "settleable": settleable,
            "paid": paid_amount,
            "remaining": remaining_amount,
            "payment_label": payment_label,
            "payment_color": payment_color,
            "direction": direction,
            "direction_color": direction_color,
            "direction_bg": direction_bg,
            "running_text": running_text,
            "running_direction": running_direction,
            "running_color": running_color,
            "description": description or "—",
            "subtitle": " · ".join(subtitle_parts),
        }

    def _build_mobile_ledger_cards(self, records, running_by_key, display_curr, is_viewer):
        cards = []
        for idx, record in enumerate(records, 1):
            values = self._record_display_values(record, running_by_key, display_curr)
            action_control = (
                ft.Icon(ft.Icons.VISIBILITY_OUTLINED, color=MUTED, size=19)
                if is_viewer
                else operation_menu_button(
                    lambda e, rec=record: self._open_record_actions(rec),
                    tooltip="إجراءات القيد",
                )
            )

            payment_strip = ft.Container(height=0)
            if values["settleable"]:
                payment_strip = ft.Container(
                    content=ft.Row([
                        key_value_tile(
                            "مدفوع",
                            currency.format_amount_ui(values["paid"], values["currency"]),
                            color=SUCCESS,
                        ),
                        key_value_tile(
                            "متبقي",
                            currency.format_amount_ui(values["remaining"], values["currency"]),
                            color=values["payment_color"],
                        ),
                        key_value_tile("الحالة", values["payment_label"], color=values["payment_color"]),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.START),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=10,
                    padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                )

            match_control = self._match_chip(record) if normalize_search_text(self.search_query) else ft.Container(height=0)
            card = data_card(
                ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(str(record.get("date") or "—"), size=12, weight=ft.FontWeight.BOLD, color=TEXT),
                            ft.Text(self._source_label(record), size=10, color=PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=2, expand=True),
                        ft.Text(f"#{idx}", size=10, color=MUTED),
                        action_control,
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(values["description"], size=13, weight=ft.FontWeight.BOLD, color=TEXT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(values["subtitle"], size=11, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                    if values["subtitle"] else ft.Container(height=0),
                    ft.Container(
                        content=ft.Row([
                            key_value_tile(values["direction"], values["amount"], color=values["direction_color"]),
                            key_value_tile(
                                "الرصيد بعد القيد",
                                f"{values['running_text']} {values['running_direction']}",
                                color=values["running_color"],
                            ),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
                        bgcolor=values["direction_bg"],
                        border_radius=10,
                        padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                    ),
                    payment_strip,
                    match_control,
                ], spacing=8),
                padding=12,
                elevation=0,
            )
            cards.append(card)

        self._mobile_ledger_rows = cards
        self._desktop_ledger_table = None
        heading = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=PRIMARY, size=20),
                    ft.Text("قيود الشركة", weight=ft.FontWeight.BOLD, color=TEXT, expand=True),
                    pill(f"{len(records)} قيد", color=PRIMARY, bgcolor=PRIMARY_SOFT, size=10),
                ], spacing=7, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("اعرض التفاصيل والسداد من زر الإجراءات داخل كل قيد", size=10, color=MUTED),
            ], spacing=4),
            padding=ft.Padding(left=10, right=10, top=6, bottom=2),
        )
        return [heading, *cards]

    def _build_ledger_table(self, records, running_by_key, display_curr, is_viewer):
        rows = []
        for idx, record in enumerate(records, 1):
            values = self._record_display_values(record, running_by_key, display_curr)
            incoming = values["amount"] if record.get("type") == "incoming" else "—"
            outgoing = values["amount"] if record.get("type") == "outgoing" else "—"
            incoming_color = values["direction_color"] if record.get("type") == "incoming" else MUTED
            outgoing_color = values["direction_color"] if record.get("type") == "outgoing" else MUTED

            if values["settleable"]:
                payment_content = ft.Column([
                    ft.Text(
                        f"مدفوع: {currency.format_amount_ui(values['paid'], values['currency'])}",
                        size=10, color=SUCCESS,
                    ),
                    ft.Text(
                        f"متبقي: {currency.format_amount_ui(values['remaining'], values['currency'])}",
                        size=10, weight=ft.FontWeight.BOLD, color=values["payment_color"],
                    ),
                    ft.Text(values["payment_label"], size=9, color=values["payment_color"]),
                ], spacing=1, tight=True)
            else:
                payment_content = ft.Text(values["payment_label"], size=10, color=MUTED)

            action_control = (
                ft.Icon(ft.Icons.VISIBILITY_OUTLINED, color=MUTED, size=19)
                if is_viewer
                else operation_menu_button(
                    lambda e, rec=record: self._open_record_actions(rec),
                    tooltip="إجراءات القيد",
                )
            )
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Container(
                    content=ft.Column([
                        ft.Text(str(record.get("date") or "—"), size=12, weight=ft.FontWeight.BOLD),
                        ft.Text(f"#{idx}", size=10, color=MUTED),
                    ], spacing=2, tight=True),
                    width=92,
                )),
                ft.DataCell(ft.Container(
                    content=ft.Column([
                        ft.Text(values["description"], size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(values["subtitle"], size=10, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                        if values["subtitle"] else ft.Container(height=0),
                    ], spacing=2, tight=True),
                    width=230,
                )),
                ft.DataCell(ft.Container(ft.Text(incoming, size=12, weight=ft.FontWeight.BOLD, color=incoming_color), width=118, alignment=ft.alignment.center_right)),
                ft.DataCell(ft.Container(ft.Text(outgoing, size=12, weight=ft.FontWeight.BOLD, color=outgoing_color), width=118, alignment=ft.alignment.center_right)),
                ft.DataCell(ft.Container(payment_content, width=170, alignment=ft.alignment.center_right)),
                ft.DataCell(ft.Container(
                    content=ft.Column([
                        ft.Text(values["running_text"], size=12, weight=ft.FontWeight.BOLD, color=values["running_color"]),
                        ft.Text(values["running_direction"], size=10, color=values["running_color"]),
                    ], spacing=1, tight=True, horizontal_alignment=ft.CrossAxisAlignment.END),
                    width=120, alignment=ft.alignment.center_right,
                )),
                ft.DataCell(ft.Container(
                    content=ft.Text(self._source_label(record), size=11, color=PRIMARY, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    width=150,
                )),
                ft.DataCell(ft.Container(action_control, width=46, alignment=ft.alignment.center)),
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("التاريخ", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("البيان", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("لنا", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("له", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("السداد", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("الرصيد", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("المصدر", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("إجراء", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=14,
            horizontal_margin=12,
            heading_row_height=46,
            data_row_min_height=62,
            data_row_max_height=76,
            divider_thickness=0.8,
            heading_row_color=ft.Colors.GREY_100,
        )
        self._desktop_ledger_table = table
        self._mobile_ledger_rows = []
        table_surface = ft.Container(
            content=ft.Row([table], scroll=ft.ScrollMode.AUTO),
            border=ft.border.all(1, BORDER),
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
        )
        return data_card(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.TABLE_ROWS_OUTLINED, color=PRIMARY, size=20),
                ft.Text("جدول قيود الشركة", weight=ft.FontWeight.BOLD, color=TEXT, expand=True),
                ft.Text("مرّر أفقياً لرؤية جميع الأعمدة", size=10, color=MUTED),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            table_surface,
        ], spacing=8), padding=8, elevation=0)

    def _load_data(self):
        display_curr = currency.get_display_currency()
        approved_records = [r for r in self._all_records if r.get('status', 'approved') != 'waiting_payment']
        waiting_count = len([r for r in self._all_records if int(r.get('is_settleable') or 0) == 1 and float(r.get('remaining_amount_original') or 0) > 0.005])
        total_in_usd = sum(float(r['amount']) for r in approved_records if r['type'] == 'incoming')
        total_out_usd = sum(float(r['amount']) for r in approved_records if r['type'] == 'outgoing')
        net_usd = total_in_usd - total_out_usd
        total_in = currency.convert(total_in_usd, 'USD', display_curr)
        total_out = currency.convert(total_out_usd, 'USD', display_curr)
        net = currency.convert(net_usd, 'USD', display_curr)

        self.summary_text.value = f"📥 {currency.format_amount_ui(total_in, display_curr)}   📤 {currency.format_amount_ui(total_out, display_curr)}   💰 {currency.format_amount_ui(net, display_curr)}   ⏳ {waiting_count}"
        self.total_in_text.value = currency.format_amount_ui(total_in, display_curr)
        self.total_out_text.value = currency.format_amount_ui(total_out, display_curr)
        self.net_text.value = currency.format_amount_ui(net, display_curr)
        self.net_text.color = SUCCESS if net_usd >= 0 else DANGER
        self.waiting_text.value = str(waiting_count)

        person_buckets = {}
        for rr in self._all_records:
            person = (rr.get('person_name') or '').strip()
            if not person:
                continue
            item = person_buckets.setdefault(person, {'incoming': 0.0, 'outgoing': 0.0, 'count': 0})
            item['count'] += 1
            if rr.get('status') != 'waiting_payment':
                if rr.get('type') == 'incoming':
                    item['incoming'] += float(rr.get('amount') or 0)
                else:
                    item['outgoing'] += float(rr.get('amount') or 0)
        if person_buckets:
            chips = [ft.Text("الأشخاص داخل الحساب", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY)]
            for person, item in sorted(person_buckets.items(), key=lambda kv: kv[0])[:8]:
                net_p = currency.convert(item['incoming'] - item['outgoing'], 'USD', display_curr)
                chips.append(pill(f"{person}: {currency.format_amount_ui(net_p, display_curr)} · {item['count']} قيد", color=PRIMARY, bgcolor=PRIMARY_SOFT))
            self.people_summary.controls = chips
            self.people_summary.visible = True
        else:
            self.people_summary.controls = []
            self.people_summary.visible = False

        filtered_records = self._filtered_records()
        chronological = sorted(self._all_records, key=self._record_sort_key)
        running_by_key = {}
        running_usd = 0.0
        for item in chronological:
            if item.get('status') != 'waiting_payment':
                running_usd += float(item.get('amount') or 0) if item.get('type') == 'incoming' else -float(item.get('amount') or 0)
            running_by_key[item.get('id') or id(item)] = running_usd

        visible_records = filtered_records[:self._visible_limit]
        is_viewer = UserSession.get_current() and UserSession.get_current().get('role') == 'viewer'

        if not visible_records:
            table_controls = [empty_state("لا توجد قيود مطابقة", "غيّر البحث أو الفلاتر", icon=ft.Icons.RECEIPT_LONG, padding=30)]
            self.pagination_bar.visible = False
        else:
            layout_mode = self._ledger_layout_mode()
            self._last_ledger_layout_mode = layout_mode
            if layout_mode == "compact":
                table_controls = self._build_mobile_ledger_cards(
                    visible_records, running_by_key, display_curr, is_viewer
                )
            else:
                table_controls = [self._build_ledger_table(
                    visible_records, running_by_key, display_curr, is_viewer
                )]
            shown = min(len(visible_records), len(filtered_records))
            self.pagination_text.value = f"عرض {shown} من {len(filtered_records)} قيد"
            self.load_more_button.visible = shown < len(filtered_records)
            self.pagination_bar.visible = len(filtered_records) > self._page_size

        self.records = filtered_records
        self.records_list.controls = table_controls
        self._page.update()


    def _open_payment_dialog(self, record):
        try:
            from views.dialogs.payment_dialog import PaymentDialog
            dialog = PaymentDialog(self._page, record, on_save=lambda _: self._reload())
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"تعذر فتح الدفعات: {str(ex)}", True)

    def _add_record(self, e=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)
            return
        try:
            from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
            dialog = AddEditExpenseDialog(
                page=self._page,
                on_save=lambda _: self._reload(),
                company_name=self.company_name,
            )
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"خطأ في فتح إضافة القيد: {str(ex)}", True)

    def _add_direct_service(self, e=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة خدمات مباشرة", True)
            return
        from views.dialogs.direct_service_dialog import DirectServiceDialog
        dialog = DirectServiceDialog(page=self._page, on_save=lambda _: self._reload(), supplier_company_name=self.company_name)
        open_control(self._page, dialog)

    def _add_batch_payment(self, e=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لتسجيل دفعات", True)
            return
        try:
            from views.dialogs.batch_payment_dialog import BatchPaymentDialog
            dialog = BatchPaymentDialog(
                page=self._page,
                initial_company=self.company_name,
                on_save=lambda _: self._reload(),
            )
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"تعذر فتح الدفعة المجمعة: {str(ex)}", True)

    async def _export_printable_statement(self, e):
        try:
            from reports.account_statement import export_account_statement_html
            from services.file_export_service import FileExportService
            path = export_account_statement_html(self.company_name, self.records)
            result = await FileExportService.open_file_async(self._page, path, title="فتح أو طباعة كشف حساب")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء كشف الطباعة: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في إنشاء الكشف: {str(ex)}", True)


    async def _export_reconciliation_statement(self, e):
        try:
            from reports.account_statement import export_reconciliation_statement_html
            from services.file_export_service import FileExportService
            path = export_reconciliation_statement_html(self.company_name, self.records)
            result = await FileExportService.open_file_async(self._page, path, title="فتح أو طباعة كشف مطابقة")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء كشف المطابقة: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في إنشاء كشف المطابقة: {str(ex)}", True)

    async def _share_statement(self, e):
        try:
            # المشاركة العامة تستخدم كشف المطابقة المختصر؛ أما زر "كشف للطباعة"
            # فيبقى للكشف التفصيلي الداخلي/العريض.
            from reports.account_statement import export_reconciliation_statement_html
            from reports.config import get_report_settings
            from reports.share import share_file_async
            settings = get_report_settings()
            path = export_reconciliation_statement_html(self.company_name, self.records, layout_mode=settings.get('whatsapp_statement_layout_mode'))
            message = f"كشف مطابقة - {self.company_name}"
            result = await share_file_async(self._page, path, message, open_whatsapp=False, title="مشاركة كشف المطابقة")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء كشف المطابقة: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في مشاركة كشف المطابقة: {str(ex)}", True)


    async def _share_statement_image_async(self, e=None):
        self._show_snackbar("جارٍ إنشاء صورة كشف المطابقة...", False)
        try:
            import asyncio
            from reports.image_export import export_statement_image
            from reports.share import share_file_async
            path = await asyncio.to_thread(lambda: export_statement_image(self.company_name, self.records, reconciliation=True, max_rows=50))
            message = f"صورة كشف مطابقة - {self.company_name}"
            result = await share_file_async(self._page, path, message, open_whatsapp=False, title="مشاركة صورة كشف المطابقة")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء صورة الكشف: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في إنشاء صورة الكشف: {str(ex)}", True)

    async def _share_statement_whatsapp(self, e):
        try:
            from reports.account_statement import export_reconciliation_statement_html
            from reports.config import get_report_settings
            from reports.share import share_file_async
            settings = get_report_settings()
            path = export_reconciliation_statement_html(self.company_name, self.records, layout_mode=settings.get('whatsapp_statement_layout_mode'))
            message = f"كشف مطابقة - {self.company_name}"
            result = await share_file_async(self._page, path, message, open_whatsapp=True, title="مشاركة كشف الحساب عبر واتساب")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء الكشف: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في مشاركة واتساب: {str(ex)}", True)

    async def _export_csv_statement(self, e):
        try:
            from reports.account_statement import export_account_statement_csv
            from services.file_export_service import FileExportService
            path = export_account_statement_csv(self.company_name, self.records)
            result = await FileExportService.share_file_async(self._page, path, f"CSV - كشف حساب {self.company_name}", open_whatsapp=False, title="مشاركة CSV كشف الحساب")
            self._show_snackbar(result.message if result.ok else result.message or f"تم إنشاء CSV: {path}", not result.ok)
        except Exception as ex:
            self._show_snackbar(f"خطأ في إنشاء CSV: {str(ex)}", True)

    def _edit_record(self, record):
        from views.dialogs.add_edit_expense_dialog import AddEditExpenseDialog
        dialog = AddEditExpenseDialog(page=self._page, on_save=lambda _: self._reload(), expense=record)
        open_control(self._page, dialog)

    def _delete_record(self, record):
        def confirm(e):
            try:
                repo = ExpenseRepository()
                repo.delete(record['id'], UserSession.get_current().get('id') if UserSession.get_current() else None)
                self._show_snackbar("تم الحذف", False)
                self._reload()
            except Exception as ex:
                self._show_snackbar(f"خطأ: {str(ex)}", True)
            self._close_dialog(dlg)

        btn_yes = ft.TextButton("نعم", on_click=confirm)
        btn_no = ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))

        dlg = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text(f"حذف قيد بمبلغ {record['amount_original']} {record['currency_original']}؟"),
            actions=[btn_yes, btn_no]
        )
        open_control(self._page, dlg)

    def _confirm_linked_operation_delete(self, record, *, title, operation_label_text, delete_callback):
        ref = str(record.get('source_ref') or '').strip()
        if not ref:
            self._show_snackbar("لا يوجد مرجع للعملية المراد حذفها", True)
            return
        reason_field = ft.TextField(
            label="سبب الحذف",
            multiline=True,
            min_lines=2,
            max_lines=3,
            hint_text="مثال: إدخال مكرر أو عملية أضيفت بالخطأ",
            autofocus=True,
        )

        def confirm(e):
            reason = str(reason_field.value or '').strip()
            if not reason:
                self._show_snackbar("سبب الحذف مطلوب", True)
                return
            try:
                user = UserSession.get_current() or {}
                delete_callback(ref, reason, user.get('id'))
                self._show_snackbar(f"تم حذف {operation_label_text} وجميع القيود المرتبطة دون إنشاء قيد عكسي", False)
                self._reload()
                self._close_dialog(dlg)
            except Exception as ex:
                self._show_snackbar(f"خطأ في الحذف: {str(ex)}", True)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.DELETE_FOREVER, color=DANGER),
                ft.Text(title, weight=ft.FontWeight.BOLD, color=DANGER),
            ], spacing=8),
            content=ft.Column([
                ft.Text(
                    f"سيُحذف {operation_label_text} {ref} نهائياً مع جميع قيود العميل والمورد والمكونات التابعة له. "
                    "لن يُنشأ قيد عكسي، وسيتغير رصيد كل شركة مرتبطة مباشرة. لا يمكن التراجع عن هذه العملية.",
                    size=13,
                ),
                reason_field,
            ], tight=True, spacing=12),
            actions=[
                ft.TextButton("حذف نهائي", on_click=confirm, style=ft.ButtonStyle(color=DANGER)),
                ft.TextButton("إلغاء", on_click=lambda e: self._close_dialog(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_control(self._page, dlg)

    def _delete_third_party(self, record):
        from database import ThirdPartyPaymentRepository
        self._confirm_linked_operation_delete(
            record,
            title="حذف عملية السداد بالنيابة",
            operation_label_text="عملية السداد بالنيابة",
            delete_callback=lambda ref, reason, uid: ThirdPartyPaymentRepository().delete_payment_on_behalf(
                ref, user_id=uid, reason=reason
            ),
        )

    def _delete_service_case(self, record):
        from database import ServiceCaseRepository
        self._confirm_linked_operation_delete(
            record,
            title="حذف ملف الخدمة",
            operation_label_text="ملف الخدمة",
            delete_callback=lambda ref, reason, uid: ServiceCaseRepository().delete(
                ref, reason=reason, user_id=uid
            ),
        )

    def _delete_direct_service(self, record):
        from database import DirectServiceRepository
        self._confirm_linked_operation_delete(
            record,
            title="حذف الخدمة المباشرة",
            operation_label_text="الخدمة المباشرة",
            delete_callback=lambda ref, reason, uid: DirectServiceRepository().delete(
                ref, user_id=uid, reason=reason
            ),
        )

    def _edit_third_party(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لتعديل العملية", True)
            return
        try:
            from database import ThirdPartyPaymentRepository
            from views.dialogs.third_party_payment_dialog import ThirdPartyPaymentDialog
            payment = ThirdPartyPaymentRepository().get_by_reference(ref)
            if payment.get('status') == 'reversed':
                self._show_snackbar("لا يمكن تعديل عملية معكوسة. استخدم إنشاء عملية جديدة.", True)
                return
            dialog = ThirdPartyPaymentDialog(page=self._page, on_save=lambda _: self._reload(), payment=payment)
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"خطأ في فتح تعديل العملية: {str(ex)}", True)

    def _reverse_third_party(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لعكس العملية", True)
            return

        def confirm(e):
            try:
                from database import ThirdPartyPaymentRepository
                repo = ThirdPartyPaymentRepository()
                repo.reverse_payment_on_behalf(ref, UserSession.get_current().get('id') if UserSession.get_current() else None)
                self._show_snackbar("تم عكس عملية السداد بالنيابة", False)
                self._reload()
            except Exception as ex:
                self._show_snackbar(f"خطأ: {str(ex)}", True)
            self._close_dialog(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("عكس سداد بالنيابة"),
            content=ft.Text(f"سيتم إنشاء قيود عكسية للعملية {ref}. هل تريد المتابعة؟"),
            actions=[ft.TextButton("نعم", on_click=confirm), ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)


    def _edit_service_case(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لتعديل ملف الخدمة", True)
            return
        try:
            from database import ServiceCaseRepository
            from views.dialogs.service_case_dialog import ServiceCaseDialog
            service_case = ServiceCaseRepository().get_by_reference(ref)
            if service_case.get('status') == 'reversed':
                self._show_snackbar("لا يمكن تعديل ملف خدمة معكوس. أنشئ ملف خدمة جديداً.", True)
                return
            dialog = ServiceCaseDialog(page=self._page, on_save=lambda _: self._reload(), service_case=service_case)
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"خطأ في فتح تعديل ملف الخدمة: {str(ex)}", True)

    def _reverse_service_case(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لعكس ملف الخدمة", True)
            return
        reason_field = ft.TextField(label="سبب العكس", multiline=True, min_lines=2, max_lines=3, hint_text="مثال: إلغاء الخدمة أو تصحيح عملية مدخلة بالخطأ")

        def confirm(e):
            reason = str(reason_field.value or '').strip()
            if not reason:
                self._show_snackbar("سبب عكس ملف الخدمة مطلوب", True)
                return
            try:
                from database import ServiceCaseRepository
                repo = ServiceCaseRepository()
                repo.reverse(ref, reason=reason)
                self._show_snackbar("تم عكس ملف الخدمة وإخفاء أثره من الحسابات والتقارير", False)
                self._reload()
                self._close_dialog(dlg)
            except Exception as ex:
                self._show_snackbar(f"خطأ: {str(ex)}", True)

        dlg = ft.AlertDialog(
            title=ft.Text("عكس ملف خدمة"),
            content=ft.Column([
                ft.Text(
                    f"سيتم إنشاء قيود عكسية لملف الخدمة {ref}. "
                    "سيختفي القيد الأصلي والعكسي من حسابات الشركات والطباعة والتقارير التشغيلية، "
                    "مع بقائهما في سجل التدقيق."
                ),
                reason_field,
            ], tight=True, spacing=10),
            actions=[ft.TextButton("عكس", on_click=confirm), ft.TextButton("إلغاء", on_click=lambda e: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)


    def _edit_direct_service(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لتعديل الخدمة المباشرة", True)
            return
        try:
            from database import DirectServiceRepository
            from views.dialogs.direct_service_dialog import DirectServiceDialog
            service = DirectServiceRepository().get_by_reference(ref)
            if service.get('status') == 'reversed':
                self._show_snackbar("لا يمكن تعديل خدمة مباشرة معكوسة. أنشئ خدمة جديدة.", True)
                return
            dialog = DirectServiceDialog(page=self._page, on_save=lambda _: self._reload(), service=service)
            open_control(self._page, dialog)
        except Exception as ex:
            self._show_snackbar(f"خطأ في فتح تعديل الخدمة المباشرة: {str(ex)}", True)

    def _reverse_direct_service(self, record):
        ref = record.get('source_ref') or ''
        if not ref:
            self._show_snackbar("لا يوجد مرجع لعكس الخدمة المباشرة", True)
            return
        reason_field = ft.TextField(label="سبب العكس", multiline=True, min_lines=2, max_lines=3, hint_text="مثال: إلغاء الخدمة أو تصحيح عملية مدخلة بالخطأ")

        def confirm(e):
            reason = str(reason_field.value or '').strip()
            if not reason:
                self._show_snackbar("سبب عكس الخدمة المباشرة مطلوب", True)
                return
            try:
                from database import DirectServiceRepository
                repo = DirectServiceRepository()
                repo.reverse(ref, UserSession.get_current().get('id') if UserSession.get_current() else None, reason=reason)
                self._show_snackbar("تم عكس الخدمة السريعة وإخفاء أثرها من الحسابات والتقارير", False)
                self._reload()
                self._close_dialog(dlg)
            except Exception as ex:
                self._show_snackbar(f"خطأ: {str(ex)}", True)

        dlg = ft.AlertDialog(
            title=ft.Text("عكس خدمة سريعة / مباشرة"),
            content=ft.Column([
                ft.Text(
                    f"سيتم إنشاء قيود عكسية للخدمة {ref}. "
                    "سيختفي القيد الأصلي والعكسي من حسابات الشركات والطباعة والتقارير التشغيلية، "
                    "مع بقائهما في سجل التدقيق."
                ),
                reason_field,
            ], tight=True, spacing=10),
            actions=[ft.TextButton("عكس", on_click=confirm), ft.TextButton("إلغاء", on_click=lambda e: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)

    def _reload(self):
        try:
            repo = ExpenseRepository()
            self._all_records = sorted(repo.get_by_company(self.company_name, convert_to_display=False), key=lambda x: x['date'])
            self._visible_limit = self._page_size
            persons = sorted({str(r.get('person_name') or '').strip() for r in self._all_records if str(r.get('person_name') or '').strip()})
            self.person_filter.options = [ft.dropdown.Option("الكل")] + [ft.dropdown.Option(name) for name in persons]
            if self.person_filter.value not in (["الكل"] + persons):
                self.person_filter.value = "الكل"
            self._load_data()
            if self.on_changed:
                self.on_changed()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
