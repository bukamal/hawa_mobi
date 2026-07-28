# -*- coding: utf-8 -*-
"""Helpers for resolving the ledger claim targeted by a payment UI action.

Reminder rows have their own primary key in ``id`` and expose the actual ledger
claim as ``expense_id``.  Ordinary ledger rows instead use ``id`` directly.
Keeping this normalization in one place prevents a reminder ID from being
mistaken for an expense ID when opening the payment dialog.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping


def resolve_payment_expense_id(record: Mapping[str, Any] | None) -> int:
    """Return the actual settleable expense ID from any supported UI record.

    Resolution order is deliberate:
    ``expense_id`` (payment reminder/API rows), ``target_expense_id`` (payment
    rows), then ``id`` (ordinary expense rows).
    """
    data = record or {}
    raw = data.get("expense_id") or data.get("target_expense_id") or data.get("id")
    try:
        expense_id = int(raw or 0)
    except (TypeError, ValueError):
        expense_id = 0
    if expense_id <= 0:
        raise ValueError("تعذر تحديد القيد المرتبط بالدفعة")
    return expense_id


def normalize_payment_target(record: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Return a copy whose ``id`` and ``expense_id`` both target the claim.

    When the source is a reminder, its original ``id`` is preserved under
    ``reminder_id`` so notification and reminder workflows retain their key.
    """
    data: Dict[str, Any] = dict(record or {})
    expense_id = resolve_payment_expense_id(data)
    original_id = data.get("id")
    if data.get("expense_id") and original_id is not None:
        try:
            if int(original_id) != expense_id:
                data.setdefault("reminder_id", int(original_id))
        except (TypeError, ValueError):
            data.setdefault("reminder_id", original_id)
    data["id"] = expense_id
    data["expense_id"] = expense_id
    return data
