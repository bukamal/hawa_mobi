# -*- coding: utf-8 -*-
"""Professional account statement export.

Generates a print-ready RTL HTML report. On Android this is the safest path:
open/share the HTML, then print or save as PDF from the system viewer/browser.
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


def _visible_columns(settings: Dict[str, object]) -> List[Dict[str, object]]:
    return [c for c in settings.get("account_statement_columns", []) if c.get("visible", True)]


def build_rows(records: Iterable[Dict], display_currency: str | None = None) -> Tuple[List[Dict[str, str]], Dict[str, float]]:
    display_currency = display_currency or currency.get_display_currency()
    rows: List[Dict[str, str]] = []
    running_usd = 0.0
    total_debit_usd = 0.0
    total_credit_usd = 0.0

    sorted_records = sorted(list(records), key=lambda r: (str(r.get("date", "")), int(r.get("id") or 0)))
    for r in sorted_records:
        is_waiting = r.get("status") == "waiting_payment"
        amount_usd = float(r.get("amount") or 0)
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

        rows.append({
            "date": str(r.get("date", "")),
            "notes": str(r.get("notes") or ""),
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


def _report_dir() -> str:
    from services.file_export_service import FileExportService
    return FileExportService.export_dir("reports", temporary=True)


def export_account_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None) -> str:
    settings = get_report_settings()
    info = get_company_info()
    display_currency = currency.get_display_currency()
    rows, totals = build_rows(records, display_currency)
    cols = _visible_columns(settings)
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    total_debit = _money(currency.convert(totals["total_debit_usd"], "USD", display_currency), display_currency)
    total_credit = _money(currency.convert(totals["total_credit_usd"], "USD", display_currency), display_currency)
    net = _money(currency.convert(totals["net_usd"], "USD", display_currency), display_currency)

    filename = f"account_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    safe_filename = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
    output_path = output_path or os.path.join(_report_dir(), safe_filename)

    header_lines = [info.get("address"), info.get("phone"), info.get("email"), info.get("tax_number")]
    logo_uri = image_to_data_uri(info.get("logo_path") or "") if settings.get("show_company_logo", True) else None
    logo_html = f"<img src='{logo_uri}' class='company-logo' alt='logo'>" if logo_uri else ""
    header_meta = " | ".join(_safe(x) for x in header_lines if x)
    header_note = _safe(settings.get("header_note", ""))
    footer_note = _safe(settings.get("footer_note", ""))

    th = "".join(f"<th style='width:{_safe(c.get('width','auto'))}'>{_safe(c.get('label'))}</th>" for c in cols)
    body_rows = []
    for row in rows:
        tds = "".join(f"<td>{_safe(row.get(str(c.get('key')), ''))}</td>" for c in cols)
        body_rows.append(f"<tr>{tds}</tr>")
    if not body_rows:
        body_rows.append(f"<tr><td colspan='{len(cols)}' class='empty'>لا توجد قيود</td></tr>")

    doc = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>كشف حساب - {_safe(company_name)}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  body {{ font-family: Tahoma, Arial, sans-serif; color:#111827; direction:rtl; margin:0; background:#fff; }}
  .sheet {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
  .top {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #1e3a8a; padding-bottom:14px; margin-bottom:18px; }}
  .brand-wrap {{ display:flex; align-items:center; gap:12px; }}
  .company-logo {{ width:72px; height:72px; object-fit:contain; border-radius:14px; border:1px solid #e5e7eb; background:#fff; padding:4px; }}
  .brand h1 {{ margin:0; color:#1e3a8a; font-size:24px; }}
  .brand p {{ margin:4px 0; color:#4b5563; font-size:12px; }}
  .badge {{ background:#eff6ff; color:#1e40af; padding:10px 14px; border-radius:12px; font-weight:bold; }}
  .title {{ text-align:center; margin: 12px 0 18px; }}
  .title h2 {{ margin:0; font-size:22px; }}
  .title p {{ margin:6px 0 0; color:#6b7280; }}
  .summary {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:14px; }}
  .metric {{ border:1px solid #e5e7eb; border-radius:12px; padding:10px; background:#f9fafb; }}
  .metric small {{ color:#6b7280; display:block; }}
  .metric strong {{ font-size:16px; }}
  table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
  th {{ background:#1e3a8a; color:#fff; padding:9px 7px; border:1px solid #1e3a8a; font-size:12px; }}
  td {{ padding:8px 7px; border:1px solid #d1d5db; font-size:12px; vertical-align:top; word-wrap:break-word; }}
  tr:nth-child(even) td {{ background:#f9fafb; }}
  .empty {{ text-align:center; color:#6b7280; padding:22px; }}
  .footer {{ margin-top:18px; padding-top:10px; border-top:1px solid #d1d5db; color:#6b7280; font-size:11px; display:flex; justify-content:space-between; gap:20px; }}
  @media print {{ .sheet {{ padding:0; }} }}
</style>
</head>
<body>
<div class="sheet">
  <div class="top">
    <div class="brand-wrap">
      {logo_html}
      <div class="brand">
        <h1>{_safe(info.get('name'))}</h1>
        <p>{header_meta}</p>
        <p>{header_note}</p>
      </div>
    </div>
    <div class="badge">{_safe(company_name)}</div>
  </div>
  <div class="title">
    <h2>كشف حساب شركة</h2>
    <p>{'تاريخ الإنشاء: ' + _safe(generated_at) if settings.get('show_generated_at', True) else ''}</p>
  </div>
  <div class="summary">
    <div class="metric"><small>لنا</small><strong>{_safe(total_debit)}</strong></div>
    <div class="metric"><small>له</small><strong>{_safe(total_credit)}</strong></div>
    <div class="metric"><small>الصافي التراكمي</small><strong>{_safe(net)}</strong></div>
  </div>
  <table>
    <thead><tr>{th}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  <div class="footer">
    <span>{footer_note}</span>
    <span>{_safe(info.get('name'))}</span>
  </div>
</div>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


def export_account_statement_csv(company_name: str, records: Iterable[Dict], output_path: str | None = None) -> str:
    settings = get_report_settings()
    rows, _ = build_rows(records, currency.get_display_currency())
    cols = _visible_columns(settings)
    filename = f"account_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    safe_filename = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
    output_path = output_path or os.path.join(_report_dir(), safe_filename)
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
        statement_text = (r.get("print_description") or r.get("notes") or "").strip()
        if r.get("source_ref"):
            reference = str(r.get("source_ref"))
        else:
            reference = str(r.get("id") or "")
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
            "description": statement_text,
            "person_name": str(r.get("person_name") or ""),
            "service_type": str(r.get("service_type") or ""),
            "debit": debit,
            "credit": credit,
            "running_balance": _money(currency.convert(running_usd, "USD", display_currency), display_currency),
        })
    return rows, {"total_debit_usd": total_debit_usd, "total_credit_usd": total_credit_usd, "net_usd": total_debit_usd - total_credit_usd}


def export_reconciliation_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None, *, show_person: bool = True, show_service: bool = True) -> str:
    """External-facing statement for company reconciliation.

    This deliberately uses print_description and hides internal supplier/client
    profit notes. It is suitable for WhatsApp or formal matching with a partner.
    """
    settings = get_report_settings()
    info = get_company_info()
    display_currency = currency.get_display_currency()
    rows, totals = build_reconciliation_rows(records, display_currency)
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = f"reconciliation_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    safe_filename = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
    output_path = output_path or os.path.join(_report_dir(), safe_filename)
    header_lines = [info.get("address"), info.get("phone"), info.get("email"), info.get("tax_number")]
    logo_uri = image_to_data_uri(info.get("logo_path") or "") if settings.get("show_company_logo", True) else None
    logo_html = f"<img src='{logo_uri}' class='company-logo' alt='logo'>" if logo_uri else ""
    header_meta = " | ".join(_safe(x) for x in header_lines if x)
    total_debit = _money(currency.convert(totals["total_debit_usd"], "USD", display_currency), display_currency)
    total_credit = _money(currency.convert(totals["total_credit_usd"], "USD", display_currency), display_currency)
    net_label = _statement_balance_label(totals["net_usd"], display_currency)
    person_th = "<th>الزبون / المسافر</th>" if show_person else ""
    service_th = "<th>الخدمة / البنود</th>" if show_service else ""
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f"<td>{_safe(row['date'])}</td>"
            f"<td>{_safe(row['reference'])}</td>"
            f"<td>{_safe(row['description'])}</td>"
            + (f"<td>{_safe(row['person_name'])}</td>" if show_person else "")
            + (f"<td>{_safe(row['service_type'])}</td>" if show_service else "")
            + f"<td class='money debit'>{_safe(row['debit'])}</td>"
            + f"<td class='money credit'>{_safe(row['credit'])}</td>"
            + f"<td class='money'>{_safe(row['running_balance'])}</td>"
            + "</tr>"
        )
    colspan = 6 + (1 if show_person else 0) + (1 if show_service else 0)
    if not body_rows:
        body_rows.append(f"<tr><td colspan='{colspan}' class='empty'>لا توجد حركات ضمن هذا الحساب</td></tr>")
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>كشف مطابقة - {_safe(company_name)}</title>
<style>
@page {{ size:A4; margin:13mm; }} body {{ font-family:Tahoma,Arial,sans-serif; direction:rtl; margin:0; color:#111827; }} .sheet {{ max-width:1120px; margin:0 auto; padding:18px; }}
.top {{ display:flex; justify-content:space-between; gap:15px; border-bottom:3px solid #1e3a8a; padding-bottom:12px; margin-bottom:14px; }} .brand-wrap {{ display:flex; gap:12px; align-items:center; }}
.company-logo {{ width:74px; height:74px; object-fit:contain; border:1px solid #e5e7eb; border-radius:14px; padding:4px; }} h1 {{ margin:0; font-size:24px; color:#1e3a8a; }} p {{ margin:4px 0; color:#4b5563; font-size:12px; }}
.badge {{ background:#eff6ff; color:#1e40af; padding:10px 14px; border-radius:12px; font-weight:bold; align-self:flex-start; }} .title {{ text-align:center; margin:12px 0 16px; }} .title h2 {{ margin:0; font-size:22px; }}
.note {{ border:1px solid #bfdbfe; background:#eff6ff; color:#1e3a8a; padding:10px; border-radius:12px; margin-bottom:12px; font-size:12px; }} .summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:14px; }} .metric {{ border:1px solid #e5e7eb; border-radius:12px; background:#f9fafb; padding:10px; }} .metric small {{ color:#6b7280; display:block; }} .metric strong {{ font-size:16px; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; }} th {{ background:#1e3a8a; color:#fff; padding:8px 6px; font-size:12px; border:1px solid #1e3a8a; }} td {{ border:1px solid #d1d5db; padding:7px 6px; font-size:12px; vertical-align:top; word-wrap:break-word; }} tr:nth-child(even) td {{ background:#f9fafb; }} .money {{ direction:ltr; unicode-bidi:embed; white-space:nowrap; }} .debit {{ color:#047857; }} .credit {{ color:#b91c1c; }} .empty {{ text-align:center; color:#6b7280; padding:22px; }}
.footer {{ margin-top:16px; border-top:1px solid #d1d5db; padding-top:10px; color:#6b7280; font-size:11px; display:flex; justify-content:space-between; gap:16px; }} @media print {{ .sheet {{ padding:0; }} }}
</style></head><body><div class="sheet">
<div class="top"><div class="brand-wrap">{logo_html}<div><h1>{_safe(info.get('name'))}</h1><p>{header_meta}</p></div></div><div class="badge">{_safe(company_name)}</div></div>
<div class="title"><h2>كشف حساب للمطابقة</h2><p>تاريخ الإنشاء: {_safe(generated_at)} | العملة المعروضة: {_safe(display_currency)}</p></div>
<div class="note">لنا = مبالغ مستحقة لنا على الحساب. له = مبالغ مستحقة للحساب علينا أو مدفوعة منه. هذا الكشف مخصص للمطابقة ولا يُعد مخالصة نهائية إلا بعد التأكيد.</div>
<div class="summary"><div class="metric"><small>لنا</small><strong>{_safe(total_debit)}</strong></div><div class="metric"><small>له</small><strong>{_safe(total_credit)}</strong></div><div class="metric"><small>النتيجة</small><strong>{_safe(net_label)}</strong></div></div>
<table><thead><tr><th>التاريخ</th><th>المرجع</th><th>البيان</th>{person_th}{service_th}<th>لنا</th><th>له</th><th>الرصيد</th></tr></thead><tbody>{''.join(body_rows)}</tbody></table>
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
        rows.append(f"<tr><td>{_safe(c.get('date'))}</td><td>{_safe(c.get('reference'))}</td><td>{_safe(c.get('person_name'))}</td><td>{_safe(c.get('client_company_name'))}</td><td>{_safe(c.get('supplier_company_name'))}</td><td>{service_cell}</td><td>{_safe(_money(currency.convert(sale,'USD',display_currency),display_currency))}</td><td>{_safe(_money(currency.convert(cost,'USD',display_currency),display_currency))}</td><td>{_safe(_money(currency.convert(profit,'USD',display_currency),display_currency))}</td><td>{_safe(c.get('status'))}</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='10' class='empty'>لا توجد ملفات خدمات</td></tr>")
    filename = f"service_profit_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), filename)
    doc = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>تقرير أرباح الخدمات</title><style>body{{font-family:Tahoma,Arial;direction:rtl;color:#111827}}.sheet{{padding:20px;max-width:1200px;margin:auto}}h1{{color:#1e3a8a}}table{{width:100%;border-collapse:collapse}}th{{background:#1e3a8a;color:#fff;padding:8px;border:1px solid #1e3a8a}}td{{border:1px solid #d1d5db;padding:7px;font-size:12px}}.summary{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:12px;margin:12px 0}}.empty{{text-align:center;color:#6b7280}}</style></head><body><div class="sheet"><h1>{_safe(info.get('name'))}</h1><h2>تقرير أرباح الخدمات الداخلي</h2><div class="summary">إجمالي الربح: <strong>{_safe(_money(currency.convert(total_profit,'USD',display_currency),display_currency))}</strong></div><table><thead><tr><th>التاريخ</th><th>المرجع</th><th>الزبون</th><th>العميل</th><th>المورد</th><th>الخدمة</th><th>البيع</th><th>التكلفة</th><th>الربح</th><th>الحالة</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path
