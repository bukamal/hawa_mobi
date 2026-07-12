# -*- coding: utf-8 -*-
"""Service-case workflow for travel agency intermediary operations.

A service case links two ledger sides with one professional reference:
- client company: the company/customer that asked Hawaa to provide the service
- supplier company: the company/vendor that actually supplies the service
- person/passenger: the end traveller/customer inside the transaction

The old expenses table remains the accounting ledger.  service_cases only ties
related entries together and exposes sale/cost/profit and reconciliation output.
"""
from __future__ import annotations

import datetime
import secrets
from typing import Any, Dict, Iterable, List

from services.ledger_operation_service import clean_text, normalize_service_type

SERVICE_CASE_SOURCE_CLIENT = "service_case_client"
SERVICE_CASE_SOURCE_SUPPLIER = "service_case_supplier"
SERVICE_CASE_REVERSAL = "service_case_reversal"
SERVICE_CASE_OPERATION_CLIENT = "service_case_client"
SERVICE_CASE_OPERATION_SUPPLIER = "service_case_supplier"
SERVICE_CASE_OPERATION_REVERSAL = "service_case_reversal"

SERVICE_CASE_STATUS_OPEN = "open"
SERVICE_CASE_STATUS_CLOSED = "closed"
SERVICE_CASE_STATUS_REVERSED = "reversed"


def new_service_case_reference(prefix: str = "SVC") -> str:
    return f"{prefix}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3).upper()}"


def parse_amount(value: Any, label: str) -> float:
    try:
        amount = float(str(value or "0").replace(",", "").strip())
    except Exception:
        raise ValueError(f"{label} غير صالح")
    if amount < 0:
        raise ValueError(f"{label} لا يمكن أن يكون سالباً")
    return amount


def validate_service_case_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    client = clean_text(data.get("client_company_name"))
    supplier = clean_text(data.get("supplier_company_name"))
    person = clean_text(data.get("person_name"))
    service = normalize_service_type(data.get("service_type") or "فيزا")
    date = clean_text(data.get("date")) or datetime.datetime.now().strftime("%Y-%m-%d")
    currency_code = clean_text(data.get("currency_original") or data.get("currency") or "USD").upper()
    notes = clean_text(data.get("notes"))
    sale = parse_amount(data.get("sale_amount_original", data.get("sale_amount", 0)), "سعر البيع")
    cost = parse_amount(data.get("cost_amount_original", data.get("cost_amount", 0)), "تكلفة المورد")
    if not client:
        raise ValueError("الشركة العميلة مطلوبة")
    if not supplier:
        raise ValueError("الشركة المورّدة مطلوبة")
    if client == supplier:
        raise ValueError("لا يمكن أن تكون الشركة العميلة والشركة المورّدة نفس الحساب")
    if not person:
        raise ValueError("اسم الزبون / المسافر مطلوب")
    if sale == 0 and cost == 0:
        raise ValueError("أدخل سعر البيع أو تكلفة المورد على الأقل")
    return {
        "client_company_name": client,
        "supplier_company_name": supplier,
        "person_name": person,
        "service_type": service,
        "sale_amount_original": sale,
        "cost_amount_original": cost,
        "currency_original": currency_code,
        "date": date,
        "notes": notes,
    }


def client_print_description(payload: Dict[str, Any]) -> str:
    return f"{payload.get('service_type') or 'خدمة'} - {payload.get('person_name') or ''}".strip(" -")


def supplier_print_description(payload: Dict[str, Any]) -> str:
    return f"تكلفة {payload.get('service_type') or 'خدمة'} - {payload.get('person_name') or ''}".strip(" -")


def internal_note(reference: str, payload: Dict[str, Any], sale_amount_base: float | None = None, cost_amount_base: float | None = None) -> str:
    profit = ""
    if sale_amount_base is not None and cost_amount_base is not None:
        profit = f" | ربح تقريبي USD: {float(sale_amount_base) - float(cost_amount_base):.2f}"
    return (
        f"ملف خدمة {reference} | العميل: {payload.get('client_company_name')} | "
        f"المورد: {payload.get('supplier_company_name')} | الزبون: {payload.get('person_name')} | "
        f"الخدمة: {payload.get('service_type')}{profit}"
    )


def build_client_note(reference: str, payload: Dict[str, Any]) -> str:
    extra = f". {payload.get('notes')}" if payload.get("notes") else ""
    return f"{client_print_description(payload)}. المرجع {reference}{extra}"


def build_supplier_note(reference: str, payload: Dict[str, Any]) -> str:
    extra = f". {payload.get('notes')}" if payload.get("notes") else ""
    return f"{supplier_print_description(payload)} لصالح {payload.get('client_company_name')}. المرجع {reference}{extra}"


def summarize_service_cases(rows: Iterable[Dict[str, Any]]) -> Dict[str, float | int]:
    total_sale = 0.0
    total_cost = 0.0
    count = 0
    open_count = 0
    for r in rows:
        count += 1
        if (r.get("status") or "open") != SERVICE_CASE_STATUS_REVERSED:
            total_sale += float(r.get("sale_amount_base") or 0)
            total_cost += float(r.get("cost_amount_base") or 0)
        if (r.get("status") or "open") == SERVICE_CASE_STATUS_OPEN:
            open_count += 1
    return {"count": count, "open_count": open_count, "sale_base": total_sale, "cost_base": total_cost, "profit_base": total_sale - total_cost}
