# -*- coding: utf-8 -*-
"""Report configuration helpers.

The report layer is intentionally data-driven: screens choose a report type,
while columns/header/footer are resolved here from app configuration.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

from config import _load_config, _save_config

ACCOUNT_STATEMENT_DEFAULT_COLUMNS: List[Dict[str, object]] = [
    {"key": "date", "label": "التاريخ", "visible": True, "width": "12%"},
    {"key": "notes", "label": "الملاحظات", "visible": True, "width": "34%"},
    {"key": "debit", "label": "لنا", "visible": True, "width": "14%"},
    {"key": "credit", "label": "له", "visible": True, "width": "14%"},
    {"key": "running_balance", "label": "التراكمي", "visible": True, "width": "14%"},
    {"key": "person_name", "label": "الزبون/المسافر", "visible": False, "width": "14%"},
    {"key": "service_type", "label": "نوع الخدمة", "visible": False, "width": "12%"},
    {"key": "operation_type", "label": "نوع العملية", "visible": False, "width": "12%"},
    # Optional business columns. They are kept disabled by default and can be
    # activated later without changing the report engine.
    {"key": "currency", "label": "العملة", "visible": False, "width": "8%"},
    {"key": "historical_currency_value", "label": "القيمة التاريخية للعملة", "visible": False, "width": "14%"},
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
    # Preserve valid custom columns appended by future versions/settings.
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
