# -*- coding: utf-8 -*-
"""Lookup/search helpers for financial input fields.

Companies in the current data model are ledger account names, while people are
operational names stored on entries/service cases.  Keep lookup logic here so
all dialogs use the same normalization and ranking rules.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List

from services.company_search_service import normalize_search_text
from services.ledger_operation_service import SERVICE_TYPES

LookupOption = Dict[str, Any]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _tokens(query: str) -> List[str]:
    return [t for t in normalize_search_text(query).split(" ") if t]


def _matches(value: Any, query: str) -> bool:
    tokens = _tokens(query)
    if not tokens:
        return True
    haystack = normalize_search_text(value)
    return all(t in haystack for t in tokens)


def _score(value: str, query: str, usage: int = 0) -> tuple:
    norm = normalize_search_text(value)
    q = normalize_search_text(query)
    if not q:
        rank = 0
    elif norm == q:
        rank = 4
    elif norm.startswith(q):
        rank = 3
    elif q in norm:
        rank = 2
    else:
        rank = 1
    return (rank, int(usage or 0), value)


def _rows_from_expenses() -> List[Dict[str, Any]]:
    try:
        from database import ExpenseRepository
        return ExpenseRepository().get_all(convert_to_display=False)
    except Exception:
        return []


def _rows_from_service_cases() -> List[Dict[str, Any]]:
    try:
        from database import ServiceCaseRepository
        return ServiceCaseRepository().list_cases()
    except Exception:
        return []


def _add_company(bucket: Dict[str, Dict[str, Any]], name: Any, *, role: str = "", company: str = "", date: str = "") -> None:
    name = _clean(name)
    if not name:
        return
    key = normalize_search_text(name)
    if not key:
        return
    item = bucket.setdefault(key, {
        "value": name,
        "label": name,
        "subtitle": "",
        "kind": "company",
        "usage_count": 0,
        "last_date": "",
        "roles": set(),
        "companies": set(),
    })
    item["usage_count"] += 1
    if date and str(date) > str(item.get("last_date") or ""):
        item["last_date"] = str(date)
    if role:
        item["roles"].add(role)
    if company and company != name:
        item["companies"].add(company)


def search_company_options(query: str = "", limit: int = 8) -> List[LookupOption]:
    """Return financial-account suggestions from ledger and service data."""
    query = _clean(query)
    bucket: Dict[str, Dict[str, Any]] = {}
    for row in _rows_from_expenses():
        _add_company(bucket, row.get("company_name"), role="حساب", date=row.get("date"))
        _add_company(bucket, row.get("counterparty_company_name"), role="طرف مقابل", company=row.get("company_name"), date=row.get("date"))
        _add_company(bucket, row.get("linked_company_name"), role="مرتبط", company=row.get("company_name"), date=row.get("date"))
    for case in _rows_from_service_cases():
        _add_company(bucket, case.get("client_company_name"), role="عميل خدمة", date=case.get("date"))
        _add_company(bucket, case.get("supplier_company_name"), role="مورد خدمة", company=case.get("client_company_name"), date=case.get("date"))
        for comp in case.get("components") or []:
            _add_company(bucket, comp.get("supplier_company_name"), role="مورد بند", company=case.get("client_company_name"), date=case.get("date"))
    options = [dict(v) for v in bucket.values() if _matches(v.get("value"), query)]
    for opt in options:
        roles = "، ".join(sorted(opt.pop("roles", set())))
        peers = "، ".join(sorted(list(opt.pop("companies", set())))[:2])
        details = []
        if roles:
            details.append(roles)
        if peers:
            details.append(f"مرتبط بـ {peers}")
        if opt.get("usage_count"):
            details.append(f"{opt.get('usage_count')} حركة")
        opt["subtitle"] = " · ".join(details)
    options.sort(key=lambda o: _score(o.get("value", ""), query, int(o.get("usage_count") or 0)), reverse=True)
    return options[: max(1, int(limit or 8))]


def search_person_options(query: str = "", limit: int = 8) -> List[LookupOption]:
    """Return operational passenger/person suggestions without making them accounts."""
    query = _clean(query)
    bucket: Dict[str, Dict[str, Any]] = {}

    def add(name: Any, company: Any = "", service: Any = "", date: Any = "") -> None:
        name = _clean(name)
        if not name:
            return
        key = normalize_search_text(name)
        item = bucket.setdefault(key, {
            "value": name,
            "label": name,
            "subtitle": "",
            "kind": "person",
            "usage_count": 0,
            "companies": set(),
            "services": set(),
            "last_date": "",
        })
        item["usage_count"] += 1
        if company:
            item["companies"].add(_clean(company))
        if service:
            item["services"].add(_clean(service))
        if date and str(date) > str(item.get("last_date") or ""):
            item["last_date"] = str(date)

    for row in _rows_from_expenses():
        add(row.get("person_name"), row.get("company_name"), row.get("service_type"), row.get("date"))
    for case in _rows_from_service_cases():
        add(case.get("person_name"), case.get("client_company_name"), case.get("service_type"), case.get("date"))
    options = [dict(v) for v in bucket.values() if _matches(v.get("value"), query)]
    for opt in options:
        companies = "، ".join(sorted(list(opt.pop("companies", set())))[:2])
        services = "، ".join(sorted(list(opt.pop("services", set())))[:2])
        details = []
        if companies:
            details.append(companies)
        if services:
            details.append(services)
        if opt.get("usage_count"):
            details.append(f"{opt.get('usage_count')} خدمة/قيد")
        opt["subtitle"] = " · ".join(details)
    options.sort(key=lambda o: _score(o.get("value", ""), query, int(o.get("usage_count") or 0)), reverse=True)
    return options[: max(1, int(limit or 8))]


def search_service_type_options(query: str = "", limit: int = 8) -> List[LookupOption]:
    """Return service type suggestions from the controlled list plus history."""
    query = _clean(query)
    usage = defaultdict(int)
    for service in SERVICE_TYPES:
        service = _clean(service)
        if service:
            usage[service] += 1000
    for row in _rows_from_expenses():
        service = _clean(row.get("service_type"))
        if service and service != "غير محدد":
            usage[service] += 1
    for case in _rows_from_service_cases():
        service = _clean(case.get("service_type"))
        if service:
            usage[service] += 1
        for comp in case.get("components") or []:
            service = _clean(comp.get("service_type"))
            if service:
                usage[service] += 1
    options = []
    for service, count in usage.items():
        if not _matches(service, query):
            continue
        options.append({
            "value": service,
            "label": service,
            "subtitle": "نوع خدمة محفوظ" if count >= 1000 else f"استُخدم {count} مرة",
            "kind": "service_type",
            "usage_count": count,
        })
    options.sort(key=lambda o: _score(o.get("value", ""), query, int(o.get("usage_count") or 0)), reverse=True)
    return options[: max(1, int(limit or 8))]


def has_company_option(value: str) -> bool:
    value = _clean(value)
    if not value:
        return False
    target = normalize_search_text(value)
    return any(normalize_search_text(opt.get("value")) == target for opt in search_company_options(value, limit=25))
