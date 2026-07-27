#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 108 integration test for multi-claim payment allocation and credits."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase108-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from database.migrations import ensure_db
from database.connection import DatabaseConnection
from database.repositories.expense_repo import ExpenseRepository
from database.repositories.payment_repo import PaymentRepository
from database.repositories.batch_payment_repo import BatchPaymentRepository
from database.repositories.direct_service_repo import DirectServiceRepository
from database.repositories.service_case_repo import ServiceCaseRepository


def approx(value, expected, eps=0.01):
    assert abs(float(value) - float(expected)) <= eps, (value, expected)


def main():
    ensure_db()
    conn = DatabaseConnection().get_connection()
    expenses = ExpenseRepository()
    payments = PaymentRepository()
    batches = BatchPaymentRepository()

    normal_id = expenses.add(
        "شركة النور", 500, "incoming", "2026-07-01", "رسوم إدارية", "USD", 1,
        payment_due_date="2026-07-05", person_name="أحمد", service_type="قيد عادي",
        initial_paid_amount=100,
    )
    direct = DirectServiceRepository().add({
        "company_name": "شركة النور", "person_name": "أحمد", "service_type": "فندق",
        "sale_amount_original": 1000, "cost_amount_original": 700,
        "supplier_company_name": "فندق المدينة", "currency_original": "USD",
        "date": "2026-07-02", "client_paid_amount": 200, "supplier_paid_amount": 0,
        "client_due_date": "2026-07-06", "supplier_due_date": "2026-07-10",
    })
    case = ServiceCaseRepository().add({
        "client_company_name": "شركة النور", "person_name": "أحمد",
        "service_type": "ملف سفر", "currency_original": "USD", "date": "2026-07-03",
        "client_due_date": "2026-07-08",
        "components": [
            {"service_type": "تأشيرة", "supplier_company_name": "مكتب التأشيرات", "sale_amount_original": 1500, "cost_amount_original": 900},
        ],
    })

    # Automatic company-level receipt: oldest claims first.
    first = batches.add({
        "company_name": "شركة النور", "person_name": "", "direction": "received",
        "amount": 1000, "currency_original": "USD", "date": "2026-07-04",
        "payment_method": "bank_transfer", "allocation_mode": "oldest",
    })
    approx(first["allocated_amount_original"], 1000)
    approx(first["credit_amount_original"], 0)
    assert len(first["allocations"]) == 2
    approx(payments.get_summary(normal_id)["remaining_amount_original"], 0)
    approx(payments.get_summary(direct["client_expense_id"])["remaining_amount_original"], 200)
    approx(payments.get_summary(case["client_expense_id"])["remaining_amount_original"], 1500)

    # An allocation inside a batch cannot be deleted alone.
    one_payment_id = first["allocations"][0]["payment_id"]
    try:
        payments.delete(one_payment_id, reason="يجب أن يفشل")
        raise AssertionError("Expected batch payment deletion guard")
    except ValueError as exc:
        assert "دفعة مجمعة" in str(exc)

    # Manual allocation with an excess amount creates customer credit.
    second = batches.add({
        "company_name": "شركة النور", "person_name": "أحمد", "direction": "received",
        "amount": 500, "currency_original": "USD", "date": "2026-07-05",
        "payment_method": "cash", "allocation_mode": "manual",
        "allocations": [
            {"expense_id": direct["client_expense_id"], "amount": 200},
            {"expense_id": case["client_expense_id"], "amount": 200},
        ],
    })
    approx(second["allocated_amount_original"], 400)
    approx(second["credit_amount_original"], 100)
    credit = conn.execute("SELECT * FROM expenses WHERE id=?", (second["credit_expense_id"],)).fetchone()
    assert credit and credit["type"] == "outgoing" and credit["source_type"] == "customer_credit"
    approx(credit["amount_original"], 100)
    approx(payments.get_summary(case["client_expense_id"])["remaining_amount_original"], 1300)

    # Supplier payments use the opposite direction and can also be batched.
    supplier_batch = batches.add({
        "company_name": "فندق المدينة", "direction": "paid", "amount": 900,
        "currency_original": "USD", "date": "2026-07-06", "allocation_mode": "oldest",
    })
    approx(supplier_batch["allocated_amount_original"], 700)
    approx(supplier_batch["credit_amount_original"], 200)
    supplier_credit = conn.execute("SELECT * FROM expenses WHERE id=?", (supplier_batch["credit_expense_id"],)).fetchone()
    assert supplier_credit and supplier_credit["type"] == "incoming" and supplier_credit["source_type"] == "supplier_advance"

    # Deleting a service that received allocations keeps the batch cash intact:
    # removed allocations are moved back to party credit.
    DirectServiceRepository().delete(direct["reference"], user_id=1, reason="إلغاء الحجز")
    first_after = batches.get(first["id"])
    second_after = batches.get(second["id"])
    approx(first_after["allocated_amount_original"], 400)
    approx(first_after["credit_amount_original"], 600)
    approx(second_after["allocated_amount_original"], 200)
    approx(second_after["credit_amount_original"], 300)
    assert not any(int(a["target_expense_id"]) == int(direct["client_expense_id"]) for a in first_after["allocations"])

    # Party credit is a normal settleable claim: it may be refunded later.
    credit_summary = payments.get_summary(second_after["credit_expense_id"])
    approx(credit_summary["remaining_amount_original"], 300)
    payments.add(second_after["credit_expense_id"], 50, date="2026-07-07", payment_method="bank_transfer")
    try:
        batches.delete(second["id"], reason="يجب أن يفشل بعد استخدام الرصيد")
        raise AssertionError("Expected used-credit deletion guard")
    except ValueError as exc:
        assert "الرصيد الدائن" in str(exc)

    # Deleting a whole batch reverses all its allocations and removes unused credit.
    restored_before = payments.get_summary(normal_id)
    approx(restored_before["remaining_amount_original"], 0)
    batches.delete(first["id"], reason="إلغاء حوالة مجمعة")
    restored_after = payments.get_summary(normal_id)
    approx(restored_after["remaining_amount_original"], 400)
    assert conn.execute("SELECT id FROM payment_batches WHERE id=?", (first["id"],)).fetchone() is None

    # Manual allocation cannot exceed the cash movement or a claim's remaining balance.
    try:
        batches.add({
            "company_name": "شركة النور", "person_name": "أحمد", "direction": "received",
            "amount": 100, "currency_original": "USD", "date": "2026-07-07",
            "allocation_mode": "manual",
            "allocations": [{"expense_id": case["client_expense_id"], "amount": 150}],
        })
        raise AssertionError("Expected manual allocation validation")
    except ValueError as exc:
        assert "أكبر من مبلغ الدفعة" in str(exc)

    print("PHASE108_BATCH_PAYMENTS_ALLOCATIONS_OK")
    print(f"database={DATA_DIR / 'hawaa_data.db'}")
    print("automatic=oldest-first; manual=multiple claims; excess=party credit")


if __name__ == "__main__":
    main()
