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
