# -*- coding: utf-8 -*-
"""Unified modern statement export templates for Android/Flet.

Phase 76 restores the business columns users need for reconciliation while
keeping the reports readable on phones.  No column is silently removed: columns
are either displayed as table columns, detail chips, or movement-card fields
according to the selected layout mode.
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

LAYOUT_FULL = "full_table"
LAYOUT_COMPACT = "compact_table"
LAYOUT_CARDS = "cards"
VALID_LAYOUTS = {LAYOUT_FULL, LAYOUT_COMPACT, LAYOUT_CARDS}

RECONCILIATION_EXPLANATORY_NOTE = (
    "لنا = مبالغ مستحقة لنا على الحساب. "
    "له = مبالغ مستحقة للحساب علينا أو مدفوعة منه. "
    "هذا الكشف مخصص للمطابقة ولا يُعد مخالصة نهائية إلا بعد التأكيد."
)


def _safe(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _money(amount, code) -> str:
    try:
        return currency.format_amount_full(float(amount or 0), code)
    except Exception:
        return f"{float(amount or 0):,.2f} {code}"


def _money_span(value: str, extra_class: str = "") -> str:
    cls = f"money {extra_class}".strip()
    return f"<span class='{cls}'>{_safe(value)}</span>" if value else "<span class='money muted'>—</span>"


def _ltr(value) -> str:
    return f"<span class='ltr'>{_safe(value)}</span>" if value not in (None, "") else ""


def _visible_columns(settings: Dict[str, object]) -> List[Dict[str, object]]:
    return [c for c in settings.get("account_statement_columns", []) if c.get("visible", True)]


def _columns_by_key(settings: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    return {str(c.get("key")): c for c in settings.get("account_statement_columns", []) if c.get("key")}


def _is_visible(settings: Dict[str, object], key: str) -> bool:
    col = _columns_by_key(settings).get(key)
    return bool(col.get("visible", True)) if col else False


def _layout_mode(settings: Dict[str, object], key: str, fallback: str) -> str:
    mode = str(settings.get(key) or fallback).strip()
    return mode if mode in VALID_LAYOUTS else fallback


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


def _ref_value(ref: object, settings: Dict[str, object], *, force_full: bool = False) -> str:
    raw = str(ref or "").strip()
    if force_full:
        return raw
    if settings.get("shorten_long_references", False):
        return _short_ref(raw)
    return raw


def _full_ref(record: Dict) -> str:
    return str(record.get("source_ref") or record.get("reference") or record.get("id") or "").strip()


def _print_description(record: Dict) -> str:
    return str(record.get("print_description") or record.get("notes") or "").strip()


def _header_html(info: Dict, *, company_name: str, statement_kind: str, settings: Dict) -> str:
    logo_uri = image_to_data_uri(info.get("logo_path") or "") if settings.get("show_company_logo", True) else None
    logo_html = f"<img src='{logo_uri}' class='company-logo' alt='logo'>" if logo_uri else ""
    contact = ""
    if settings.get("show_company_contact", True):
        address = _safe(info.get("address") or "")
        phone = _ltr(info.get("phone") or "")
        email = _ltr(info.get("email") or "")
        contact_bits = [x for x in (address, phone, email) if x]
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


def _base_css(*, compact: bool, use_colors: bool = True) -> str:
    color_rules = ".debit{color:#1FA56A}.credit{color:#E54848}.balance{color:#0A3F70}" if use_colors else ".debit,.credit,.balance{color:#172033}"
    return f"""
@page {{ size:A4; margin:12mm; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#f8fafc; color:#172033; direction:rtl; font-family:Tahoma,Arial,system-ui,sans-serif; }}
.sheet {{ max-width:{'860px' if compact else '1120px'}; margin:0 auto; padding:18px; background:#fff; }}
.report-header {{ border-bottom:3px solid #0A3F70; padding-bottom:14px; margin-bottom:18px; position:relative; }}
.brand-block {{ display:flex; align-items:center; justify-content:center; gap:18px; text-align:center; }}
.brand-text h1 {{ margin:0; color:#0A3F70; font-size:28px; line-height:1.35; }}
.company-logo {{ width:64px; height:64px; object-fit:contain; border:1px solid #e5e7eb; border-radius:14px; background:#fff; padding:4px; flex:0 0 auto; }}
.contact-line {{ color:#4b5563; font-size:13px; line-height:1.8; margin-top:5px; }}
.statement-kind {{ color:#4b5563; font-size:12px; margin-top:4px; }}
.account-badge {{ position:absolute; left:0; top:0; background:#EAF4FF; color:#0A3F70; border-radius:12px; padding:9px 13px; font-weight:700; max-width:145px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.title {{ text-align:center; margin:16px 0 14px; }}
.title h2 {{ margin:0 0 7px; font-size:25px; color:#172033; }}
.title .meta {{ color:#6b7280; font-size:13px; }}
.account-line {{ font-size:16px; font-weight:700; color:#0A3F70; margin-top:4px; }}
.summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:14px 0; }}
.metric {{ border:1px solid #e5e7eb; border-radius:14px; padding:12px; background:#f9fafb; text-align:center; min-height:78px; }}
.metric small {{ display:block; color:#6b7280; margin-bottom:7px; }}
.metric strong {{ display:block; font-size:20px; line-height:1.35; }}
.final-metric strong {{ font-size:16px; }}
.note {{ border:1px solid #B8D7F2; background:#EAF4FF; color:#0A3F70; padding:11px 13px; border-radius:14px; margin:12px 0; font-size:13px; line-height:1.75; }}
.money,.ltr,.ref {{ direction:ltr; unicode-bidi:isolate; white-space:nowrap; display:inline-block; }}
.muted {{ color:#9ca3af; }}
{color_rules}
.footer {{ margin-top:18px; border-top:1px solid #d1d5db; padding-top:10px; color:#6b7280; font-size:11px; display:flex; justify-content:space-between; gap:16px; }}
.empty {{ text-align:center; color:#6b7280; padding:22px; border:1px dashed #d1d5db; border-radius:14px; }}
.table-scroll {{ width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:14px; border:1px solid #d1d5db; }}
.modern-table {{ width:100%; border-collapse:collapse; min-width:760px; background:#fff; }}
.modern-table th {{ background:#0A3F70; color:#fff; padding:10px 8px; border:1px solid #0A3F70; font-size:13px; white-space:nowrap; }}
.modern-table td {{ border:1px solid #d1d5db; padding:9px 8px; font-size:12px; vertical-align:top; line-height:1.7; }}
.modern-table tr:nth-child(even) td {{ background:#f9fafb; }}
.statement-main {{ font-weight:700; line-height:1.65; }}
.statement-meta {{ margin-top:6px; color:#6b7280; font-size:11px; display:flex; flex-wrap:wrap; gap:5px 9px; }}
.statement-meta span {{ background:#f3f4f6; border-radius:999px; padding:2px 7px; }}
.ref-cell {{ max-width:150px; overflow-wrap:anywhere; }}
@media (max-width:640px) {{
  .sheet {{ padding:14px 12px; }}
  .brand-block {{ justify-content:flex-start; text-align:right; gap:12px; }}
  .brand-text h1 {{ font-size:24px; }}
  .company-logo {{ width:58px; height:58px; }}
  .account-badge {{ position:static; display:inline-block; margin-bottom:10px; max-width:100%; }}
  .summary {{ grid-template-columns:1fr; }}
  .modern-table th,.modern-table td {{ font-size:11px; padding:8px 6px; }}
}}
@media print {{ body {{ background:#fff; }} .sheet {{ padding:0; max-width:none; }} .table-scroll {{ overflow:visible; border:none; }} .modern-table {{ min-width:0; }} }}
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


def build_reconciliation_rows(records: Iterable[Dict], display_currency: str | None = None) -> Tuple[List[Dict[str, str]], Dict[str, float]]:
    display_currency = display_currency or currency.get_display_currency()
    approved = [r for r in records if r.get("status") != "waiting_payment"]
    return build_rows(approved, display_currency)


def _summary_values(totals: Dict[str, float], display_currency: str) -> Tuple[str, str, str]:
    total_debit = _money(currency.convert(totals["total_debit_usd"], "USD", display_currency), display_currency)
    total_credit = _money(currency.convert(totals["total_credit_usd"], "USD", display_currency), display_currency)
    net = _money(currency.convert(totals["net_usd"], "USD", display_currency), display_currency)
    return total_debit, total_credit, net


def _column_value(row: Dict[str, str], key: str, settings: Dict[str, object], *, force_full_ref: bool = False) -> str:
    if key == "date":
        return _ltr(row.get("date"))
    if key == "reference":
        ref = _ref_value(row.get("reference"), settings, force_full=force_full_ref)
        return f"<span class='ref'>{_safe(ref)}</span>" if ref else ""
    if key in {"debit", "credit", "running_balance"}:
        extra = {"debit": "debit", "credit": "credit", "running_balance": "balance"}.get(key, "")
        return _money_span(row.get(key, ""), extra)
    if key == "notes":
        return _safe(row.get("description") or row.get("notes") or "")
    return _safe(row.get(key, ""))


def _detail_chips(row: Dict[str, str], settings: Dict[str, object], *, exclude_keys: set[str] | None = None, force_full_ref: bool = False) -> str:
    exclude_keys = exclude_keys or set()
    chips: List[str] = []
    def add(label: str, value: str, *, ltr: bool = False):
        if value:
            val = f"<span class='ltr'>{_safe(value)}</span>" if ltr else _safe(value)
            chips.append(f"<span>{_safe(label)}: {val}</span>")

    if _is_visible(settings, "reference") and "reference" not in exclude_keys:
        add("المرجع", _ref_value(row.get("reference"), settings, force_full=force_full_ref), ltr=True)
    if _is_visible(settings, "person_name") and "person_name" not in exclude_keys:
        add("الزبون", row.get("person_name") or "")
    if _is_visible(settings, "service_type") and "service_type" not in exclude_keys:
        add("الخدمة", row.get("service_type") or "")
    if _is_visible(settings, "operation_type") and "operation_type" not in exclude_keys:
        add("نوع العملية", row.get("operation_type") or "")
    if _is_visible(settings, "currency") and "currency" not in exclude_keys:
        add("العملة", row.get("currency") or "", ltr=True)
    if _is_visible(settings, "historical_currency_value") and "historical_currency_value" not in exclude_keys:
        add("القيمة التاريخية للعملة", row.get("historical_currency_value") or "", ltr=True)
    if _is_visible(settings, "status") and "status" not in exclude_keys:
        add("الحالة", row.get("status") or "")
    if _is_visible(settings, "due_date") and "due_date" not in exclude_keys:
        add("تاريخ الاستحقاق", row.get("due_date") or "", ltr=True)
    return "".join(chips)


def _statement_balance_label(net_usd: float, display_currency: str) -> str:
    value = _money(abs(currency.convert(net_usd, "USD", display_currency)), display_currency)
    if net_usd > 0:
        return f"الرصيد النهائي لصالح {get_company_info().get('name')}: {value}"
    if net_usd < 0:
        return f"الرصيد النهائي لصالح الحساب المقابل: {value}"
    return "الرصيد النهائي: مطابق / لا يوجد رصيد"


def _render_summary(totals: Dict[str, float], display_currency: str, settings: Dict[str, object], *, reconciliation: bool) -> str:
    if not settings.get("show_statement_summary", True):
        return ""
    total_debit, total_credit, net = _summary_values(totals, display_currency)
    final = _statement_balance_label(totals["net_usd"], display_currency) if reconciliation else net
    return (
        "<div class='summary'>"
        f"<div class='metric'><small>لنا</small><strong>{_money_span(total_debit,'debit')}</strong></div>"
        f"<div class='metric'><small>له</small><strong>{_money_span(total_credit,'credit')}</strong></div>"
        f"<div class='metric final-metric'><small>{'النتيجة' if reconciliation else 'الصافي التراكمي'}</small><strong>{_safe(final) if reconciliation else _money_span(final,'balance')}</strong></div>"
        "</div>"
    )


def _render_full_table(rows: List[Dict[str, str]], settings: Dict[str, object], *, force_full_ref: bool, title_prefix: str = "") -> str:
    cols = _visible_columns(settings)
    if not cols:
        cols = [
            {"key": "date", "label": "التاريخ"},
            {"key": "notes", "label": "البيان"},
            {"key": "debit", "label": "لنا"},
            {"key": "credit", "label": "له"},
            {"key": "running_balance", "label": "الرصيد"},
        ]
    headers = "".join(f"<th>{_safe(c.get('label', c.get('key')))}</th>" for c in cols)
    body = []
    for row in rows:
        cells = []
        for c in cols:
            key = str(c.get("key"))
            cls = "statement-cell" if key == "notes" else ("ref-cell" if key == "reference" else "")
            value = _column_value(row, key, settings, force_full_ref=force_full_ref)
            cells.append(f"<td class='{cls}'>{value}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    if not body:
        body.append(f"<tr><td colspan='{len(cols)}' class='empty'>لا توجد حركات</td></tr>")
    return f"<div class='table-scroll {title_prefix}'><table class='modern-table full-table'><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def _render_compact_table(rows: List[Dict[str, str]], settings: Dict[str, object], *, force_full_ref: bool) -> str:
    body = []
    for row in rows:
        meta_html = _detail_chips(row, settings, exclude_keys={"date", "notes", "debit", "credit", "running_balance"}, force_full_ref=force_full_ref)
        statement = _safe(row.get("description") or row.get("notes") or "حركة حساب")
        body.append(
            "<tr>"
            f"<td class='date-cell'>{_ltr(row.get('date'))}</td>"
            f"<td class='statement-cell'><div class='statement-main'>{statement}</div><div class='statement-meta'>{meta_html}</div></td>"
            f"<td>{_money_span(row.get('debit'), 'debit')}</td>"
            f"<td>{_money_span(row.get('credit'), 'credit')}</td>"
            f"<td>{_money_span(row.get('running_balance'), 'balance')}</td>"
            "</tr>"
        )
    if not body:
        body.append("<tr><td colspan='5' class='empty'>لا توجد حركات</td></tr>")
    return (
        "<div class='table-scroll compact-statement'>"
        "<table class='modern-table compact-table'><thead><tr>"
        "<th>التاريخ</th><th>البيان والتفاصيل</th><th>لنا</th><th>له</th><th>الرصيد</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _render_cards(rows: List[Dict[str, str]], settings: Dict[str, object], *, force_full_ref: bool) -> str:
    cards = []
    for i, row in enumerate(rows, start=1):
        meta_html = _detail_chips(row, settings, force_full_ref=force_full_ref)
        cards.append(f"""
<section class="movement statement-card">
  <div class="movement-head"><span class="idx">#{i}</span><span class="date">{_ltr(row.get('date'))}</span></div>
  <div class="movement-desc">{_safe(row.get('description') or row.get('notes') or 'حركة حساب')}</div>
  <div class="movement-meta statement-meta">{meta_html}</div>
  <div class="movement-money">
    <div><small>لنا</small><strong>{_money_span(row.get('debit'), 'debit')}</strong></div>
    <div><small>له</small><strong>{_money_span(row.get('credit'), 'credit')}</strong></div>
    <div><small>الرصيد</small><strong>{_money_span(row.get('running_balance'), 'balance')}</strong></div>
  </div>
</section>
""")
    if not cards:
        cards.append("<div class='empty'>لا توجد حركات ضمن هذا الحساب</div>")
    return f"<div class='movements'>{''.join(cards)}</div>"


def _render_body(rows: List[Dict[str, str]], settings: Dict[str, object], *, layout_mode: str, force_full_ref: bool) -> str:
    if layout_mode == LAYOUT_FULL:
        return _render_full_table(rows, settings, force_full_ref=force_full_ref)
    if layout_mode == LAYOUT_CARDS:
        return _render_cards(rows, settings, force_full_ref=force_full_ref)
    return _render_compact_table(rows, settings, force_full_ref=force_full_ref)


def _statement_css(settings: Dict[str, object], *, compact: bool) -> str:
    return _base_css(compact=compact, use_colors=bool(settings.get("statement_use_colors", True))) + """
.date-cell { width:78px; }
.compact-table { min-width:720px; }
.compact-table .statement-cell { width:auto; }
.full-table { min-width:980px; }
.movements { display:flex; flex-direction:column; gap:10px; }
.movement { border:1px solid #d1d5db; border-radius:16px; padding:12px; background:#fff; page-break-inside:avoid; }
.movement:nth-child(even) { background:#f9fafb; }
.movement-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; color:#6b7280; }
.idx { background:#EAF4FF; color:#0A3F70; border-radius:999px; padding:3px 8px; font-weight:700; }
.date { font-weight:700; color:#374151; }
.movement-desc { font-size:15px; font-weight:700; line-height:1.65; margin-bottom:6px; }
.movement-meta { display:flex; flex-wrap:wrap; gap:5px 7px; margin-bottom:10px; color:#4b5563; font-size:12px; }
.movement-money { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; }
.movement-money div { border:1px solid #e5e7eb; border-radius:12px; padding:8px; background:#fff; text-align:center; min-width:0; }
.movement-money small { display:block; color:#6b7280; margin-bottom:5px; }
.movement-money strong { font-size:14px; }
@media (max-width:640px) { .movement-money { grid-template-columns:1fr; } .movement-desc { font-size:14px; } }
"""


def _render_document(company_name: str, rows: List[Dict[str, str]], totals: Dict[str, float], *, statement_kind: str, title: str, reconciliation: bool, layout_mode: str, output_path: str) -> str:
    settings = get_report_settings()
    info = get_company_info()
    display_currency = currency.get_display_currency()
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    force_full_ref = not bool(settings.get("shorten_long_references", False)) or layout_mode == LAYOUT_FULL
    compact = layout_mode != LAYOUT_FULL
    note_text = RECONCILIATION_EXPLANATORY_NOTE if reconciliation and settings.get("show_reconciliation_note", True) else ""
    note_html = f"<div class='note'>{_safe(note_text)}</div>" if note_text else ""
    body = _render_body(rows, settings, layout_mode=layout_mode, force_full_ref=force_full_ref)
    footer_note = _safe("يرجى مراجعة الكشف وإبلاغنا بأي اختلاف خلال 48 ساعة." if reconciliation else settings.get("footer_note", "هذا الكشف صادر آلياً من نظام هوى الشام."))
    meta = f"تاريخ الإنشاء: {_ltr(generated_at)} | العملة المعروضة: {_ltr(display_currency)}" if settings.get("show_generated_at", True) else f"العملة المعروضة: {_ltr(display_currency)}"
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_safe(title)} - {_safe(company_name)}</title>
<style>{_statement_css(settings, compact=compact)}</style></head><body><div class="sheet">
{_header_html(info, company_name=company_name, statement_kind=statement_kind, settings=settings)}
<div class="title"><h2>{_safe(title)}</h2><div class="account-line">الحساب: {_safe(company_name)}</div><div class="meta">{meta}</div></div>
{note_html}
{_render_summary(totals, display_currency, settings, reconciliation=reconciliation)}
{body}
<div class="footer"><span>{footer_note}</span><span>{_safe(info.get('name'))}</span></div>
</div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


def export_account_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None, *, layout_mode: str | None = None) -> str:
    settings = get_report_settings()
    display_currency = currency.get_display_currency()
    rows, totals = build_rows(records, display_currency)
    mode = layout_mode if layout_mode in VALID_LAYOUTS else _layout_mode(settings, "print_statement_layout_mode", LAYOUT_FULL)
    filename = f"account_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), _safe_filename(filename))
    return _render_document(company_name, rows, totals, statement_kind="كشف حساب تفصيلي", title="كشف حساب شركة", reconciliation=False, layout_mode=mode, output_path=output_path)


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


def export_reconciliation_statement_html(company_name: str, records: Iterable[Dict], output_path: str | None = None, *, show_person: bool = True, show_service: bool = True, layout_mode: str | None = None) -> str:
    settings = get_report_settings()
    display_currency = currency.get_display_currency()
    rows, totals = build_reconciliation_rows(records, display_currency)
    # Preserve legacy flags by temporarily hiding relevant columns only for this render.
    if not show_person or not show_service:
        settings = dict(settings)
        cols = []
        for col in settings.get("account_statement_columns", []):
            item = dict(col)
            if not show_person and item.get("key") == "person_name":
                item["visible"] = False
            if not show_service and item.get("key") == "service_type":
                item["visible"] = False
            cols.append(item)
        settings["account_statement_columns"] = cols
    mode = layout_mode if layout_mode in VALID_LAYOUTS else _layout_mode(settings, "reconciliation_layout_mode", LAYOUT_COMPACT)
    filename = f"reconciliation_statement_{company_name}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = output_path or os.path.join(_report_dir(), _safe_filename(filename))
    # _render_document loads settings again; pass through the user's saved settings by writing is not desirable.
    # The show_person/show_service legacy flags are rarely used; render directly here when they alter settings.
    if show_person and show_service:
        return _render_document(company_name, rows, totals, statement_kind="كشف حساب للمطابقة", title="كشف حساب للمطابقة", reconciliation=True, layout_mode=mode, output_path=output_path)
    info = get_company_info()
    generated_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    force_full_ref = not bool(settings.get("shorten_long_references", False)) or mode == LAYOUT_FULL
    body = _render_body(rows, settings, layout_mode=mode, force_full_ref=force_full_ref)
    note_text = RECONCILIATION_EXPLANATORY_NOTE if settings.get("show_reconciliation_note", True) else ""
    note_html = f"<div class='note'>{_safe(note_text)}</div>" if note_text else ""
    display_currency = currency.get_display_currency()
    doc = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>كشف مطابقة - {_safe(company_name)}</title><style>{_statement_css(settings, compact=(mode != LAYOUT_FULL))}</style></head><body><div class="sheet">{_header_html(info, company_name=company_name, statement_kind='كشف حساب للمطابقة', settings=settings)}<div class="title"><h2>كشف حساب للمطابقة</h2><div class="account-line">الحساب: {_safe(company_name)}</div><div class="meta">تاريخ الإنشاء: {_ltr(generated_at)} | العملة المعروضة: {_ltr(display_currency)}</div></div>{note_html}{_render_summary(totals, display_currency, settings, reconciliation=True)}{body}<div class="footer"><span>يرجى مراجعة الكشف وإبلاغنا بأي اختلاف خلال 48 ساعة.</span><span>{_safe(info.get('name'))}</span></div></div></body></html>"""
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
        service_cell = (_safe(str(c.get("service_type") or "")) + (f"<br><small>{_safe(component_summary)}</small>" if component_summary else ""))
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
    settings = get_report_settings()
    css = _base_css(compact=False, use_colors=bool(settings.get("statement_use_colors", True))) + "table{width:100%;border-collapse:collapse;min-width:980px}th{background:#0A3F70;color:#fff;padding:8px;border:1px solid #0A3F70}td{border:1px solid #d1d5db;padding:7px;font-size:12px;vertical-align:top}.summary-box{background:#EAF4FF;border:1px solid #B8D7F2;border-radius:12px;padding:12px;margin:12px 0}"
    doc = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>تقرير أرباح الخدمات</title><style>{css}</style></head><body><div class="sheet">{_header_html(info, company_name='داخلي', statement_kind='تقرير أرباح الخدمات', settings={'show_company_logo': True, 'show_company_contact': True})}<div class="title"><h2>تقرير أرباح الخدمات الداخلي</h2></div><div class="summary-box">إجمالي الربح: <strong>{_money_span(_money(currency.convert(total_profit,'USD',display_currency),display_currency),'balance')}</strong></div><div class='table-scroll'><table><thead><tr><th>التاريخ</th><th>المرجع</th><th>الزبون</th><th>العميل</th><th>المورد</th><th>الخدمة</th><th>البيع</th><th>التكلفة</th><th>الربح</th><th>الحالة</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div></body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path
