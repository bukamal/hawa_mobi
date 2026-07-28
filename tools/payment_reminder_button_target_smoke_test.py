#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression test: reminder.id must never be used as the payment expense ID."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HAWAA_DATA_DIR", tempfile.mkdtemp(prefix="hawaa-payment-button-"))

from database.migrations import ensure_db
from database.repositories.expense_repo import ExpenseRepository
from database.repositories.payment_repo import PaymentRepository
from services.payment_target_service import normalize_payment_target, resolve_payment_expense_id


def main():
    ensure_db()
    expenses = ExpenseRepository()
    payments = PaymentRepository()

    # Create ordinary claims first so expense IDs advance while reminder IDs do
    # not.  This reproduces the Android failure where reminder.id=1 but the
    # actual target expense.id is larger.
    decoy_ids = [
        expenses.add(
            f"شركة وهمية {idx}", 50, "incoming", "2026-07-01", "تمهيد", "USD", 1,
            is_settleable=True,
        )
        for idx in range(1, 4)
    ]
    target_id = expenses.add(
        "شركة الاختبار", 1000, "incoming", "2026-07-28", "قيد مستحق", "USD", 1,
        payment_due_date="2026-08-15", payment_note="اختبار زر الدفع",
        person_name="أحمد", service_type="قيد عادي", is_settleable=True,
    )

    rows = expenses.get_pending_payment_reminders()
    row = next(item for item in rows if int(item["expense_id"]) == target_id)
    assert int(row["id"]) != target_id, (row["id"], target_id)
    assert int(row["id"]) in decoy_ids, "The fixture must expose the old wrong-target bug"

    assert resolve_payment_expense_id(row) == target_id
    target = normalize_payment_target(row)
    assert target["id"] == target_id
    assert target["expense_id"] == target_id
    assert target["reminder_id"] == int(row["id"])

    result = payments.add(target["id"], 250, date="2026-07-28", payment_method="cash")
    assert abs(float(result["paid_amount_original"]) - 250) < 0.01
    assert abs(float(result["remaining_amount_original"]) - 750) < 0.01

    # The claim whose ID equals reminder.id must remain untouched.
    decoy_summary = payments.get_summary(int(row["id"]))
    assert abs(float(decoy_summary["paid_amount_original"])) < 0.01

    dialog_source = (ROOT / "views" / "dialogs" / "payment_dialog.py").read_text(encoding="utf-8")
    screen_source = (ROOT / "views" / "payment_reminders_mobile_view.py").read_text(encoding="utf-8")
    assert "normalize_payment_target(expense)" in dialog_source
    assert "normalize_payment_target(record)" in screen_source
    assert "تعذر فتح نافذة تسجيل الدفعة" in screen_source

    print("payment_reminder_button_target_smoke_test passed")
    print(f"reminder_id={row['id']} expense_id={target_id} paid=250 remaining=750")


if __name__ == "__main__":
    main()
