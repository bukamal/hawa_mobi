# -*- coding: utf-8 -*-
"""Professional statement export templates for Android/Flet.

Phase 71 separates external reconciliation from internal/detailed printing.
The reconciliation template is deliberately mobile-first: it avoids wide tables,
keeps money/phone/email/reference text LTR-isolated, and hides internal supplier
profit/cost context.
"""
from __future__ import annotations

import csv
import datetime as _dt
import html
import os
from typing import Dict, Iterable, List, Tuple

from config import get_company_info
from currency import currency
from reports.config import get_report_settings
from services.company_logo_service import image_to_data_uri


def _safe(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _money(amount, code) -> str:
    try:
        return currency.format_amount_full(float(amount or 0), code)
    except Exception:
        return f"{float(amount or 0):,.2f} {code}"


def _money_span(value: str, extra_class: str = "") -> str:
    cls = f"money {extra_class}".strip()
    return f"<span class='{cls}'>{_safe(value)}</span>"


def _ltr(value) -> str:
    return f"<span class='ltr'>{_safe(value)}</span>" if value not in (None, "") else ""


def _visible_columns(settings: Dict[str, object]) -> List[Dict[str, object]]:
    return [c for c in settings.get("account_statement_columns", []) if c.get("visible", True)]


def _report_dir() -> str:
    from services.file_export_service import FileExportService
    return FileExportService.export_dir("reports", temporary=True)


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)


def _short_ref(ref: object) -> str:
    raw = str(ref or "").strip()
    if not raw:
        return ""
    if len(raw) <= 16:
        return raw
    parts = raw.split("-")
    if len(parts) >= 2 and parts[0] in {"SVC", "TPP", "PAY"}:
        return f"{parts[0]}-{parts[-1][-8:]}"
    return "…" + raw[-14:]


def _full_ref(record: Dict) -> str:
    return str(record.get("source_ref") or record.get("reference") or record.get("id") or "").strip()


def _print_description(record: Dict) -> str:
    return str(record.get("print_description") or record.get("notes") or "").strip()


def _statement_meta(record_or_row: Dict, *, include_full_ref: bool = False) -> List[str]:
    meta: List[str] = []
    person = str(record_or_row.get("person_name") or "").strip()
    service = str(record_or_row.get("service_type") or "").strip()
    ref = str(record_or_row.get("reference") or record_or_row.get("source_ref") or "").strip()
    if person:
        meta.append(f"الزبون: {person}")
    if service:
        meta.append(f"الخدمة: {service}")
    if ref:
        meta.append(f"Ref: {ref if include_full_ref else _short_ref(ref)}")
    return meta


def _header_html(info: Dict, *, company_name: str, statement_kind: str, settings: Dict) -> str:
    logo_uri = image_to_data_uri(info.get("logo_path") or "") if settings.get("show_company_logo", True) else None
    logo_html = f"<img src='{logo_uri}' class='company-logo' alt='logo'>" if logo_uri else ""
    address = _safe(info.get("address") or "")
    phone = _ltr(info.get("phone") or "")
    email = _ltr(info.get("email") or "")
    contact_bits = []
    if address:
        contact_bits.append(address)
    if phone:
        contact_bits.append(phone)
    if email:
        contact_bits.append(email)
    tax = _safe(info.get("tax_number") or "")
    if tax:
        contact_bits.append(tax)
    contact = " <span class='sep'>|</span> ".join(contact_bits)
    return f"""
<header class="report-header">
  <div class="account-badge">{_safe(company_name)}</div>
  <div class="brand-block">
    <div class="brand-text">
      <h1>{_safe(info.get('name'))}</h1>
      <div class="contact-line">{contact}</div>
      <div class="statement-kind">{_safe(statement_kind)}</div>
    </div>
    {logo_html}
  </div>
</header>
"""


def _base_css(*, compact: bool) -> str:
    return f"""
@page {{ size:A4; margin:12mm; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#f8fafc; color:#111827; direction:rtl; font-family:Tahoma,Arial,system-ui,sans-serif; }}
.sheet {{ max-width:{'820px' if compact else '980px'}; margin:0 auto; padding:18px; background:#fff; }}
.report-header {{ border-bottom:3px solid #1e3a8a; padding-bottom:14px; margin-bottom:18px; position:relative; }}
.brand-block {{ display:flex; align-items:center; justify-content:center; gap:18px; text-align:center; }}
.brand-text h1 {{ margin:0; color:#1e3a8a; font-size:28px; line-height:1.35; }}
.company-logo {{ width:64px; height:64px; object-fit:contain; border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:4px; flex:0 0 auto; }}
.contact-line {{ color:#4b5563; font-size:13px; line-height:1.8; margin-top:5px; }}
.statement-kind {{ color:#4b5563; font-size:12px; margin-top:4px; }}
.account-badge {{ position:absolute; left:0; top:0; background:#eff6ff; color:#1e40af; border-radius:12px; padding:9px 13px; font-weight:700; max-width:145px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.title {{ text-align:center; margin:16px 0 14px; }}
.title h2 {{ margin:0 0 7px; font-size:25px; color:#111827; }}
.title .meta {{ color:#6b7280; font-size:13px; }}
.account-line {{ font-size:16px; font-weight:700; color:#1e3a8a; margin-top:4px; }}
.summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:14px 0; }}
.metric {{ border:1px solid #e5e7eb; border-radius:14px; padding:12px; background:#f9fafb; text-align:center; min-height:78px; }}
.metric small {{ display:block; color:#6b7280; margin-bottom:7px; }}
.metric strong {{ display:block; font-size:20px; line-height:1.35; }}
.final-metric strong {{ font-size:16px; }}
.note {{ border:1px solid #bfdbfe; background:#eff6ff; color:#1e3a8a; padding:11px 13px; border-radius:14px; margin:12px 0; font-size:13px; line-height:1.75; }}
.money,.ltr,.ref {{ direction:ltr; unicode-bidi:isolate; white-space:nowrap; display:inline-block; }}
.debit {{ color:#047857; }} .credit {{ color:#b91c1c; }} .balance {{ color:#1e3a8a; }}
.footer {{ margin-top:18px; border-top:1px solid #d1d5db; padding-top:10px; color:#6b7280; font-size:11px; display:flex; justify-content:space-between; gap:16px; }}
.empty {{ text-align:center; color:#6b7280; padding:22px; border:1px dashed #d1d5db; border-radius:14px; }}
@media (max-width:640px) {{
  .sheet {{ padding:14px 12px; }}
  .brand-block {{ justify-content:flex-start; text-align:right; gap:12px; }}
  .brand-text h1 {{ font-size:24px; }}
  .company-logo {{ width:58px; height:58px; }}
  .account-badge {{ position:static; display:inline-block; margin-bottom:10px; max-width:100%; }}
  .summary {{ grid-template-columns:1fr; }}
}}
@media print {{ body {{ background:#fff; }} .sheet {{ padding:0; max-width:none; }} }}
"""


def build_rows(records: Iterable[Dict], display_currency: str | None = None) -> Tuple[List[Dict[str, str]], Dict[str, float]]:
    display_currency = display_currency or currency.get_display_currency()
    rows: List[Dict[str, str]] = []
    running_usd = 0.0
    total_debit_usd = 0.0
    total_credit_usd = 0.0

    sorted_records = sorted(list(records), key=lambda r: (str(r.get("date", "")), int(r.get("id") or 0)))
    for r in sorted_records:
        is_waiting = r.get("status") == "waiting_payment"
        amount_usd = float(r.get("amount") or r.get("amount_base") or 0)
        amount_original = float(r.get("amount_original", amount_usd) or 0)
        currency_original = r.get("currency_original") or r.get("currency") or display_currency
        type_val = r.get("type")

        debit = ""
        credit = ""
        if type_val == "incoming":
            debit = _money(amount_original, currency_original)
            if not is_waiting:
                running_usd += amount_usd
                total_debit_usd += amount_usd
        else:
            credit = _money(amount_original, currency_original)
            if not is_waiting:
                running_usd -= amount_usd
                total_credit_usd += amount_usd

        exchange_rate = r.get("exchange_rate_to_usd")
        historical = ""
        if exchange_rate not in (None, ""):
            try:
                historical = f"1 USD = {float(exchange_rate):,.6f} {currency_original}"
            except Exception:
                historical = str(exchange_rate)

        reference = _full_ref(r)
        rows.append({
            "date": str(r.get("date", "")),
            "notes": str(r.get("notes") or ""),
            "description": _print_description(r) or str(r.get("notes") or ""),
            "reference": reference,
            "short_reference": _short_ref(reference),
            "debit": debit,
            "credit": credit,
            "running_balance": _money(currency.convert(running_usd, "USD", display_currency), display_currency),
            "currency": str(currency_original),
            "historical_currency_value": historical,
            "status": "بانتظار الدفع" if is_waiting else "معتمد",
            "due_date": str(r.get("payment_due_date") or ""),
            "person_name": str(r.get("person_name") or ""),
            "service_type": str(r.get("service_type") or ""),
            "operation_type": str(r.get("operation_type") or ""),
        })

    return rows, {
        "total_debit_usd": total_debit_usd,
        "total_credit_usd": total_credit_usd,
        "net_usd": total_debit_usd - total_credit_usd,
    }


def _summary_values(totals: Dict[str, float], display_currency: str) -> Tuple[str, str, str]:
    total_debit = _money(currency.convert(totals["total_debit_usd"], "USD", display_currency), display_currency)
    total_credit = _money(currency.convert(totals["total_credit_usd"], "USD", display_currency), display_currency)
    net = _money(currency.convert(totals["net_usd"], "USD", display_currency), display_currency)
    return total_debit, total_credit, net


def export_account_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None) -> str:
    """Detailed printable statement.

    The detailed layout is still table-based, but it is constrained to five
    columns. Person/service/reference data is folded into the statement cell so
    mobile browsers do not break the report into unreadable narrow columns.
    """
    settings = get_report_settings()
    info = get_company_info()
    display_currency = currency.get_display_currency()
    rows, totals = build_rows(records, display_currency)
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_debit, total_credit, net = _summary_values(totals, display_currency)

    filename = f"account_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), _safe_filename(filename))
    footer_note = _safe(settings.get("footer_note", "هذا الكشف صادر آلياً من نظام هوى الشام."))

    body_rows = []
    for row in rows:
        meta = _statement_meta(row, include_full_ref=True)
        meta_html = "".join(f"<span>{_safe(x)}</span>" for x in meta)
        statement = _safe(row.get("description") or row.get("notes") or "")
        body_rows.append(
            "<tr>"
            f"<td class='date-cell'>{_ltr(row['date'])}</td>"
            f"<td class='statement-cell'><div class='statement-main'>{statement}</div><div class='statement-meta'>{meta_html}</div></td>"
            f"<td>{_money_span(row['debit'], 'debit')}</td>"
            f"<td>{_money_span(row['credit'], 'credit')}</td>"
            f"<td>{_money_span(row['running_balance'], 'balance')}</td>"
            "</tr>"
        )
    if not body_rows:
        body_rows.append("<tr><td colspan='5' class='empty'>لا توجد قيود</td></tr>")

    doc = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>كشف حساب تفصيلي - {_safe(company_name)}</title>
<style>{_base_css(compact=False)}
.detailed-table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
.detailed-table th {{ background:#1e3a8a; color:#fff; padding:9px 7px; border:1px solid #1e3a8a; font-size:13px; }}
.detailed-table td {{ border:1px solid #d1d5db; padding:8px 7px; font-size:12px; vertical-align:top; }}
.detailed-table tr:nth-child(even) td {{ background:#f9fafb; }}
.date-cell {{ width:76px; }}
.statement-cell {{ width:auto; }}
.statement-main {{ font-weight:600; line-height:1.65; }}
.statement-meta {{ margin-top:5px; color:#6b7280; font-size:11px; display:flex; flex-wrap:wrap; gap:5px 9px; }}
.statement-meta span {{ background:#f3f4f6; border-radius:999px; padding:2px 7px; }}
@media (max-width:640px) {{ .detailed-table th,.detailed-table td {{ font-size:11px; padding:7px 5px; }} .date-cell {{ width:66px; }} }}
</style></head><body><div class="sheet">
{_header_html(info, company_name=company_name, statement_kind='كشف حساب تفصيلي', settings=settings)}
<div class="title"><h2>كشف حساب شركة</h2><div class="account-line">الحساب: {_safe(company_name)}</div><div class="meta">{'تاريخ الإنشاء: ' + _ltr(generated_at) if settings.get('show_generated_at', True) else ''} | العملة: {_ltr(display_currency)}</div></div>
<div class="summary"><div class="metric"><small>لنا</small><strong>{_money_span(total_debit,'debit')}</strong></div><div class="metric"><small>له</small><strong>{_money_span(total_credit,'credit')}</strong></div><div class="metric"><small>الصافي التراكمي</small><strong>{_money_span(net,'balance')}</strong></div></div>
<table class="detailed-table"><thead><tr><th>التاريخ</th><th>البيان</th><th>لنا</th><th>له</th><th>التراكمي</th></tr></thead><tbody>{''.join(body_rows)}</tbody></table>
<div class="footer"><span>{footer_note}</span><span>{_safe(info.get('name'))}</span></div>
</div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


def export_account_statement_csv(company_name: str, records: Iterable[Dict], output_path: str | None = None) -> str:
    settings = get_report_settings()
    rows, _ = build_rows(records, currency.get_display_currency())
    cols = _visible_columns(settings)
    filename = f"account_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = output_path or os.path.join(_report_dir(), _safe_filename(filename))
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([c.get("label") for c in cols])
        for row in rows:
            writer.writerow([row.get(str(c.get("key")), "") for c in cols])
    return output_path


def _statement_balance_label(net_usd: float, display_currency: str) -> str:
    value = _money(abs(currency.convert(net_usd, "USD", display_currency)), display_currency)
    if net_usd > 0:
        return f"الرصيد النهائي لصالح {get_company_info().get('name')}: {value}"
    if net_usd < 0:
        return f"الرصيد النهائي لصالح الحساب المقابل: {value}"
    return "الرصيد النهائي: مطابق / لا يوجد رصيد"


def build_reconciliation_rows(records: Iterable[Dict], display_currency: str | None = None) -> Tuple[List[Dict[str, str]], Dict[str, float]]:
    display_currency = display_currency or currency.get_display_currency()
    rows: List[Dict[str, str]] = []
    running_usd = 0.0
    total_debit_usd = 0.0
    total_credit_usd = 0.0
    for r in sorted(list(records), key=lambda x: (str(x.get("date", "")), int(x.get("id") or 0))):
        if r.get("status") == "waiting_payment":
            continue
        amount_usd = float(r.get("amount") or r.get("amount_base") or 0)
        amount_original = float(r.get("amount_original", amount_usd) or 0)
        currency_original = r.get("currency_original") or r.get("currency") or display_currency
        reference = _full_ref(r)
        debit = credit = ""
        if r.get("type") == "incoming":
            debit = _money(amount_original, currency_original)
            running_usd += amount_usd
            total_debit_usd += amount_usd
        else:
            credit = _money(amount_original, currency_original)
            running_usd -= amount_usd
            total_credit_usd += amount_usd
        rows.append({
            "date": str(r.get("date") or ""),
            "reference": reference,
            "short_reference": _short_ref(reference),
            "description": _print_description(r),
            "person_name": str(r.get("person_name") or ""),
            "service_type": str(r.get("service_type") or ""),
            "debit": debit,
            "credit": credit,
            "running_balance": _money(currency.convert(running_usd, "USD", display_currency), display_currency),
        })
    return rows, {"total_debit_usd": total_debit_usd, "total_credit_usd": total_credit_usd, "net_usd": total_debit_usd - total_credit_usd}


def export_reconciliation_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None, *, show_person: bool = True, show_service: bool = True) -> str:
    """External-facing mobile-first statement for company reconciliation."""
    settings = get_report_settings()
    info = get_company_info()
    display_currency = currency.get_display_currency()
    rows, totals = build_reconciliation_rows(records, display_currency)
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = f"reconciliation_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), _safe_filename(filename))
    total_debit, total_credit, _net = _summary_values(totals, display_currency)
    net_label = _statement_balance_label(totals["net_usd"], display_currency)

    movement_cards = []
    for i, row in enumerate(rows, start=1):
        meta_parts = []
        if show_person and row.get("person_name"):
            meta_parts.append(f"الزبون: {row['person_name']}")
        if show_service and row.get("service_type"):
            meta_parts.append(f"الخدمة: {row['service_type']}")
        if row.get("reference"):
            meta_parts.append(f"Ref: {row['short_reference']}")
        meta_html = "".join(f"<span>{_safe(x)}</span>" for x in meta_parts)
        movement_cards.append(f"""
<section class="movement">
  <div class="movement-head"><span class="idx">#{i}</span><span class="date">{_ltr(row['date'])}</span></div>
  <div class="movement-desc">{_safe(row.get('description') or 'حركة حساب')}</div>
  <div class="movement-meta">{meta_html}</div>
  <div class="movement-money">
    <div><small>لنا</small><strong>{_money_span(row['debit'], 'debit')}</strong></div>
    <div><small>له</small><strong>{_money_span(row['credit'], 'credit')}</strong></div>
    <div><small>الرصيد</small><strong>{_money_span(row['running_balance'], 'balance')}</strong></div>
  </div>
</section>
""")
    if not movement_cards:
        movement_cards.append("<div class='empty'>لا توجد حركات ضمن هذا الحساب</div>")

    doc = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>كشف مطابقة - {_safe(company_name)}</title>
<style>{_base_css(compact=True)}
.movements {{ display:flex; flex-direction:column; gap:10px; }}
.movement {{ border:1px solid #d1d5db; border-radius:16px; padding:12px; background:#fff; page-break-inside:avoid; }}
.movement:nth-child(even) {{ background:#f9fafb; }}
.movement-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; color:#6b7280; }}
.idx {{ background:#eff6ff; color:#1e40af; border-radius:999px; padding:3px 8px; font-weight:700; }}
.date {{ font-weight:700; color:#374151; }}
.movement-desc {{ font-size:15px; font-weight:700; line-height:1.65; margin-bottom:6px; }}
.movement-meta {{ display:flex; flex-wrap:wrap; gap:5px 7px; margin-bottom:10px; color:#4b5563; font-size:12px; }}
.movement-meta span {{ background:#f3f4f6; border-radius:999px; padding:3px 8px; }}
.movement-money {{ display:grid; grid-template-columns:repeat(3,1fr); gap:7px; }}
.movement-money div {{ border:1px solid #e5e7eb; border-radius:12px; padding:8px; background:#fff; text-align:center; min-width:0; }}
.movement-money small {{ display:block; color:#6b7280; margin-bottom:5px; }}
.movement-money strong {{ font-size:14px; }}
@media (max-width:640px) {{ .movement-money {{ grid-template-columns:1fr; }} .movement-desc {{ font-size:14px; }} }}
</style></head><body><div class="sheet">
{_header_html(info, company_name=company_name, statement_kind='كشف حساب للمطابقة', settings=settings)}
<div class="title"><h2>كشف حساب للمطابقة</h2><div class="account-line">الحساب: {_safe(company_name)}</div><div class="meta">تاريخ الإنشاء: {_ltr(generated_at)} | العملة المعروضة: {_ltr(display_currency)}</div></div>
<div class="note">لنا = مبالغ مستحقة لنا على الحساب. له = مبالغ مستحقة للحساب علينا أو مدفوعة منه. هذا الكشف مخصص للمطابقة ولا يُعد مخالصة نهائية إلا بعد التأكيد.</div>
<div class="summary"><div class="metric"><small>لنا</small><strong>{_money_span(total_debit,'debit')}</strong></div><div class="metric"><small>له</small><strong>{_money_span(total_credit,'credit')}</strong></div><div class="metric final-metric"><small>النتيجة</small><strong>{_safe(net_label)}</strong></div></div>
<div class="movements">{''.join(movement_cards)}</div>
<div class="footer"><span>يرجى مراجعة الكشف وإبلاغنا بأي اختلاف خلال 48 ساعة.</span><span>{_safe(info.get('name'))}</span></div>
</div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


def export_service_profit_report_html(cases: Iterable[Dict], output_path: str | None = None) -> str:
    info = get_company_info()
    display_currency = currency.get_display_currency()
    rows = []
    total_profit = 0.0
    for c in cases:
        sale = float(c.get("sale_amount_base") or 0)
        cost = float(c.get("cost_amount_base") or 0)
        profit = sale - cost
        total_profit += profit if (c.get("status") or "open") != "reversed" else 0
        component_summary = c.get("components_summary") or ""
        if not component_summary and c.get("components"):
            try:
                component_summary = " ؛ ".join(f"{x.get('service_type')} / {x.get('supplier_company_name') or '-'}" for x in c.get("components") or [])
            except Exception:
                component_summary = ""
        service_cell = (str(c.get("service_type") or "") + (f"<br><small>{_safe(component_summary)}</small>" if component_summary else ""))
        rows.append(
            f"<tr><td>{_ltr(c.get('date'))}</td><td>{_ltr(c.get('reference'))}</td><td>{_safe(c.get('person_name'))}</td>"
            f"<td>{_safe(c.get('client_company_name'))}</td><td>{_safe(c.get('supplier_company_name'))}</td><td>{service_cell}</td>"
            f"<td>{_money_span(_money(currency.convert(sale,'USD',display_currency),display_currency),'debit')}</td>"
            f"<td>{_money_span(_money(currency.convert(cost,'USD',display_currency),display_currency),'credit')}</td>"
            f"<td>{_money_span(_money(currency.convert(profit,'USD',display_currency),display_currency),'balance')}</td><td>{_safe(c.get('status'))}</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='10' class='empty'>لا توجد ملفات خدمات</td></tr>")
    filename = f"service_profit_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), filename)
    doc = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>تقرير أرباح الخدمات</title><style>{_base_css(compact=False)}table{{width:100%;border-collapse:collapse}}th{{background:#1e3a8a;color:#fff;padding:8px;border:1px solid #1e3a8a}}td{{border:1px solid #d1d5db;padding:7px;font-size:12px;vertical-align:top}}.summary-box{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:12px;margin:12px 0}}</style></head><body><div class="sheet">{_header_html(info, company_name='داخلي', statement_kind='تقرير أرباح الخدمات', settings={'show_company_logo': True})}<div class="title"><h2>تقرير أرباح الخدمات الداخلي</h2></div><div class="summary-box">إجمالي الربح: <strong>{_money_span(_money(currency.convert(total_profit,'USD',display_currency),display_currency),'balance')}</strong></div><table><thead><tr><th>التاريخ</th><th>المرجع</th><th>الزبون</th><th>العميل</th><th>المورد</th><th>الخدمة</th><th>البيع</th><th>التكلفة</th><th>الربح</th><th>الحالة</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path
