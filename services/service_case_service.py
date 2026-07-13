# -*- coding: utf-8 -*-
"""Service-case workflow for travel agency intermediary operations.

A service case links a client ledger side with one or more supplier/component
sides.  This supports modern travel workflows:

- client company: the company/customer that asked Hawaa to provide the service
- supplier components: visa supplier, embassy fees, ground transport, hotel, etc.
- person/passenger: the end traveller/customer inside the transaction

The old expenses table remains the accounting ledger.  service_cases and
service_case_components only tie related entries together and expose sale,
cost, profit, and reconciliation output.
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


_ARABIC_DIGITS = str.maketrans(
    {
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
    }
)


def normalize_amount_text(value: Any) -> str:
    """Normalize user-entered mobile amounts.

    Android Arabic keyboards often submit Eastern Arabic digits and Arabic
    decimal separators.  A save button must not appear dead merely because the
    user typed ١٥٠ or ١٥٠٫٥.  Keep this parser strict but locale-tolerant.
    """
    raw = str(value or "").strip().translate(_ARABIC_DIGITS)
    raw = raw.replace(" ", "").replace(" ", "")
    raw = raw.replace("٬", ",").replace("٫", ".")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "")
    elif "," in raw:
        if raw.count(",") == 1 and len(raw.rsplit(",", 1)[1]) in (1, 2, 3):
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    return raw


def parse_amount(value: Any, label: str) -> float:
    try:
        amount = float(normalize_amount_text(value))
    except Exception:
        raise ValueError(f"{label} غير صالح")
    if amount < 0:
        raise ValueError(f"{label} لا يمكن أن يكون سالباً")
    return amount


def _component_has_value(component: Dict[str, Any]) -> bool:
    if clean_text(component.get("supplier_company_name")):
        return True
    if clean_text(component.get("service_type")):
        return True
    try:
        if parse_amount(component.get("sale_amount_original", 0), "سعر البيع") != 0:
            return True
    except Exception:
        return True
    try:
        if parse_amount(component.get("cost_amount_original", 0), "التكلفة") != 0:
            return True
    except Exception:
        return True
    return False


def validate_service_component(
    component: Dict[str, Any],
    *,
    default_supplier: str = "",
    default_service: str = "تأشيرة سياحية",
    idx: int = 1,
) -> Dict[str, Any]:
    service = normalize_service_type(
        component.get("service_type") or default_service or "تأشيرة سياحية"
    )
    supplier = clean_text(
        component.get("supplier_company_name")
        or component.get("supplier")
        or default_supplier
    )
    sale = parse_amount(
        component.get("sale_amount_original", component.get("sale_amount", 0)),
        f"سعر بيع البند {idx}",
    )
    cost = parse_amount(
        component.get("cost_amount_original", component.get("cost_amount", 0)),
        f"تكلفة البند {idx}",
    )
    notes = clean_text(component.get("notes"))
    print_client = clean_text(component.get("print_description_client"))
    print_supplier = clean_text(component.get("print_description_supplier"))
    if cost > 0 and not supplier:
        raise ValueError(f"المورّد مطلوب للبند {idx}: {service}")
    if sale == 0 and cost == 0:
        raise ValueError(f"أدخل سعر بيع أو تكلفة للبند {idx}: {service}")
    return {
        "service_type": service,
        "supplier_company_name": supplier,
        "sale_amount_original": sale,
        "cost_amount_original": cost,
        "notes": notes,
        "print_description_client": print_client,
        "print_description_supplier": print_supplier,
    }


def _legacy_component_from_payload(
    data: Dict[str, Any], service: str, supplier: str, sale: float, cost: float
) -> Dict[str, Any]:
    return {
        "service_type": service,
        "supplier_company_name": supplier,
        "sale_amount_original": sale,
        "cost_amount_original": cost,
        "notes": clean_text(data.get("notes")),
        "print_description_client": "",
        "print_description_supplier": "",
    }


def validate_service_case_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    client = clean_text(data.get("client_company_name"))
    supplier = clean_text(data.get("supplier_company_name"))
    person = clean_text(data.get("person_name"))
    service = normalize_service_type(data.get("service_type") or "تأشيرة سياحية")
    date = clean_text(data.get("date")) or datetime.datetime.now().strftime("%Y-%m-%d")
    currency_code = clean_text(
        data.get("currency_original") or data.get("currency") or "USD"
    ).upper()
    notes = clean_text(data.get("notes"))

    if not client:
        raise ValueError("الشركة العميلة مطلوبة")
    if not person:
        raise ValueError("اسم الزبون / المسافر مطلوب")

    raw_components = data.get("components")
    components: List[Dict[str, Any]] = []
    if isinstance(raw_components, list) and raw_components:
        for idx, raw in enumerate(raw_components, 1):
            raw = dict(raw or {})
            if not _component_has_value(raw):
                continue
            comp = validate_service_component(
                raw, default_supplier=supplier, default_service=service, idx=idx
            )
            if (
                comp["supplier_company_name"]
                and comp["supplier_company_name"] == client
            ):
                raise ValueError(f"لا يمكن أن يكون العميل هو نفس مورّد البند {idx}")
            components.append(comp)
    else:
        if not supplier:
            raise ValueError("الشركة المورّدة مطلوبة")
        sale = parse_amount(
            data.get("sale_amount_original", data.get("sale_amount", 0)), "سعر البيع"
        )
        cost = parse_amount(
            data.get("cost_amount_original", data.get("cost_amount", 0)), "تكلفة المورد"
        )
        if client == supplier:
            raise ValueError(
                "لا يمكن أن تكون الشركة العميلة والشركة المورّدة نفس الحساب"
            )
        components.append(
            _legacy_component_from_payload(data, service, supplier, sale, cost)
        )

    if not components:
        raise ValueError("أضف بند خدمة واحد على الأقل")
    total_sale = sum(float(c.get("sale_amount_original") or 0) for c in components)
    total_cost = sum(float(c.get("cost_amount_original") or 0) for c in components)
    if total_sale == 0 and total_cost == 0:
        raise ValueError("أدخل سعر البيع أو التكلفة في بنود الخدمة")
    suppliers = [
        c["supplier_company_name"] for c in components if c.get("supplier_company_name")
    ]
    primary_supplier = suppliers[0] if suppliers else supplier
    supplier_summary = "، ".join(dict.fromkeys(suppliers))
    service_summary = summarize_component_services(components)
    stored_service_type = service_summary if len(components) == 1 else "متعدد الخدمات"

    return {
        "client_company_name": client,
        "supplier_company_name": primary_supplier,
        "supplier_summary": supplier_summary,
        "person_name": person,
        "service_type": stored_service_type,
        "service_description": service_summary,
        "primary_service_type": service,
        "sale_amount_original": total_sale,
        "cost_amount_original": total_cost,
        "currency_original": currency_code,
        "date": date,
        "notes": notes,
        "components": components,
    }


def summarize_component_services(components: Iterable[Dict[str, Any]]) -> str:
    names: List[str] = []
    for comp in components:
        name = normalize_service_type(comp.get("service_type"))
        if name and name != "غير محدد" and name not in names:
            names.append(name)
    if not names:
        return "خدمة"
    if len(names) == 1:
        return names[0]
    # Keep the printed statement compact on mobile/WhatsApp.
    return " + ".join(names)


def client_print_description(payload: Dict[str, Any]) -> str:
    service_label = (
        payload.get("service_description") or payload.get("service_type") or "خدمة"
    )
    return f"{service_label} - {payload.get('person_name') or ''}".strip(" -")


def component_client_print_description(
    payload: Dict[str, Any], component: Dict[str, Any]
) -> str:
    return (
        component.get("print_description_client")
        or f"{component.get('service_type') or 'خدمة'} - {payload.get('person_name') or ''}"
    ).strip(" -")


def supplier_print_description(
    payload: Dict[str, Any], component: Dict[str, Any] | None = None
) -> str:
    comp = component or payload
    return (
        comp.get("print_description_supplier")
        or f"تكلفة {comp.get('service_type') or 'خدمة'} - {payload.get('person_name') or ''}"
    ).strip(" -")


def internal_note(
    reference: str,
    payload: Dict[str, Any],
    sale_amount_base: float | None = None,
    cost_amount_base: float | None = None,
) -> str:
    profit = ""
    if sale_amount_base is not None and cost_amount_base is not None:
        profit = f" | ربح تقريبي USD: {float(sale_amount_base) - float(cost_amount_base):.2f}"
    components = payload.get("components") or []
    component_text = ""
    if components:
        parts = []
        for c in components:
            parts.append(
                f"{c.get('service_type')} / {c.get('supplier_company_name') or '-'} / بيع {c.get('sale_amount_original')} / تكلفة {c.get('cost_amount_original')}"
            )
        component_text = " | البنود: " + " ؛ ".join(parts)
    return (
        f"ملف خدمة {reference} | العميل: {payload.get('client_company_name')} | "
        f"الموردون: {payload.get('supplier_summary') or payload.get('supplier_company_name')} | الزبون: {payload.get('person_name')} | "
        f"الخدمة: {payload.get('service_description') or payload.get('service_type')}{profit}{component_text}"
    )


def build_client_note(reference: str, payload: Dict[str, Any]) -> str:
    extra = f". {payload.get('notes')}" if payload.get("notes") else ""
    return f"{client_print_description(payload)}. المرجع {reference}{extra}"


def build_supplier_note(
    reference: str, payload: Dict[str, Any], component: Dict[str, Any] | None = None
) -> str:
    comp = component or payload
    extra = (
        f". {comp.get('notes') or payload.get('notes')}"
        if (comp.get("notes") or payload.get("notes"))
        else ""
    )
    return f"{supplier_print_description(payload, comp)} لصالح {payload.get('client_company_name')}. المرجع {reference}{extra}"


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
    return {
        "count": count,
        "open_count": open_count,
        "sale_base": total_sale,
        "cost_base": total_cost,
        "profit_base": total_sale - total_cost,
    }
