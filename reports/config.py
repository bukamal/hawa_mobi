# -*- coding: utf-8 -*-
"""Report configuration helpers.

Phase 76 adds a unified modern statement renderer with configurable layouts.
The data contract stays backward compatible: old report settings are merged with
new defaults and no database migration is required for printing options.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

from config import _load_config, _save_config

ACCOUNT_STATEMENT_DEFAULT_COLUMNS: List[Dict[str, object]] = [
    {"key": "date", "label": "التاريخ", "visible": True, "width": "11%"},
    {"key": "notes", "label": "البيان", "visible": True, "width": "28%"},
    {"key": "debit", "label": "لنا", "visible": True, "width": "12%"},
    {"key": "credit", "label": "له", "visible": True, "width": "12%"},
    {"key": "running_balance", "label": "الرصيد", "visible": True, "width": "12%"},
    # Business context.  These remain visible by default after Phase 76 so
    # reconciliation never loses the passenger/service/reference information.
    {"key": "reference", "label": "المرجع", "visible": True, "width": "14%"},
    {"key": "person_name", "label": "الزبون / المسافر", "visible": True, "width": "14%"},
    {"key": "service_type", "label": "الخدمة / البند", "visible": True, "width": "14%"},
    {"key": "operation_type", "label": "نوع العملية", "visible": False, "width": "12%"},
    {"key": "currency", "label": "العملة", "visible": False, "width": "8%"},
    {"key": "historical_currency_value", "label": "القيمة التاريخية للعملة", "visible": False, "width": "16%"},
    {"key": "status", "label": "الحالة", "visible": False, "width": "10%"},
    {"key": "due_date", "label": "تاريخ الاستحقاق", "visible": False, "width": "12%"},
]

DEFAULT_REPORT_SETTINGS = {
    "account_statement_columns": ACCOUNT_STATEMENT_DEFAULT_COLUMNS,
    "header_enabled": True,
    "footer_enabled": True,
    "header_note": "كشف حساب تفصيلي",
    "footer_note": "هذا الكشف صادر آلياً من نظام هوى الشام.",
    "show_company_logo": True,
    "show_generated_at": True,
    "show_company_contact": True,
    "show_statement_summary": True,
    "show_reconciliation_note": True,
    "statement_use_colors": True,
    "shorten_long_references": False,
    # full_table = full accounting table with all visible columns.
    # compact_table = modern responsive table: core columns + details line.
    # cards = card layout for narrow/mobile sharing.
    "reconciliation_layout_mode": "compact_table",
    "whatsapp_statement_layout_mode": "compact_table",
    "print_statement_layout_mode": "full_table",
}


def _merge_columns(saved_columns):
    saved_by_key = {c.get("key"): c for c in saved_columns or [] if c.get("key")}
    merged = []
    for col in ACCOUNT_STATEMENT_DEFAULT_COLUMNS:
        item = deepcopy(col)
        saved = saved_by_key.get(item["key"])
        if saved:
            item.update({k: saved[k] for k in ("label", "visible", "width") if k in saved})
        merged.append(item)
    known = {c["key"] for c in merged}
    for col in saved_columns or []:
        if col.get("key") and col["key"] not in known:
            extra = deepcopy(col)
            extra.setdefault("label", str(extra["key"]))
            extra.setdefault("visible", True)
            extra.setdefault("width", "12%")
            merged.append(extra)
    return merged


def get_report_settings() -> Dict[str, object]:
    cfg = _load_config()
    raw = cfg.get("reports", {}) if isinstance(cfg.get("reports", {}), dict) else {}
    settings = deepcopy(DEFAULT_REPORT_SETTINGS)
    settings.update({k: raw[k] for k in settings.keys() if k in raw and k != "account_statement_columns"})
    settings["account_statement_columns"] = _merge_columns(raw.get("account_statement_columns"))
    return settings


def save_report_settings(settings: Dict[str, object]) -> None:
    cfg = _load_config()
    current = get_report_settings()
    current.update(settings or {})
    current["account_statement_columns"] = _merge_columns(current.get("account_statement_columns"))
    cfg["reports"] = current
    _save_config(cfg)
