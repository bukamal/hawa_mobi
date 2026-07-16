# -*- coding: utf-8 -*-
"""Autocomplete suggestions used by Android form fields.

The functions are intentionally small and repository-based so they work for
local SQLite and REST mode.  They only return text suggestions; typing a new
company/person remains allowed.
"""
from __future__ import annotations

from typing import Iterable, List

from database import ExpenseRepository
from services.company_search_service import normalize_search_text
from services.ledger_operation_service import SERVICE_TYPES


def _clean(value) -> str:
    return str(value or "").strip()


def _dedupe_sorted(values: Iterable[str], limit: int = 120) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in values:
        value = _clean(raw)
        if not value:
            continue
        key = normalize_search_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    out.sort(key=lambda v: normalize_search_text(v))
    return out[: max(1, int(limit or 120))]


def list_company_names(limit: int = 200) -> List[str]:
    try:
        rows = ExpenseRepository().get_all(convert_to_display=False)
    except Exception:
        rows = []
    names = []
    for row in rows:
        names.append(row.get("company_name"))
        names.append(row.get("linked_company_name"))
        names.append(row.get("counterparty_company_name"))
    return _dedupe_sorted(names, limit=limit)


def list_person_names(company_name: str | None = None, limit: int = 200) -> List[str]:
    try:
        rows = ExpenseRepository().get_all(convert_to_display=False)
    except Exception:
        rows = []
    wanted = normalize_search_text(company_name or "")
    values = []
    for row in rows:
        if wanted and normalize_search_text(row.get("company_name")) != wanted:
            continue
        values.append(row.get("person_name"))
        values.append(row.get("person_name_search"))
    return _dedupe_sorted(values, limit=limit)


def list_service_types(limit: int = 200) -> List[str]:
    values = list(SERVICE_TYPES)
    try:
        rows = ExpenseRepository().get_all(convert_to_display=False)
        values.extend(row.get("service_type") for row in rows)
    except Exception:
        pass
    return _dedupe_sorted(values, limit=limit)
