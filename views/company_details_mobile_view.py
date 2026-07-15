# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, run_async_task
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from views.ui_kit import show_snackbar, empty_state, data_card, action_text_button, amount_pill, key_value_tile, pill, summary_bar, metric_tile, info_banner, PRIMARY, PRIMARY_SOFT, SUCCESS, DANGER, WARNING
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
        self.records = repo.get_by_company(company_name, convert_to_display=False)
        self.records = sorted(self.records, key=lambda x: x['date'])
        if normalize_search_text(self.search_query):
            filtered = [r for r in self.records if enrich_expense_match(r, self.search_query)]
            # If the query matched only the company name, every row may be valid;
            # keep all rows in that case so the user can still inspect the account.
            if filtered:
                self.records = filtered
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
        self.records_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        self.report_actions = ft.Row([
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_ALT), ft.Text("خدمة مباشرة")], tight=True),
                on_click=self._add_direct_service,
                bgcolor=WARNING,
                color=ft.Colors.WHITE,
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.PRINT), ft.Text("كشف للطباعة")], tight=True),
                on_click=self._export_printable_statement,
                bgcolor=PRIMARY,
                color=ft.Colors.WHITE,
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.FACT_CHECK), ft.Text("كشف مطابقة")], tight=True),
                on_click=self._export_reconciliation_statement,
                bgcolor=PRIMARY,
                color=ft.Colors.WHITE,
            ),
            ft.FilledButton(
                content=ft.Row([ft.Icon(ft.Icons.SHARE), ft.Text("مشاركة")], tight=True),
                on_click=self._share_statement,
                bgcolor=SUCCESS,
                color=ft.Colors.WHITE,
            ),
            ft.TextButton(
                content=ft.Row([ft.Icon(ft.Icons.IMAGE), ft.Text("صورة")], tight=True),
                on_click=self._on_share_statement_image,
            ),
            ft.TextButton(
                content=ft.Row([ft.Icon(ft.Icons.CHAT), ft.Text("واتساب")], tight=True),
                on_click=self._share_statement_whatsapp,
            ),
            ft.TextButton(
                content=ft.Row([ft.Icon(ft.Icons.TABLE_VIEW), ft.Text("CSV")], tight=True),
                on_click=self._export_csv_statement,
            ),
        ], spacing=8, wrap=True)
        search_banner = info_banner(
            f"نتائج داخل {company_name} عن: {self.search_query}",
            icon=ft.Icons.MANAGE_SEARCH,
            color=PRIMARY,
            bgcolor=PRIMARY_SOFT,
        ) if normalize_search_text(self.search_query) else ft.Container(width=0, height=0)
        self.controls = [self.summary_panel, search_banner, self.report_actions, self.people_summary, ft.Divider(height=1), self.records_list]
        self._load_data()

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)


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

    def _load_data(self):
        display_curr = currency.get_display_currency()
        approved_records = [r for r in self.records if r.get('status', 'approved') != 'waiting_payment']
        waiting_count = len([r for r in self.records if r.get('status') == 'waiting_payment'])
        total_in_usd = sum(float(r['amount']) for r in approved_records if r['type'] == 'incoming')
        total_out_usd = sum(float(r['amount']) for r in approved_records if r['type'] == 'outgoing')
        net_usd = total_in_usd - total_out_usd
        total_in = currency.convert(total_in_usd, 'USD', display_curr)
        total_out = currency.convert(total_out_usd, 'USD', display_curr)
        net = currency.convert(net_usd, 'USD', display_curr)

        self.summary_text.value = f"📥 {currency.format_amount(total_in, display_curr)}   📤 {currency.format_amount(total_out, display_curr)}   💰 {currency.format_amount(net, display_curr)}   ⏳ {waiting_count}"
        self.total_in_text.value = currency.format_amount(total_in, display_curr)
        self.total_out_text.value = currency.format_amount(total_out, display_curr)
        self.net_text.value = currency.format_amount(net, display_curr)
        self.net_text.color = SUCCESS if net_usd >= 0 else DANGER
        self.waiting_text.value = str(waiting_count)

        person_buckets = {}
        for rr in self.records:
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
                chips.append(pill(f"{person}: {currency.format_amount(net_p, display_curr)} · {item['count']} قيد", color=PRIMARY, bgcolor=PRIMARY_SOFT))
            self.people_summary.controls = chips
            self.people_summary.visible = True
        else:
            self.people_summary.controls = []
            self.people_summary.visible = False

        cards = []
        running_usd = 0.0
        is_viewer = UserSession.get_current() and UserSession.get_current().get('role') == 'viewer'

        for idx, r in enumerate(self.records, 1):
            amount_str = currency.format_amount(float(r.get('amount_original') or 0), r.get('currency_original') or display_curr)
            is_waiting = r.get('status') == 'waiting_payment'
            if r['type'] == 'incoming':
                inc_out = amount_str
                out_txt = "—"
                if not is_waiting:
                    running_usd += float(r['amount'])
                amount_color = WARNING if is_waiting else SUCCESS
                icon = ft.Icons.PAYMENTS if is_waiting else ft.Icons.ARROW_DOWNWARD
                amount_label = "بانتظار الدفع" if is_waiting else "لنا"
            else:
                inc_out = "—"
                out_txt = amount_str
                if not is_waiting:
                    running_usd -= float(r['amount'])
                amount_color = WARNING if is_waiting else DANGER
                icon = ft.Icons.PAYMENTS if is_waiting else ft.Icons.ARROW_UPWARD
                amount_label = "بانتظار الدفع" if is_waiting else "له"

            running_display = currency.convert(running_usd, 'USD', display_curr)
            running_str = currency.format_amount(running_display, display_curr)
            running_color = SUCCESS if running_usd >= 0 else DANGER

            card = data_card(
                ft.Column([
                    ft.Row([
                        pill(f"#{idx}", color=ft.Colors.GREY_700, bgcolor=ft.Colors.GREY_100),
                        ft.Text(r['date'], size=12, color=ft.Colors.GREY_600, expand=True),
                        ft.Icon(icon, color=amount_color, size=18),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        key_value_tile(amount_label, amount_str, amount_color),
                        key_value_tile("تراكمي", running_str, running_color),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    pill(
                        f"⏳ تنبيه الدفع: {r.get('payment_due_date') or 'غير محدد'}",
                        color=WARNING,
                        bgcolor="#FFF7E3",
                    ) if is_waiting else ft.Container(width=0, height=0),
                    ft.Row([
                        pill(f"👤 {r.get('person_name')}", color=PRIMARY, bgcolor=PRIMARY_SOFT) if (r.get('person_name') or '').strip() else ft.Container(width=0, height=0),
                        pill(f"🧾 {r.get('service_type') or 'غير محدد'}", color=ft.Colors.GREY_800, bgcolor=ft.Colors.GREY_100),
                        pill(f"⚙️ {operation_label(r.get('operation_type'))}", color=PRIMARY, bgcolor=PRIMARY_SOFT),
                    ], spacing=5, wrap=True),
                    ft.Text(r['notes'] or '', size=12, color=ft.Colors.GREY_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    self._match_chip(r) if normalize_search_text(self.search_query) else ft.Container(width=0, height=0),
                    pill(
                        "🔁 سداد بالنيابة" if r.get('source_type') == 'third_party_payment' else "↩️ عكس سداد بالنيابة",
                        color=PRIMARY if r.get('source_type') == 'third_party_payment' else WARNING,
                        bgcolor=PRIMARY_SOFT if r.get('source_type') == 'third_party_payment' else "#FFF7E3",
                    ) if r.get('source_type') in ('third_party_payment', 'third_party_payment_reversal') else ft.Container(width=0, height=0),
                    pill(
                        '🧭 ملف خدمة - عميل' if r.get('source_type') == 'service_case_client' else ('🧭 ملف خدمة - مورد' if r.get('source_type') == 'service_case_supplier' else '↩️ عكس ملف خدمة'),
                        color=PRIMARY,
                        bgcolor=PRIMARY_SOFT,
                    ) if r.get('source_type') in ('service_case_client', 'service_case_supplier', 'service_case_reversal') else ft.Container(width=0, height=0),
                    pill(
                        '💼 خدمة مباشرة - عميل' if r.get('source_type') == 'direct_service_client' else ('💼 خدمة مباشرة - مورد' if r.get('source_type') == 'direct_service_supplier' else '↩️ عكس خدمة مباشرة'),
                        color=PRIMARY,
                        bgcolor=PRIMARY_SOFT,
                    ) if r.get('source_type') in ('direct_service_client', 'direct_service_supplier', 'direct_service_reversal') else ft.Container(width=0, height=0),
                    ft.Row([
                        action_text_button("تعديل", ft.Icons.EDIT, lambda e, rec=r: self._edit_record(rec), color=PRIMARY, visible=(not is_viewer and not r.get('source_type') and not int(r.get('is_locked') or 0))),
                        action_text_button("حذف", ft.Icons.DELETE, lambda e, rec=r: self._delete_record(rec), color=DANGER, visible=(not is_viewer and not r.get('source_type') and not int(r.get('is_locked') or 0))),
                        action_text_button("تعديل العملية", ft.Icons.EDIT_NOTE, lambda e, rec=r: self._edit_third_party(rec), color=PRIMARY, visible=(not is_viewer and r.get('source_type') == 'third_party_payment')),
                        action_text_button("عكس", ft.Icons.UNDO, lambda e, rec=r: self._reverse_third_party(rec), color=WARNING, visible=(not is_viewer and r.get('source_type') == 'third_party_payment')),
                    ], alignment=ft.MainAxisAlignment.END)
                ], spacing=8),
                padding=12,
                elevation=1,
                margin=ft.Margin(left=5, right=5, top=5, bottom=5),
            )
            cards.append(card)

        if not cards:
            cards.append(empty_state("لا توجد قيود", icon=ft.Icons.RECEIPT_LONG, padding=30))

        self.records_list.controls = cards
        self._page.update()


    def _add_direct_service(self, e=None):
        if UserSession.get_current() and UserSession.get_current().get('role') == 'viewer':
            self._show_snackbar("ليس لديك صلاحية لإضافة خدمات مباشرة", True)
            return
        from views.dialogs.direct_service_dialog import DirectServiceDialog
        dialog = DirectServiceDialog(page=self._page, on_save=lambda _: self._reload(), company_name=self.company_name)
        open_control(self._page, dialog)

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


    def _on_share_statement_image(self, e=None):
        self._show_snackbar("جارٍ إنشاء صورة كشف المطابقة...", False)
        run_async_task(self._page, self._share_statement_image_async)

    async def _share_statement_image_async(self):
        try:
            import asyncio
            from reports.image_export import export_statement_image
            from reports.share import share_file_async
            path = await asyncio.to_thread(lambda: export_statement_image(self.company_name, self.records, reconciliation=True))
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

    def _reload(self):
        try:
            repo = ExpenseRepository()
            self.records = repo.get_by_company(self.company_name, convert_to_display=False)
            self.records = sorted(self.records, key=lambda x: x['date'])
            if normalize_search_text(self.search_query):
                filtered = [r for r in self.records if enrich_expense_match(r, self.search_query)]
                if filtered:
                    self.records = filtered
            self._load_data()
            if self.on_changed:
                self.on_changed()
        except Exception as ex:
            self._show_snackbar(f"خطأ: {str(ex)}", True)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
