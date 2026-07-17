# -*- coding: utf-8 -*-
"""Ledger operation helpers.

This layer keeps the old expenses table backward-compatible while adding
structured fields for travel/passenger/customer workflows. Old rows remain
normal posted entries; new rows can carry person/service/operation metadata.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from services.company_search_service import normalize_search_text

NORMAL_OPERATION = "normal"
THIRD_PARTY_OPERATION = "third_party_payment"
THIRD_PARTY_REVERSAL_OPERATION = "third_party_payment_reversal"
REVERSAL_OPERATION = "reversal"
SERVICE_CASE_CLIENT_OPERATION = "service_case_client"
SERVICE_CASE_SUPPLIER_OPERATION = "service_case_supplier"
SERVICE_CASE_REVERSAL_OPERATION = "service_case_reversal"
DIRECT_SERVICE_CLIENT_OPERATION = "direct_service_client"
DIRECT_SERVICE_SUPPLIER_OPERATION = "direct_service_supplier"
DIRECT_SERVICE_REVERSAL_OPERATION = "direct_service_reversal"

# Operational visibility groups.  A reversed service operation is preserved in
# SQLite for audit, but the original and reversal ledger rows must disappear
# together from company screens, statements, normal reports and balance totals.
SERVICE_CASE_SOURCE_TYPES = {
    SERVICE_CASE_CLIENT_OPERATION,
    SERVICE_CASE_SUPPLIER_OPERATION,
    SERVICE_CASE_REVERSAL_OPERATION,
}
DIRECT_SERVICE_SOURCE_TYPES = {
    DIRECT_SERVICE_CLIENT_OPERATION,
    DIRECT_SERVICE_SUPPLIER_OPERATION,
    DIRECT_SERVICE_REVERSAL_OPERATION,
}
SERVICE_OPERATION_SOURCE_TYPES = SERVICE_CASE_SOURCE_TYPES | DIRECT_SERVICE_SOURCE_TYPES
SERVICE_OPERATION_REVERSAL_TYPES = {
    SERVICE_CASE_REVERSAL_OPERATION,
    DIRECT_SERVICE_REVERSAL_OPERATION,
}

SERVICE_TYPES = [
    "غير محدد",
    "تذكرة سفر",
    "حجز فندق",
    "فيزا",
    "تأشيرة سياحية",
    "سفارة / رسوم سفارة",
    "نقل بري",
    "رسوم",
    "تسديد",
    "سداد بالنيابة",
    "مرتجع",
    "عمولة",
    "تحويل ذمة",
    "متعدد الخدمات",
    "أخرى",
]

OPERATION_TYPES = [
    NORMAL_OPERATION,
    "ticket",
    "booking",
    "visa",
    "fee",
    "embassy_fee",
    "ground_transport",
    "payment",
    THIRD_PARTY_OPERATION,
    THIRD_PARTY_REVERSAL_OPERATION,
    "liability_transfer",
    REVERSAL_OPERATION,
    SERVICE_CASE_CLIENT_OPERATION,
    SERVICE_CASE_SUPPLIER_OPERATION,
    SERVICE_CASE_REVERSAL_OPERATION,
    DIRECT_SERVICE_CLIENT_OPERATION,
    DIRECT_SERVICE_SUPPLIER_OPERATION,
    DIRECT_SERVICE_REVERSAL_OPERATION,
    "other",
]

OPERATION_LABELS = {
    NORMAL_OPERATION: "قيد عادي",
    "ticket": "تذكرة / حجز",
    "booking": "حجز",
    "visa": "فيزا",
    "fee": "رسوم",
    "embassy_fee": "سفارة / رسوم سفارة",
    "ground_transport": "نقل بري",
    "payment": "تسديد",
    THIRD_PARTY_OPERATION: "سداد بالنيابة",
    THIRD_PARTY_REVERSAL_OPERATION: "عكس سداد بالنيابة",
    "liability_transfer": "تحويل ذمة",
    REVERSAL_OPERATION: "عكس قيد",
    SERVICE_CASE_CLIENT_OPERATION: "خدمة وسيطة - عميل",
    SERVICE_CASE_SUPPLIER_OPERATION: "خدمة وسيطة - مورد",
    SERVICE_CASE_REVERSAL_OPERATION: "عكس خدمة وسيطة",
    DIRECT_SERVICE_CLIENT_OPERATION: "خدمة مباشرة - عميل",
    DIRECT_SERVICE_SUPPLIER_OPERATION: "خدمة مباشرة - مورد",
    DIRECT_SERVICE_REVERSAL_OPERATION: "عكس خدمة مباشرة",
    "other": "أخرى",
}

SERVICE_TO_OPERATION = {
    "غير محدد": NORMAL_OPERATION,
    "تذكرة سفر": "ticket",
    "حجز فندق": "booking",
    "فيزا": "visa",
    "تأشيرة سياحية": "visa",
    "سفارة / رسوم سفارة": "embassy_fee",
    "نقل بري": "ground_transport",
    "رسوم": "fee",
    "تسديد": "payment",
    "سداد بالنيابة": THIRD_PARTY_OPERATION,
    "مرتجع": REVERSAL_OPERATION,
    "عمولة": "fee",
    "تحويل ذمة": "liability_transfer",
    "متعدد الخدمات": "other",
    "أخرى": "other",
}


def clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_service_type(value: Any) -> str:
    value = clean_text(value)
    return value if value in SERVICE_TYPES else "غير محدد"


def normalize_operation_type(value: Any, service_type: Any = None, source_type: Any = None) -> str:
    source = clean_text(source_type)
    if source in {THIRD_PARTY_OPERATION, THIRD_PARTY_REVERSAL_OPERATION, SERVICE_CASE_CLIENT_OPERATION, SERVICE_CASE_SUPPLIER_OPERATION, SERVICE_CASE_REVERSAL_OPERATION, DIRECT_SERVICE_CLIENT_OPERATION, DIRECT_SERVICE_SUPPLIER_OPERATION, DIRECT_SERVICE_REVERSAL_OPERATION}:
        return source
    value = clean_text(value)
    if value in OPERATION_TYPES:
        return value
    return SERVICE_TO_OPERATION.get(normalize_service_type(service_type), NORMAL_OPERATION)


def is_generated_source(source_type: Any) -> bool:
    return clean_text(source_type) in {THIRD_PARTY_OPERATION, THIRD_PARTY_REVERSAL_OPERATION, SERVICE_CASE_CLIENT_OPERATION, SERVICE_CASE_SUPPLIER_OPERATION, SERVICE_CASE_REVERSAL_OPERATION, DIRECT_SERVICE_CLIENT_OPERATION, DIRECT_SERVICE_SUPPLIER_OPERATION, DIRECT_SERVICE_REVERSAL_OPERATION}


def is_locked_payload(data: Dict[str, Any]) -> int:
    if int(data.get("is_locked") or 0):
        return 1
    return 1 if is_generated_source(data.get("source_type")) else 0


def normalize_expense_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    person = clean_text(out.get("person_name"))
    service = normalize_service_type(out.get("service_type"))
    operation = normalize_operation_type(out.get("operation_type"), service, out.get("source_type"))
    out["person_name"] = person
    out["person_name_search"] = normalize_search_text(person)
    out["service_type"] = service
    out["operation_type"] = operation
    out["is_locked"] = is_locked_payload(out)
    if out.get("reversal_of") in ("", None):
        out["reversal_of"] = None
    if out.get("reversed_by") in ("", None):
        out["reversed_by"] = None
    return out


def operation_label(value: Any) -> str:
    return OPERATION_LABELS.get(clean_text(value), clean_text(value) or OPERATION_LABELS[NORMAL_OPERATION])

def is_service_operation_source(source_type: Any) -> bool:
    """Return True for generated service/direct-service ledger rows."""
    return clean_text(source_type) in SERVICE_OPERATION_SOURCE_TYPES


def reversed_service_references(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    """Collect service references that have a generated reversal ledger row.

    This works in local and REST/client modes because the reversal marker lives
    in the expenses payload itself.  It also supports historical databases that
    predate explicit ``reversed_by`` links.
    """
    refs: Set[str] = set()
    for row in rows or []:
        source_type = clean_text((row or {}).get("source_type"))
        source_ref = clean_text((row or {}).get("source_ref"))
        if source_ref and source_type in SERVICE_OPERATION_REVERSAL_TYPES:
            refs.add(source_ref)
    return refs


def is_operationally_hidden_service_entry(row: Dict[str, Any], reversed_refs: Set[str] | None = None) -> bool:
    """Whether a ledger row belongs to a fully reversed service operation."""
    row = row or {}
    source_type = clean_text(row.get("source_type"))
    source_ref = clean_text(row.get("source_ref"))
    if not source_ref or source_type not in SERVICE_OPERATION_SOURCE_TYPES:
        return False
    refs = reversed_refs or set()
    return source_ref in refs


def filter_operational_expenses(rows: Iterable[Dict[str, Any]], *, include_reversed: bool = False) -> List[Dict[str, Any]]:
    """Return expense rows suitable for operational screens and totals.

    When a service case or direct/quick service is reversed, both its original
    rows and its reversal rows are omitted.  The raw rows remain available by
    passing ``include_reversed=True`` for the dedicated audit/reversal report.
    Third-party payment reversals are intentionally unchanged.
    """
    materialized = list(rows or [])
    if include_reversed:
        return materialized
    refs = reversed_service_references(materialized)
    if not refs:
        return materialized
    return [
        row for row in materialized
        if not is_operationally_hidden_service_entry(row, refs)
    ]
