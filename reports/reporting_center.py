# -*- coding: utf-8 -*-
"""Professional reporting center core.

This module keeps report calculations independent from Flet widgets.  The same
report definitions feed the mobile preview, HTML print/share output and CSV
exports so financial totals do not diverge between screens.
"""
from __future__ import annotations

import csv
import datetime as _dt
import html
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from config import get_company_info
from currency import currency
from database import AuditRepository, ExpenseRepository, ServiceCaseRepository
from reports.account_statement import _base_css, _header_html, _ltr, _money_span, _safe
from services.file_export_service import FileExportService
from services.ledger_operation_service import operation_label

PERIOD_ALL = "all"
PERIOD_TODAY = "today"
PERIOD_YESTERDAY = "yesterday"
PERIOD_THIS_MONTH = "this_month"
PERIOD_LAST_MONTH = "last_month"
PERIOD_THIS_YEAR = "this_year"
PERIOD_CUSTOM = "custom"

REPORT_COMPANY_BALANCES = "company_balances"
REPORT_AGING = "aging_receivables"
REPORT_PROFIT = "period_profit"
REPORT_SERVICES = "services_period"
REPORT_THIRD_PARTY = "third_party_payments"
REPORT_AUDIT = "audit_activity"
REPORT_OPEN_SERVICES = "open_services"
REPORT_LOW_MARGIN = "low_margin_services"
REPORT_LOCKED_ENTRIES = "locked_entries"
REPORT_REVERSALS = "reversal_operations"
REPORT_OPERATION_SUMMARY = "operation_summary"

REPORT_DEFINITIONS: Dict[str, Dict[str, str]] = {
    REPORT_COMPANY_BALANCES: {"title": "تقرير أرصدة الشركات", "category": "تقارير مالية", "icon": "account_balance"},
    REPORT_AGING: {"title": "تقرير أعمار الذمم", "category": "تقارير مالية", "icon": "hourglass_bottom"},
    REPORT_PROFIT: {"title": "تقرير أرباح الفترة", "category": "تقارير الأرباح", "icon": "trending_up"},
    REPORT_SERVICES: {"title": "تقرير الخدمات حسب الفترة", "category": "تقارير الخدمات", "icon": "travel_explore"},
    REPORT_THIRD_PARTY: {"title": "تقرير سدد عني", "category": "تقارير السداد", "icon": "swap_horiz"},
    REPORT_AUDIT: {"title": "تقرير نشاط المستخدمين", "category": "تقارير التدقيق", "icon": "assignment"},
    REPORT_OPEN_SERVICES: {"title": "تقرير الخدمات المفتوحة", "category": "تقارير الخدمات", "icon": "pending_actions"},
    REPORT_LOW_MARGIN: {"title": "تقرير الخدمات منخفضة الربح", "category": "تقارير الأرباح", "icon": "warning"},
    REPORT_LOCKED_ENTRIES: {"title": "تقرير القيود المقفلة", "category": "تقارير التدقيق", "icon": "lock"},
    REPORT_REVERSALS: {"title": "تقرير العمليات المعكوسة", "category": "تقارير التدقيق", "icon": "undo"},
    REPORT_OPERATION_SUMMARY: {"title": "ملخص أنواع العمليات", "category": "تقارير مالية", "icon": "donut_large"},
}


def today_iso() -> str:
    return _dt.date.today().strftime("%Y-%m-%d")


def _parse_iso(value: object) -> _dt.date | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return _dt.datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def resolve_period(period: str = PERIOD_THIS_MONTH, start_date: str | None = None, end_date: str | None = None) -> Tuple[str | None, str | None, str]:
    """Return inclusive YYYY-MM-DD start/end and an Arabic label."""
    period = str(period or PERIOD_THIS_MONTH).strip()
    today = _dt.date.today()
    if period == PERIOD_ALL:
        return None, None, "كل الفترات"
    if period == PERIOD_TODAY:
        d = today.strftime("%Y-%m-%d")
        return d, d, "اليوم"
    if period == PERIOD_YESTERDAY:
        d = (today - _dt.timedelta(days=1)).strftime("%Y-%m-%d")
        return d, d, "أمس"
    if period == PERIOD_THIS_YEAR:
        return f"{today.year}-01-01", f"{today.year}-12-31", "السنة الحالية"
    if period == PERIOD_LAST_MONTH:
        first_this_month = today.replace(day=1)
        last_prev = first_this_month - _dt.timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d"), "الشهر السابق"
    if period == PERIOD_CUSTOM:
        s = str(start_date or "").strip() or None
        e = str(end_date or "").strip() or None
        label = f"من {s or 'البداية'} إلى {e or 'النهاية'}"
        return s, e, label
    first = today.replace(day=1)
    # compute last day of this month without calendar dependency
    next_month = (first.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
    last = next_month - _dt.timedelta(days=1)
    return first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d"), "الشهر الحالي"


def _in_range(date_value: object, start: str | None, end: str | None) -> bool:
    text = str(date_value or "")[:10]
    if start and text < start:
        return False
    if end and text > end:
        return False
    return True


def _amount_base(row: Dict) -> float:
    try:
        value = row.get("amount_base")
        if value in (None, ""):
            value = row.get("amount")
        return float(value or 0)
    except Exception:
        return 0.0


def _original_currency(row: Dict) -> str:
    return str(row.get("currency_original") or row.get("currency") or "USD").upper()


def _original_amount(row: Dict) -> float:
    try:
        return float(row.get("amount_original") if row.get("amount_original") not in (None, "") else row.get("amount") or 0)
    except Exception:
        return 0.0


def _fmt_usd_to_display(value_usd: float, display_currency: str | None = None) -> str:
    display_currency = display_currency or currency.get_display_currency()
    return currency.format_amount_full(currency.convert(float(value_usd or 0), "USD", display_currency), display_currency)


def _fmt_original(value: float, code: str) -> str:
    return currency.format_amount_full(float(value or 0), code or "USD")


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name or "report")).strip("._ ") or "report"


@dataclass
class ReportResult:
    report_id: str
    title: str
    category: str
    period_label: str
    generated_at: str
    display_currency: str
    columns: List[Dict[str, str]]
    rows: List[Dict[str, object]]
    summary: List[Dict[str, str]]
    filename_slug: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "report_id": self.report_id,
            "title": self.title,
            "category": self.category,
            "period_label": self.period_label,
            "generated_at": self.generated_at,
            "display_currency": self.display_currency,
            "columns": self.columns,
            "rows": self.rows,
            "summary": self.summary,
            "filename_slug": self.filename_slug,
        }


class ReportingCenterService:
    """Single source of truth for management reports."""

    def __init__(self):
        self.expense_repo = ExpenseRepository()
        self.service_repo = ServiceCaseRepository()
        self.audit_repo = AuditRepository()

    def list_companies(self) -> List[str]:
        names = {str(r.get("company_name") or "").strip() for r in self.expense_repo.get_all(convert_to_display=False)}
        return sorted(n for n in names if n)

    def _filtered_expenses(self, *, period: str = PERIOD_THIS_MONTH, start_date: str | None = None, end_date: str | None = None, company_name: str | None = None, currency_code: str | None = None, include_waiting: bool = False) -> Tuple[List[Dict], str, str | None, str | None]:
        start, end, label = resolve_period(period, start_date, end_date)
        company_name = str(company_name or "").strip()
        currency_code = str(currency_code or "").upper().strip()
        rows = []
        for r in self.expense_repo.get_all(convert_to_display=False):
            if not include_waiting and r.get("status", "approved") == "waiting_payment":
                continue
            if not _in_range(r.get("date"), start, end):
                continue
            if company_name and company_name != "الكل" and r.get("company_name") != company_name:
                continue
            if currency_code and currency_code != "الكل" and _original_currency(r) != currency_code:
                continue
            rows.append(r)
        return rows, label, start, end

    def build_report(self, report_id: str, *, period: str = PERIOD_THIS_MONTH, start_date: str | None = None, end_date: str | None = None, company_name: str | None = None, currency_code: str | None = None, detail_mode: str = "summary") -> ReportResult:
        if report_id == REPORT_COMPANY_BALANCES:
            return self.company_balances(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_AGING:
            return self.aging_receivables(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_PROFIT:
            return self.period_profit(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_SERVICES:
            return self.services_period(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_THIRD_PARTY:
            return self.third_party_payments(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_AUDIT:
            return self.audit_activity(period=period, start_date=start_date, end_date=end_date)
        if report_id == REPORT_OPEN_SERVICES:
            return self.open_services(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_LOW_MARGIN:
            return self.low_margin_services(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_LOCKED_ENTRIES:
            return self.locked_entries(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_REVERSALS:
            return self.reversal_operations(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        if report_id == REPORT_OPERATION_SUMMARY:
            return self.operation_summary(period=period, start_date=start_date, end_date=end_date, company_name=company_name, currency_code=currency_code)
        raise ValueError("تقرير غير معروف")

    def _result(self, report_id: str, period_label: str, columns: List[Dict[str, str]], rows: List[Dict[str, object]], summary: List[Dict[str, str]], slug_suffix: str = "") -> ReportResult:
        info = REPORT_DEFINITIONS[report_id]
        slug = report_id + (f"_{slug_suffix}" if slug_suffix else "")
        return ReportResult(
            report_id=report_id,
            title=info["title"],
            category=info["category"],
            period_label=period_label,
            generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            display_currency=currency.get_display_currency(),
            columns=columns,
            rows=rows,
            summary=summary,
            filename_slug=slug,
        )

    def company_balances(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(**filters)
        groups: Dict[str, Dict[str, object]] = defaultdict(lambda: {"incoming_usd": 0.0, "outgoing_usd": 0.0, "count": 0, "last_date": "", "persons": set(), "waiting": 0})
        # include waiting count independently but do not add to balance
        all_for_waiting, _, _, _ = self._filtered_expenses(include_waiting=True, **{k: v for k, v in filters.items() if k != "include_waiting"})
        for r in all_for_waiting:
            if r.get("status") == "waiting_payment":
                groups[str(r.get("company_name") or "")]["waiting"] = int(groups[str(r.get("company_name") or "")]["waiting"] or 0) + 1
        for r in expenses:
            company = str(r.get("company_name") or "").strip()
            if not company:
                continue
            item = groups[company]
            amount = _amount_base(r)
            if r.get("type") == "incoming":
                item["incoming_usd"] = float(item["incoming_usd"]) + amount
            else:
                item["outgoing_usd"] = float(item["outgoing_usd"]) + amount
            item["count"] = int(item["count"] or 0) + 1
            if str(r.get("date") or "") > str(item.get("last_date") or ""):
                item["last_date"] = str(r.get("date") or "")
            person = str(r.get("person_name") or "").strip()
            if person:
                item["persons"].add(person)

        display = currency.get_display_currency()
        rows = []
        total_in = total_out = 0.0
        for company, v in sorted(groups.items()):
            inc = float(v.get("incoming_usd") or 0)
            out = float(v.get("outgoing_usd") or 0)
            net = inc - out
            total_in += inc
            total_out += out
            rows.append({
                "company": company,
                "incoming": _fmt_usd_to_display(inc, display),
                "outgoing": _fmt_usd_to_display(out, display),
                "net": _fmt_usd_to_display(net, display),
                "side": "لصالح هوى الشام" if net > 0 else ("لصالح الشركة" if net < 0 else "مطابق"),
                "count": int(v.get("count") or 0),
                "persons": len(v.get("persons") or []),
                "waiting": int(v.get("waiting") or 0),
                "last_date": v.get("last_date") or "—",
            })
        columns = [
            {"key": "company", "label": "الشركة"}, {"key": "incoming", "label": "لنا"}, {"key": "outgoing", "label": "له"},
            {"key": "net", "label": "الصافي"}, {"key": "side", "label": "الاتجاه"}, {"key": "count", "label": "القيود"},
            {"key": "persons", "label": "الأشخاص"}, {"key": "waiting", "label": "انتظار"}, {"key": "last_date", "label": "آخر حركة"},
        ]
        summary = [
            {"label": "إجمالي لنا", "value": _fmt_usd_to_display(total_in, display), "class": "debit"},
            {"label": "إجمالي له", "value": _fmt_usd_to_display(total_out, display), "class": "credit"},
            {"label": "الصافي", "value": _fmt_usd_to_display(total_in - total_out, display), "class": "balance"},
            {"label": "عدد الشركات", "value": str(len(rows)), "class": "balance"},
        ]
        return self._result(REPORT_COMPANY_BALANCES, label, columns, rows, summary)

    def aging_receivables(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(**filters)
        grouped: Dict[str, Dict[str, object]] = defaultdict(lambda: {"net_usd": 0.0, "last_date": "", "count": 0})
        for r in expenses:
            company = str(r.get("company_name") or "").strip()
            if not company:
                continue
            amount = _amount_base(r)
            grouped[company]["net_usd"] = float(grouped[company]["net_usd"] or 0) + (amount if r.get("type") == "incoming" else -amount)
            grouped[company]["count"] = int(grouped[company]["count"] or 0) + 1
            if str(r.get("date") or "") > str(grouped[company].get("last_date") or ""):
                grouped[company]["last_date"] = str(r.get("date") or "")
        today = _dt.date.today()
        bucket_totals = defaultdict(float)
        rows = []
        for company, v in sorted(grouped.items()):
            net = float(v.get("net_usd") or 0)
            if abs(net) < 0.000001:
                continue
            last = _parse_iso(v.get("last_date")) or today
            age = max(0, (today - last).days)
            if age <= 7:
                bucket = "0 - 7 أيام"
            elif age <= 30:
                bucket = "8 - 30 يوم"
            elif age <= 60:
                bucket = "31 - 60 يوم"
            else:
                bucket = "أكثر من 60 يوم"
            bucket_totals[bucket] += net
            rows.append({
                "company": company,
                "last_date": v.get("last_date") or "—",
                "age_days": age,
                "bucket": bucket,
                "net": _fmt_usd_to_display(net),
                "side": "لنا" if net > 0 else "له",
                "count": int(v.get("count") or 0),
            })
        rows.sort(key=lambda x: (str(x.get("bucket")), -int(x.get("age_days") or 0), str(x.get("company"))))
        columns = [
            {"key": "company", "label": "الشركة"}, {"key": "last_date", "label": "آخر حركة"}, {"key": "age_days", "label": "العمر"},
            {"key": "bucket", "label": "الشريحة"}, {"key": "net", "label": "الرصيد"}, {"key": "side", "label": "الاتجاه"}, {"key": "count", "label": "القيود"},
        ]
        net_total = sum(bucket_totals.values())
        summary = [{"label": k, "value": _fmt_usd_to_display(bucket_totals.get(k, 0.0)), "class": "balance"} for k in ["0 - 7 أيام", "8 - 30 يوم", "31 - 60 يوم", "أكثر من 60 يوم"]]
        summary.insert(0, {"label": "الصافي", "value": _fmt_usd_to_display(net_total), "class": "balance"})
        return self._result(REPORT_AGING, label, columns, rows, summary)

    def _filtered_service_cases(self, *, period: str = PERIOD_THIS_MONTH, start_date: str | None = None, end_date: str | None = None, company_name: str | None = None, currency_code: str | None = None) -> Tuple[List[Dict], str]:
        start, end, label = resolve_period(period, start_date, end_date)
        company_name = str(company_name or "").strip()
        currency_code = str(currency_code or "").upper().strip()
        cases = []
        for c in self.service_repo.list_cases():
            if not _in_range(c.get("date"), start, end):
                continue
            if company_name and company_name != "الكل" and company_name not in {c.get("client_company_name"), c.get("supplier_company_name")}:
                # multi-component suppliers can also match
                component_suppliers = {x.get("supplier_company_name") for x in c.get("components") or []}
                if company_name not in component_suppliers:
                    continue
            if currency_code and currency_code != "الكل" and str(c.get("currency_original") or "USD").upper() != currency_code:
                continue
            cases.append(c)
        return cases, label

    def period_profit(self, **filters) -> ReportResult:
        cases, label = self._filtered_service_cases(**filters)
        display = currency.get_display_currency()
        rows = []
        total_sale = total_cost = total_profit = 0.0
        by_service = defaultdict(lambda: {"sale": 0.0, "cost": 0.0, "count": 0})
        for c in cases:
            if str(c.get("status") or "open") == "reversed":
                continue
            sale = float(c.get("sale_amount_base") or 0)
            cost = float(c.get("cost_amount_base") or 0)
            profit = sale - cost
            margin = (profit / sale * 100.0) if sale else 0.0
            total_sale += sale
            total_cost += cost
            total_profit += profit
            service = str(c.get("service_type") or "غير محدد")
            by_service[service]["sale"] += sale
            by_service[service]["cost"] += cost
            by_service[service]["count"] += 1
            rows.append({
                "date": c.get("date") or "", "reference": c.get("reference") or "", "client": c.get("client_company_name") or "",
                "person": c.get("person_name") or "", "service": service, "sale": _fmt_usd_to_display(sale, display),
                "cost": _fmt_usd_to_display(cost, display), "profit": _fmt_usd_to_display(profit, display), "margin": f"{margin:.2f}%",
            })
        # Append grouped summaries after details; keeps the report useful even if UI preview uses first rows.
        for service, vals in sorted(by_service.items()):
            sale = float(vals["sale"]); cost = float(vals["cost"]); profit = sale - cost
            rows.append({"date": "—", "reference": "ملخص", "client": "حسب نوع الخدمة", "person": "—", "service": service, "sale": _fmt_usd_to_display(sale, display), "cost": _fmt_usd_to_display(cost, display), "profit": _fmt_usd_to_display(profit, display), "margin": f"{(profit / sale * 100.0) if sale else 0.0:.2f}%"})
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "reference", "label": "المرجع"}, {"key": "client", "label": "العميل"},
            {"key": "person", "label": "المسافر"}, {"key": "service", "label": "الخدمة"}, {"key": "sale", "label": "البيع"},
            {"key": "cost", "label": "التكلفة"}, {"key": "profit", "label": "الربح"}, {"key": "margin", "label": "الهامش"},
        ]
        summary = [
            {"label": "إجمالي البيع", "value": _fmt_usd_to_display(total_sale, display), "class": "debit"},
            {"label": "إجمالي التكلفة", "value": _fmt_usd_to_display(total_cost, display), "class": "credit"},
            {"label": "إجمالي الربح", "value": _fmt_usd_to_display(total_profit, display), "class": "balance"},
            {"label": "عدد الخدمات", "value": str(len([c for c in cases if str(c.get("status") or "open") != "reversed"])), "class": "balance"},
        ]
        return self._result(REPORT_PROFIT, label, columns, rows, summary)

    def services_period(self, **filters) -> ReportResult:
        cases, label = self._filtered_service_cases(**filters)
        rows = []
        total_sale = total_cost = 0.0
        for c in cases:
            sale = float(c.get("sale_amount_base") or 0)
            cost = float(c.get("cost_amount_base") or 0)
            total_sale += sale if str(c.get("status") or "open") != "reversed" else 0
            total_cost += cost if str(c.get("status") or "open") != "reversed" else 0
            components = c.get("components_summary") or ""
            if not components and c.get("components"):
                components = " ؛ ".join(f"{x.get('service_type')} / {x.get('supplier_company_name') or '-'}" for x in c.get("components") or [])
            rows.append({
                "date": c.get("date") or "", "reference": c.get("reference") or "", "client": c.get("client_company_name") or "",
                "supplier": c.get("supplier_company_name") or "", "person": c.get("person_name") or "", "service": c.get("service_type") or "",
                "components": components, "sale": _fmt_usd_to_display(sale), "cost": _fmt_usd_to_display(cost),
                "profit": _fmt_usd_to_display(sale - cost), "status": c.get("status") or "open",
            })
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "reference", "label": "المرجع"}, {"key": "client", "label": "العميل"},
            {"key": "supplier", "label": "المورد"}, {"key": "person", "label": "المسافر"}, {"key": "service", "label": "الخدمة"},
            {"key": "components", "label": "البنود"}, {"key": "sale", "label": "البيع"}, {"key": "cost", "label": "التكلفة"},
            {"key": "profit", "label": "الربح"}, {"key": "status", "label": "الحالة"},
        ]
        summary = [
            {"label": "عدد الخدمات", "value": str(len(cases)), "class": "balance"},
            {"label": "إجمالي البيع", "value": _fmt_usd_to_display(total_sale), "class": "debit"},
            {"label": "إجمالي التكلفة", "value": _fmt_usd_to_display(total_cost), "class": "credit"},
            {"label": "صافي الربح", "value": _fmt_usd_to_display(total_sale - total_cost), "class": "balance"},
        ]
        return self._result(REPORT_SERVICES, label, columns, rows, summary)

    def third_party_payments(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(include_waiting=False, **filters)
        grouped: Dict[str, Dict[str, object]] = defaultdict(dict)
        for r in expenses:
            if str(r.get("source_type") or "") != "third_party_payment":
                continue
            ref = str(r.get("source_ref") or "").strip() or str(r.get("id"))
            item = grouped[ref]
            item["date"] = r.get("date") or item.get("date") or ""
            item["reference"] = ref
            item["currency"] = _original_currency(r)
            item["amount_original"] = _original_amount(r)
            item["amount_base"] = _amount_base(r)
            item["notes"] = r.get("notes") or item.get("notes") or ""
            if r.get("type") == "outgoing":
                item["payer"] = r.get("company_name")
                item["paid_to"] = r.get("counterparty_company_name") or item.get("paid_to")
            elif r.get("type") == "incoming":
                item["paid_to"] = r.get("company_name")
                item["payer"] = r.get("counterparty_company_name") or item.get("payer")
        rows = []
        total = 0.0
        for ref, item in sorted(grouped.items(), key=lambda x: (str(x[1].get("date") or ""), x[0]), reverse=True):
            amount_base = float(item.get("amount_base") or 0)
            total += amount_base
            code = str(item.get("currency") or "USD")
            rows.append({
                "date": item.get("date") or "", "reference": ref, "payer": item.get("payer") or "—", "paid_to": item.get("paid_to") or "—",
                "amount": _fmt_original(float(item.get("amount_original") or 0), code), "amount_display": _fmt_usd_to_display(amount_base),
                "notes": item.get("notes") or "",
            })
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "reference", "label": "المرجع"}, {"key": "payer", "label": "الشركة الدافعة"},
            {"key": "paid_to", "label": "الشركة المدفوع لها"}, {"key": "amount", "label": "المبلغ الأصلي"}, {"key": "amount_display", "label": "المبلغ المعروض"}, {"key": "notes", "label": "ملاحظة"},
        ]
        summary = [{"label": "عدد العمليات", "value": str(len(rows)), "class": "balance"}, {"label": "إجمالي سدد عني", "value": _fmt_usd_to_display(total), "class": "balance"}]
        return self._result(REPORT_THIRD_PARTY, label, columns, rows, summary)



    def open_services(self, **filters) -> ReportResult:
        cases, label = self._filtered_service_cases(**filters)
        today = _dt.date.today()
        rows = []
        total_sale = total_cost = 0.0
        for c in cases:
            status = str(c.get("status") or "open")
            if status == "reversed":
                continue
            sale = float(c.get("sale_amount_base") or 0)
            cost = float(c.get("cost_amount_base") or 0)
            total_sale += sale
            total_cost += cost
            d = _parse_iso(c.get("date")) or today
            age = max(0, (today - d).days)
            components = c.get("components_summary") or ""
            if not components and c.get("components"):
                components = " ؛ ".join(f"{x.get('service_type')} / {x.get('supplier_company_name') or '-'}" for x in c.get("components") or [])
            rows.append({
                "date": c.get("date") or "", "age_days": age, "reference": c.get("reference") or "",
                "client": c.get("client_company_name") or "", "supplier": c.get("supplier_company_name") or "",
                "person": c.get("person_name") or "", "service": c.get("service_type") or "",
                "components": components, "sale": _fmt_usd_to_display(sale), "cost": _fmt_usd_to_display(cost),
                "profit": _fmt_usd_to_display(sale - cost), "status": status,
            })
        rows.sort(key=lambda r: (-int(r.get("age_days") or 0), str(r.get("date") or "")))
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "age_days", "label": "العمر"}, {"key": "reference", "label": "المرجع"},
            {"key": "client", "label": "العميل"}, {"key": "supplier", "label": "المورد"}, {"key": "person", "label": "المسافر"},
            {"key": "service", "label": "الخدمة"}, {"key": "components", "label": "البنود"}, {"key": "sale", "label": "البيع"},
            {"key": "cost", "label": "التكلفة"}, {"key": "profit", "label": "الربح"}, {"key": "status", "label": "الحالة"},
        ]
        summary = [
            {"label": "خدمات مفتوحة", "value": str(len(rows)), "class": "balance"},
            {"label": "إجمالي البيع", "value": _fmt_usd_to_display(total_sale), "class": "debit"},
            {"label": "إجمالي التكلفة", "value": _fmt_usd_to_display(total_cost), "class": "credit"},
            {"label": "ربح مفتوح", "value": _fmt_usd_to_display(total_sale - total_cost), "class": "balance"},
        ]
        return self._result(REPORT_OPEN_SERVICES, label, columns, rows, summary)

    def low_margin_services(self, **filters) -> ReportResult:
        cases, label = self._filtered_service_cases(**filters)
        rows = []
        total_risk_profit = 0.0
        count_loss = count_low = 0
        threshold = 10.0
        for c in cases:
            if str(c.get("status") or "open") == "reversed":
                continue
            sale = float(c.get("sale_amount_base") or 0)
            cost = float(c.get("cost_amount_base") or 0)
            profit = sale - cost
            margin = (profit / sale * 100.0) if sale else 0.0
            if profit >= 0 and margin > threshold:
                continue
            status = "خسارة" if profit < 0 else "هامش منخفض"
            count_loss += 1 if profit < 0 else 0
            count_low += 1 if profit >= 0 else 0
            total_risk_profit += profit
            rows.append({
                "date": c.get("date") or "", "reference": c.get("reference") or "", "client": c.get("client_company_name") or "",
                "supplier": c.get("supplier_company_name") or "", "person": c.get("person_name") or "", "service": c.get("service_type") or "",
                "sale": _fmt_usd_to_display(sale), "cost": _fmt_usd_to_display(cost), "profit": _fmt_usd_to_display(profit),
                "margin": f"{margin:.2f}%", "risk": status,
            })
        rows.sort(key=lambda r: float(str(r.get("margin") or "0").replace("%", "") or 0))
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "reference", "label": "المرجع"}, {"key": "client", "label": "العميل"},
            {"key": "supplier", "label": "المورد"}, {"key": "person", "label": "المسافر"}, {"key": "service", "label": "الخدمة"},
            {"key": "sale", "label": "البيع"}, {"key": "cost", "label": "التكلفة"}, {"key": "profit", "label": "الربح"},
            {"key": "margin", "label": "الهامش"}, {"key": "risk", "label": "التصنيف"},
        ]
        summary = [
            {"label": "عمليات خطرة", "value": str(len(rows)), "class": "balance"},
            {"label": "خسارة", "value": str(count_loss), "class": "credit"},
            {"label": "هامش منخفض", "value": str(count_low), "class": "balance"},
            {"label": "ربحها الصافي", "value": _fmt_usd_to_display(total_risk_profit), "class": "balance"},
        ]
        return self._result(REPORT_LOW_MARGIN, label, columns, rows, summary)

    def locked_entries(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(include_waiting=True, **filters)
        rows = []
        total_in = total_out = 0.0
        for r in expenses:
            if not (int(r.get("is_locked") or 0) or str(r.get("source_type") or "").strip()):
                continue
            amount = _amount_base(r)
            if r.get("type") == "incoming":
                total_in += amount
            else:
                total_out += amount
            op = operation_label(r.get("operation_type") or r.get("source_type"))
            rows.append({
                "date": r.get("date") or "", "id": r.get("id") or "", "company": r.get("company_name") or "",
                "direction": "لنا" if r.get("type") == "incoming" else "له", "amount": _fmt_original(_original_amount(r), _original_currency(r)),
                "amount_display": _fmt_usd_to_display(amount), "operation": op, "source_type": r.get("source_type") or "—",
                "reference": r.get("source_ref") or "—", "counterparty": r.get("counterparty_company_name") or r.get("linked_company_name") or "—",
                "person": r.get("person_name") or "", "service": r.get("service_type") or "", "notes": r.get("print_description") or r.get("notes") or "",
            })
        rows.sort(key=lambda r: (str(r.get("date") or ""), str(r.get("id") or "")), reverse=True)
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "id", "label": "ID"}, {"key": "company", "label": "الشركة"},
            {"key": "direction", "label": "الاتجاه"}, {"key": "amount", "label": "الأصلي"}, {"key": "amount_display", "label": "المعروض"},
            {"key": "operation", "label": "نوع العملية"}, {"key": "reference", "label": "المرجع"}, {"key": "counterparty", "label": "الطرف المقابل"},
            {"key": "person", "label": "الشخص"}, {"key": "service", "label": "الخدمة"}, {"key": "notes", "label": "البيان"},
        ]
        summary = [
            {"label": "قيود مقفلة", "value": str(len(rows)), "class": "balance"},
            {"label": "لنا", "value": _fmt_usd_to_display(total_in), "class": "debit"},
            {"label": "له", "value": _fmt_usd_to_display(total_out), "class": "credit"},
            {"label": "الصافي", "value": _fmt_usd_to_display(total_in - total_out), "class": "balance"},
        ]
        return self._result(REPORT_LOCKED_ENTRIES, label, columns, rows, summary)

    def reversal_operations(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(include_waiting=True, **filters)
        rows = []
        total = 0.0
        for r in expenses:
            source_type = str(r.get("source_type") or "")
            op_type = str(r.get("operation_type") or "")
            is_rev = "reversal" in source_type or "reversal" in op_type or r.get("reversal_of") or r.get("reversed_by")
            if not is_rev:
                continue
            amount = _amount_base(r)
            total += amount if r.get("type") == "incoming" else -amount
            rows.append({
                "date": r.get("date") or "", "reference": r.get("source_ref") or r.get("reversal_of") or r.get("reversed_by") or r.get("id"),
                "company": r.get("company_name") or "", "direction": "لنا" if r.get("type") == "incoming" else "له",
                "amount": _fmt_original(_original_amount(r), _original_currency(r)), "amount_display": _fmt_usd_to_display(amount),
                "operation": operation_label(op_type or source_type), "counterparty": r.get("counterparty_company_name") or r.get("linked_company_name") or "—",
                "notes": r.get("notes") or r.get("internal_note") or "",
            })
        # Add service case headers that have been reversed, even if reversal entries were filtered by company/currency.
        cases, _ = self._filtered_service_cases(**{k: v for k, v in filters.items() if k in {"period", "start_date", "end_date", "company_name", "currency_code"}})
        for c in cases:
            if str(c.get("status") or "") != "reversed":
                continue
            rows.append({
                "date": str(c.get("reversed_at") or c.get("date") or "")[:10], "reference": c.get("reversal_ref") or f"REV-{c.get('reference')}",
                "company": c.get("client_company_name") or "", "direction": "ملف خدمة", "amount": _fmt_original(float(c.get("sale_amount_original") or 0), str(c.get("currency_original") or "USD")),
                "amount_display": _fmt_usd_to_display(float(c.get("sale_amount_base") or 0)), "operation": "عكس ملف خدمة", "counterparty": c.get("supplier_company_name") or "—",
                "notes": c.get("reference") or "",
            })
        rows.sort(key=lambda r: (str(r.get("date") or ""), str(r.get("reference") or "")), reverse=True)
        columns = [
            {"key": "date", "label": "التاريخ"}, {"key": "reference", "label": "مرجع العكس/الأصل"}, {"key": "company", "label": "الشركة"},
            {"key": "direction", "label": "الاتجاه"}, {"key": "amount", "label": "الأصلي"}, {"key": "amount_display", "label": "المعروض"},
            {"key": "operation", "label": "نوع العكس"}, {"key": "counterparty", "label": "الطرف المقابل"}, {"key": "notes", "label": "ملاحظة"},
        ]
        summary = [
            {"label": "عمليات معكوسة", "value": str(len(rows)), "class": "balance"},
            {"label": "الأثر الصافي", "value": _fmt_usd_to_display(total), "class": "balance"},
        ]
        return self._result(REPORT_REVERSALS, label, columns, rows, summary)

    def operation_summary(self, **filters) -> ReportResult:
        expenses, label, _, _ = self._filtered_expenses(include_waiting=True, **filters)
        grouped = defaultdict(lambda: {"incoming": 0.0, "outgoing": 0.0, "count": 0, "locked": 0, "waiting": 0})
        for r in expenses:
            key = operation_label(r.get("operation_type") or r.get("source_type") or "normal")
            item = grouped[key]
            amount = _amount_base(r)
            if r.get("type") == "incoming":
                item["incoming"] += amount
            else:
                item["outgoing"] += amount
            item["count"] += 1
            item["locked"] += 1 if int(r.get("is_locked") or 0) else 0
            item["waiting"] += 1 if r.get("status") == "waiting_payment" else 0
        rows = []
        total_in = total_out = 0.0
        for op, item in sorted(grouped.items()):
            incoming = float(item["incoming"]); outgoing = float(item["outgoing"]); net = incoming - outgoing
            total_in += incoming; total_out += outgoing
            rows.append({
                "operation": op, "count": int(item["count"]), "incoming": _fmt_usd_to_display(incoming), "outgoing": _fmt_usd_to_display(outgoing),
                "net": _fmt_usd_to_display(net), "locked": int(item["locked"]), "waiting": int(item["waiting"]),
            })
        columns = [
            {"key": "operation", "label": "نوع العملية"}, {"key": "count", "label": "العدد"}, {"key": "incoming", "label": "لنا"},
            {"key": "outgoing", "label": "له"}, {"key": "net", "label": "الصافي"}, {"key": "locked", "label": "مقفلة"}, {"key": "waiting", "label": "انتظار"},
        ]
        summary = [
            {"label": "أنواع العمليات", "value": str(len(rows)), "class": "balance"},
            {"label": "إجمالي لنا", "value": _fmt_usd_to_display(total_in), "class": "debit"},
            {"label": "إجمالي له", "value": _fmt_usd_to_display(total_out), "class": "credit"},
            {"label": "الصافي", "value": _fmt_usd_to_display(total_in - total_out), "class": "balance"},
        ]
        return self._result(REPORT_OPERATION_SUMMARY, label, columns, rows, summary)

    def audit_activity(self, **filters) -> ReportResult:
        start, end, label = resolve_period(filters.get("period"), filters.get("start_date"), filters.get("end_date"))
        logs = self.audit_repo.get_all(limit=1000, start_date=start, end_date=end)
        by_action = defaultdict(int)
        by_user = defaultdict(int)
        rows = []
        for log in logs:
            action = str(log.get("action") or "")
            username = str(log.get("username") or "") or "—"
            by_action[action] += 1
            by_user[username] += 1
            rows.append({
                "timestamp": str(log.get("timestamp") or "")[:19], "username": username, "action": action,
                "table_name": log.get("table_name") or "", "record_id": log.get("record_id") or "", "details": log.get("details") or "",
            })
        columns = [
            {"key": "timestamp", "label": "الوقت"}, {"key": "username", "label": "المستخدم"}, {"key": "action", "label": "الإجراء"},
            {"key": "table_name", "label": "الجدول"}, {"key": "record_id", "label": "المعرّف"}, {"key": "details", "label": "التفاصيل"},
        ]
        top_action = max(by_action.items(), key=lambda x: x[1])[0] if by_action else "—"
        top_user = max(by_user.items(), key=lambda x: x[1])[0] if by_user else "—"
        summary = [
            {"label": "عدد السجلات", "value": str(len(rows)), "class": "balance"},
            {"label": "أكثر إجراء", "value": str(top_action), "class": "balance"},
            {"label": "أكثر مستخدم", "value": str(top_user), "class": "balance"},
        ]
        return self._result(REPORT_AUDIT, label, columns, rows, summary)


def _summary_html(report: ReportResult) -> str:
    if not report.summary:
        return ""
    cells = []
    for item in report.summary:
        cls = str(item.get("class") or "balance")
        cells.append(f"<div class='metric'><small>{_safe(item.get('label'))}</small><strong class='{cls}'>{_safe(item.get('value'))}</strong></div>")
    return f"<div class='summary report-summary'>{''.join(cells)}</div>"


def _rows_html(report: ReportResult) -> str:
    headers = "".join(f"<th>{_safe(c.get('label'))}</th>" for c in report.columns)
    rows = []
    for row in report.rows:
        cells = []
        for c in report.columns:
            key = str(c.get("key"))
            value = row.get(key, "")
            cls = "ref" if key in {"reference", "timestamp", "date"} else ""
            if key in {"incoming", "outgoing", "net", "sale", "cost", "profit", "amount", "amount_display"}:
                cells.append(f"<td>{_money_span(str(value), 'balance' if key in {'net','profit','amount_display'} else ('debit' if key in {'incoming','sale','amount'} else 'credit'))}</td>")
            elif cls:
                cells.append(f"<td><span class='ltr'>{_safe(value)}</span></td>")
            else:
                cells.append(f"<td>{_safe(value)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    if not rows:
        rows.append(f"<tr><td colspan='{max(1, len(report.columns))}' class='empty'>لا توجد بيانات ضمن الفلاتر المحددة</td></tr>")
    return f"<div class='table-scroll'><table class='modern-table reporting-table'><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def _report_css() -> str:
    return _base_css(compact=False, use_colors=True) + """
.reporting-table { min-width:980px; }
.reporting-table td { font-size:12px; }
.report-summary { grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); }
.report-note { background:#F3F8FF;border:1px solid #D8E4EE;border-radius:14px;padding:11px 13px;color:#334155;font-size:12px;margin:10px 0;line-height:1.8; }
@media (max-width:640px) { .reporting-table { min-width:820px; } }
"""


def export_report_html(report: ReportResult, output_path: str | None = None) -> str:
    info = get_company_info()
    filename = f"{report.filename_slug}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or FileExportService.build_path(_safe_filename(filename), "reports", temporary=True)
    meta = f"الفترة: {_safe(report.period_label)} | العملة المعروضة: <span class='ltr'>{_safe(report.display_currency)}</span> | تاريخ الإنشاء: <span class='ltr'>{_safe(report.generated_at)}</span>"
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_safe(report.title)}</title><style>{_report_css()}</style></head><body><div class="sheet">
{_header_html(info, company_name=report.category, statement_kind=report.title, settings={"show_company_logo": True, "show_company_contact": True})}
<div class="title"><h2>{_safe(report.title)}</h2><div class="meta">{meta}</div></div>
<div class="report-note">هذا التقرير صادر من مركز التقارير الموحّد. الأرقام المالية تعتمد نفس دفتر القيود وسعر العملة التاريخي المستخدم في الكشوف.</div>
{_summary_html(report)}
{_rows_html(report)}
<div class="footer"><span>تم إنشاء التقرير بواسطة نظام هوى الشام</span><span>{_safe(info.get('name'))}</span></div>
</div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


def export_report_csv(report: ReportResult, output_path: str | None = None) -> str:
    filename = f"{report.filename_slug}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = output_path or FileExportService.build_path(_safe_filename(filename), "reports", temporary=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([c.get("label") for c in report.columns])
        for row in report.rows:
            writer.writerow([row.get(str(c.get("key")), "") for c in report.columns])
    return output_path
