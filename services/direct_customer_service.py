# -*- coding: utf-8 -*-
"""Direct customer service workflow helpers.

A direct service stores sale, cost and profit for a direct passenger/customer.

Two accounting modes are supported:
- classic mode: a sale is posted to a customer/company account and an optional
  supplier payable is posted when a separate supplier is chosen.
- supplier-only mode: the selected company is the supplier/source of the service
  (for example ticket issuer); only the supplier cost is posted to that company
  as payable, while sale/profit remain internal direct-service metadata.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict

from services.ledger_operation_service import clean_text, normalize_service_type

DIRECT_SERVICE_REF_PREFIX = "DIR"
DIRECT_SERVICE_STATUS_OPEN = "open"
DIRECT_SERVICE_STATUS_REVERSED = "reversed"

DIRECT_SERVICE_SOURCE_CLIENT = "direct_service_client"
DIRECT_SERVICE_SOURCE_SUPPLIER = "direct_service_supplier"
DIRECT_SERVICE_REVERSAL = "direct_service_reversal"

DIRECT_SERVICE_OPERATION_CLIENT = "direct_service_client"
DIRECT_SERVICE_OPERATION_SUPPLIER = "direct_service_supplier"
DIRECT_SERVICE_OPERATION_REVERSAL = "direct_service_reversal"


def new_direct_service_reference() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{DIRECT_SERVICE_REF_PREFIX}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def parse_amount(value: Any, label: str, *, allow_zero: bool = True) -> float:
    try:
        amount = float(str(value or "0").replace("٬", "").replace(",", ".").strip() or 0)
    except Exception:
        raise ValueError(f"{label} غير صالح")
    if amount < 0:
        raise ValueError(f"{label} لا يمكن أن يكون سالباً")
    if not allow_zero and amount <= 0:
        raise ValueError(f"{label} يجب أن يكون أكبر من صفر")
    return amount


def validate_direct_service_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    supplier_only = bool(data.get("supplier_only") or data.get("direct_supplier_only"))
    company = clean_text(data.get("company_name") or data.get("client_company_name"))
    person = clean_text(data.get("person_name"))
    service = normalize_service_type(data.get("service_type") or "خدمة")
    sale = parse_amount(data.get("sale_amount_original", data.get("sale_amount", 0)), "سعر البيع", allow_zero=False)
    cost = parse_amount(data.get("cost_amount_original", data.get("cost_amount", 0)), "التكلفة", allow_zero=True)
    supplier = clean_text(data.get("supplier_company_name") or data.get("supplier"))
    currency_code = clean_text(data.get("currency_original") or data.get("currency") or "USD").upper()
    date = clean_text(data.get("date")) or datetime.datetime.now().strftime("%Y-%m-%d")
    notes = clean_text(data.get("notes"))
    print_description = clean_text(data.get("print_description")) or f"{service} - {person}".strip(" -")

    if not company:
        raise ValueError("الشركة / الحساب مطلوب")
    if not person:
        raise ValueError("اسم الزبون / المسافر مطلوب")
    if not currency_code:
        currency_code = "USD"

    if supplier_only:
        # In the Android card workflow the selected company is the supplier/source
        # of the direct service.  There is no second supplier field and no customer
        # company receivable row; the sale/profit are internal, while the cost is
        # posted as a payable to this selected company.
        supplier = company
    else:
        if supplier and supplier == company:
            raise ValueError("لا يمكن أن يكون حساب المورد هو نفس حساب العميل")
        if cost > 0 and not supplier:
            # Cost can remain internal without a supplier only when the user chooses
            # not to create a payable.  Keep it valid; reports still calculate profit.
            supplier = ""

    return {
        "company_name": company,
        "person_name": person,
        "service_type": service,
        "sale_amount_original": sale,
        "cost_amount_original": cost,
        "supplier_company_name": supplier,
        "currency_original": currency_code,
        "date": date[:10],
        "notes": notes,
        "print_description": print_description,
        "supplier_only": supplier_only,
    }


def client_note(reference: str, payload: Dict[str, Any]) -> str:
    extra = f". {payload.get('notes')}" if payload.get("notes") else ""
    return f"{payload.get('print_description') or payload.get('service_type')}. المرجع {reference}{extra}".strip()


def supplier_note(reference: str, payload: Dict[str, Any]) -> str:
    extra = f". {payload.get('notes')}" if payload.get("notes") else ""
    if payload.get("supplier_only"):
        return f"تكلفة {payload.get('service_type') or 'خدمة'} مباشرة للزبون {payload.get('person_name')}. المرجع {reference}{extra}".strip()
    return f"تكلفة {payload.get('service_type') or 'خدمة'} - {payload.get('person_name')} لصالح {payload.get('company_name')}. المرجع {reference}{extra}".strip()


def internal_note(reference: str, payload: Dict[str, Any], sale_base: float, cost_base: float) -> str:
    account_label = "المورد" if payload.get("supplier_only") else "الحساب"
    return (
        f"خدمة مباشرة {reference} | {account_label}: {payload.get('company_name')} | الزبون: {payload.get('person_name')} | "
        f"الخدمة: {payload.get('service_type')} | بيع USD: {float(sale_base or 0):.2f} | "
        f"تكلفة USD: {float(cost_base or 0):.2f} | ربح USD: {float(sale_base or 0) - float(cost_base or 0):.2f}"
    )
