# -*- coding: utf-8 -*-
"""Mobile reporting center view."""
from __future__ import annotations

from typing import Dict, List

import flet as ft

from currency import currency
from reports.reporting_center import (
    PERIOD_ALL,
    PERIOD_CUSTOM,
    PERIOD_LAST_MONTH,
    PERIOD_THIS_MONTH,
    PERIOD_THIS_YEAR,
    PERIOD_TODAY,
    PERIOD_YESTERDAY,
    REPORT_AGING,
    REPORT_AUDIT,
    REPORT_OPEN_SERVICES,
    REPORT_LOW_MARGIN,
    REPORT_LOCKED_ENTRIES,
    REPORT_REVERSALS,
    REPORT_OPERATION_SUMMARY,
    REPORT_COMPANY_BALANCES,
    REPORT_DEFINITIONS,
    REPORT_PROFIT,
    REPORT_DIRECT_SERVICES,
    REPORT_SERVICES,
    REPORT_THIRD_PARTY,
    ReportingCenterService,
    export_report_csv,
    export_report_html,
)
from reports.image_export import export_report_image
from services.file_export_service import FileExportService
from views.flet_compat import run_async_task
from views.financial_date_field import FinancialDateField, today_iso
from views.searchable_field import SearchableTextField
from views.ui_kit import (
    BORDER,
    CARD_BG,
    DANGER,
    MUTED,
    PAGE_BG,
    PRIMARY,
    PRIMARY_SOFT,
    SUCCESS,
    TEXT,
    WARNING,
    data_card,
    empty_state,
    info_banner,
    money_text,
    page_header,
    pill,
    primary_button,
    show_snackbar,
    stat_card,
)


_PERIOD_OPTIONS = [
    (PERIOD_TODAY, "اليوم"),
    (PERIOD_YESTERDAY, "أمس"),
    (PERIOD_THIS_MONTH, "الشهر الحالي"),
    (PERIOD_LAST_MONTH, "الشهر السابق"),
    (PERIOD_THIS_YEAR, "السنة الحالية"),
    (PERIOD_CUSTOM, "مخصص"),
    (PERIOD_ALL, "كل الفترات"),
]

_REPORT_ORDER = [
    REPORT_COMPANY_BALANCES,
    REPORT_AGING,
    REPORT_PROFIT,
    REPORT_DIRECT_SERVICES,
    REPORT_SERVICES,
    REPORT_THIRD_PARTY,
    REPORT_AUDIT,
    REPORT_OPEN_SERVICES,
    REPORT_LOW_MARGIN,
    REPORT_LOCKED_ENTRIES,
    REPORT_REVERSALS,
    REPORT_OPERATION_SUMMARY,
]


class ReportsCenterMobileView(ft.Column):
    """A unified preview/export surface for accounting and operational reports."""

    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO
        self._service = ReportingCenterService()
        self._current_report = None

        self.report_dropdown = ft.Dropdown(
            label="التقرير",
            value=REPORT_COMPANY_BALANCES,
            options=[ft.dropdown.Option(key, f"{REPORT_DEFINITIONS[key]['category']} — {REPORT_DEFINITIONS[key]['title']}") for key in _REPORT_ORDER],
            on_change=self._on_filter_changed,
            border_radius=16,
            filled=True,
            bgcolor=CARD_BG,
            border_color=BORDER,
            focused_border_color=PRIMARY,
        )
        self.period_dropdown = ft.Dropdown(
            label="الفترة",
            value=PERIOD_THIS_MONTH,
            options=[ft.dropdown.Option(k, v) for k, v in _PERIOD_OPTIONS],
            on_change=self._on_period_changed,
            width=190,
            border_radius=16,
            filled=True,
            bgcolor=CARD_BG,
            border_color=BORDER,
            focused_border_color=PRIMARY,
        )
        self.company_dropdown = SearchableTextField(
            label="الشركة",
            value="الكل",
            width=220,
            hint_text="الكل أو ابحث عن شركة",
            suggestions_provider=lambda: ["الكل"] + self._company_suggestions,
            on_change=self._on_filter_changed,
        )
        self._company_suggestions = []
        self.currency_dropdown = ft.Dropdown(
            label="العملة الأصلية",
            value="الكل",
            options=[ft.dropdown.Option("الكل", "كل العملات")] + [ft.dropdown.Option(c, c) for c in currency.SUPPORTED_CURRENCIES],
            on_change=self._on_filter_changed,
            width=170,
            border_radius=16,
            filled=True,
            bgcolor=CARD_BG,
            border_color=BORDER,
            focused_border_color=PRIMARY,
        )
        self.detail_dropdown = ft.Dropdown(
            label="العرض",
            value="summary",
            options=[ft.dropdown.Option("summary", "مختصر"), ft.dropdown.Option("detail", "تفصيلي")],
            on_change=self._on_filter_changed,
            width=145,
            border_radius=16,
            filled=True,
            bgcolor=CARD_BG,
            border_color=BORDER,
            focused_border_color=PRIMARY,
        )
        self.start_date = FinancialDateField(page, label="من تاريخ", width=160, include_quick_buttons=False, use_last_date=False)
        self.end_date = FinancialDateField(page, label="إلى تاريخ", value=today_iso(), width=160, include_quick_buttons=False, use_last_date=False)
        self.custom_dates = ft.Container(
            content=ft.Row([self.start_date, self.end_date], spacing=8, wrap=True),
            visible=False,
            padding=ft.Padding(left=10, right=10, top=0, bottom=0),
        )

        self.summary_container = ft.Column(spacing=6)
        self.preview_container = ft.Column(spacing=8)
        self.status_banner = ft.Container(visible=False)

        self.controls = [
            page_header("مركز التقارير", icon=ft.Icons.INSIGHTS, subtitle="تقارير مالية وتشغيلية موحّدة بنفس هوية هوى الشام"),
            ft.Container(
                content=ft.Column([
                    ft.Row([self.report_dropdown], spacing=8),
                    ft.Row([self.period_dropdown, self.company_dropdown, self.currency_dropdown, self.detail_dropdown], spacing=8, run_spacing=8, wrap=True),
                ], spacing=8),
                padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            ),
            self.custom_dates,
            ft.Container(
                content=ft.Row([
                    primary_button("عرض", ft.Icons.VISIBILITY, self._on_view_report),
                    ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.PRINT, color=PRIMARY), ft.Text("HTML", color=PRIMARY, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._on_export_html),
                    ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.IMAGE, color=PRIMARY), ft.Text("PNG", color=PRIMARY, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._export_png_async),
                    ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.TABLE_VIEW, color=PRIMARY), ft.Text("CSV", color=PRIMARY, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._on_export_csv),
                    ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.SHARE, color=PRIMARY), ft.Text("مشاركة", color=PRIMARY, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._on_share_html),
                ], spacing=8, run_spacing=8, wrap=True),
                padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            ),
            self.status_banner,
            self.summary_container,
            self.preview_container,
        ]
        self._load_companies()
        self._render_report()

    def _show_snackbar(self, message: str, is_error: bool = False):
        show_snackbar(self._page, message, is_error=is_error)

    def _load_companies(self):
        try:
            self._company_suggestions = list(self._service.list_companies() or [])
        except Exception:
            # Reporting must still open even if company loading fails; the view
            # button will surface the detailed error.
            self._company_suggestions = []

    def _on_period_changed(self, e=None):
        self.custom_dates.visible = self.period_dropdown.value == PERIOD_CUSTOM
        self._render_report()

    def _on_filter_changed(self, e=None):
        self._render_report()

    def _filters(self) -> Dict[str, object]:
        return {
            "report_id": self.report_dropdown.value or REPORT_COMPANY_BALANCES,
            "period": self.period_dropdown.value or PERIOD_THIS_MONTH,
            "start_date": self.start_date.value if self.period_dropdown.value == PERIOD_CUSTOM else None,
            "end_date": self.end_date.value if self.period_dropdown.value == PERIOD_CUSTOM else None,
            "company_name": None if not str(self.company_dropdown.value or "").strip() or self.company_dropdown.value == "الكل" else self.company_dropdown.value,
            "currency_code": None if self.currency_dropdown.value == "الكل" else self.currency_dropdown.value,
            "detail_mode": self.detail_dropdown.value or "summary",
        }

    def _render_report(self):
        try:
            f = self._filters()
            report = self._service.build_report(**f)
            self._current_report = report
            self.status_banner.visible = True
            self.status_banner.content = info_banner(
                f"{report.category} · {report.period_label} · العملة المعروضة: {report.display_currency}",
                icon=ft.Icons.FILTER_ALT,
                color=PRIMARY,
                bgcolor=PRIMARY_SOFT,
            )
            self.summary_container.controls = self._summary_cards(report)
            self.preview_container.controls = self._preview_cards(report)
        except Exception as ex:
            self._current_report = None
            self.summary_container.controls = []
            self.preview_container.controls = [empty_state("تعذر إنشاء التقرير", str(ex), icon=ft.Icons.ERROR_OUTLINE)]
        try:
            self._page.update()
        except Exception:
            pass

    def _summary_cards(self, report):
        if not report.summary:
            return []
        controls = []
        color_map = {"debit": SUCCESS, "credit": DANGER, "balance": PRIMARY}
        for item in report.summary[:8]:
            cls = str(item.get("class") or "balance")
            controls.append(stat_card(str(item.get("label") or ""), str(item.get("value") or ""), color=color_map.get(cls, PRIMARY), icon=ft.Icons.QUERY_STATS))
        return controls

    def _row_primary_value(self, report, row: Dict[str, object]) -> str:
        for key in ("company", "reference", "client", "payer", "username", "service", "operation", "risk"):
            if row.get(key):
                return str(row.get(key))
        first = report.columns[0]["key"] if report.columns else ""
        return str(row.get(first) or "حركة")

    def _preview_cards(self, report):
        if not report.rows:
            return [empty_state("لا توجد بيانات", "غيّر الفترة أو الشركة أو العملة", icon=ft.Icons.FACT_CHECK_OUTLINED)]
        controls = [ft.Container(content=ft.Row([ft.Icon(ft.Icons.TABLE_CHART, color=PRIMARY), ft.Text(f"{report.title} — {len(report.rows)} صف", size=15, weight=ft.FontWeight.BOLD, color=TEXT, expand=True)], spacing=6), padding=ft.Padding(left=12, right=12, top=8, bottom=0))]
        limit = 60 if self.detail_dropdown.value == "detail" else 25
        for row in report.rows[:limit]:
            details = []
            for col in report.columns[:9]:
                key = col.get("key")
                if key in {"company", "reference", "client", "payer", "username", "operation", "risk"}:
                    continue
                value = row.get(str(key), "")
                if value in (None, ""):
                    continue
                details.append(ft.Text(f"{col.get('label')}: {value}", size=11, color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS))
            controls.append(
                data_card(
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.DESCRIPTION, color=PRIMARY, size=20),
                            ft.Text(self._row_primary_value(report, row), size=14, weight=ft.FontWeight.BOLD, color=TEXT, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            pill(str(row.get("date") or row.get("timestamp") or ""), color=PRIMARY, bgcolor=PRIMARY_SOFT, size=10) if (row.get("date") or row.get("timestamp")) else ft.Container(width=0, height=0),
                        ], spacing=6),
                        ft.Column(details, spacing=2) if details else ft.Text("—", color=MUTED, size=11),
                    ], spacing=7),
                    padding=13,
                    elevation=1,
                )
            )
        if len(report.rows) > limit:
            controls.append(info_banner(f"يتم عرض أول {limit} صف فقط داخل التطبيق. التصدير يحتوي كل الصفوف.", icon=ft.Icons.INFO_OUTLINE, color=WARNING, bgcolor="#FFF7E3"))
        return controls

    def _on_view_report(self, e=None):
        self._render_report()

    def _require_report(self):
        if self._current_report is None:
            self._render_report()
        if self._current_report is None:
            raise ValueError("لا يوجد تقرير جاهز للتصدير")
        return self._current_report

    async def _open_path(self, path: str, title: str):
        result = await FileExportService.open_file_async(self._page, path, title=title)
        self._show_snackbar(result.message if result.ok else result.message or path, is_error=not result.ok)

    async def _share_path(self, path: str, title: str):
        result = await FileExportService.share_file_async(self._page, path, f"{title} من نظام هوى الشام", open_whatsapp=False, title=title)
        self._show_snackbar(result.message if result.ok else result.message or path, is_error=not result.ok)

    def _on_export_html(self, e=None):
        try:
            report = self._require_report()
            path = export_report_html(report)
            run_async_task(self._page, self._open_path, path, report.title)
        except Exception as ex:
            self._show_snackbar(f"تعذر إنشاء HTML: {ex}", True)


    async def _export_png_async(self, e=None):
        try:
            import asyncio
            report = self._require_report()
            self._show_snackbar("جارٍ إنشاء صورة PNG للتقرير...", False)
            path = await asyncio.to_thread(lambda: export_report_image(report, max_rows=40))
            await self._open_path(path, f"PNG — {report.title}")
        except Exception as ex:
            self._show_snackbar(f"تعذر إنشاء PNG: {ex}", True)

    def _on_export_csv(self, e=None):
        try:
            report = self._require_report()
            path = export_report_csv(report)
            run_async_task(self._page, self._open_path, path, f"CSV — {report.title}")
        except Exception as ex:
            self._show_snackbar(f"تعذر إنشاء CSV: {ex}", True)

    def _on_share_html(self, e=None):
        try:
            report = self._require_report()
            path = export_report_html(report)
            run_async_task(self._page, self._share_path, path, report.title)
        except Exception as ex:
            self._show_snackbar(f"تعذر مشاركة التقرير: {ex}", True)
