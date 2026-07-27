#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 107 integration smoke test for partial payments and dynamic reminders."""
from __future__ import annotations

import os
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase107-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from database.connection import DatabaseConnection
from database.migrations import ensure_db
from database.repositories.expense_repo import ExpenseRepository
from database.repositories.payment_repo import PaymentRepository
from database.repositories.direct_service_repo import DirectServiceRepository
from database.repositories.service_case_repo import ServiceCaseRepository


def approx(value, expected, eps=0.01):
    assert abs(float(value) - float(expected)) <= eps, (value, expected)


def main():
    ensure_db()
    db = DatabaseConnection()
    conn = db.get_connection()

    # Normal receivable: total 1000, paid 400, dynamic reminder for 600.
    expense_id = ExpenseRepository().add(
        "شركة عميلة", 1000, "incoming", "2026-07-27", "حجز جزئي", "USD", 1,
        payment_due_date="2026-08-15", payment_note="متابعة المسافر",
        person_name="أحمد", service_type="قيد عادي", initial_paid_amount=400,
        payment_method="cash",
    )
    summary = PaymentRepository().get_summary(expense_id)
    approx(summary["total_amount_original"], 1000)
    approx(summary["paid_amount_original"], 400)
    approx(summary["remaining_amount_original"], 600)
    assert summary["payment_status"] == "partial"
    reminders = ExpenseRepository().get_pending_payment_reminders()
    assert any(int(x["expense_id"]) == expense_id and abs(float(x["remaining_amount_original"]) - 600) < 0.01 for x in reminders)

    second = PaymentRepository().add(expense_id, 300, date="2026-08-01", payment_method="bank_transfer", reference_number="TR-300")
    approx(second["paid_amount_original"], 700)
    approx(second["remaining_amount_original"], 300)
    payments = PaymentRepository().list_for_expense(expense_id)
    assert len(payments) == 2

    # Removing one payment restores the balance; no claim mutation.
    payment_300 = next(p for p in payments if abs(float(p["amount_original"]) - 300) < 0.01)
    restored = PaymentRepository().delete(payment_300["id"], reason="اختبار تصحيح دفعة")
    approx(restored["paid_amount_original"], 400)
    approx(restored["remaining_amount_original"], 600)
    original = conn.execute("SELECT amount_original FROM expenses WHERE id=?", (expense_id,)).fetchone()
    approx(original["amount_original"], 1000)

    # Direct service: independent client receipt and supplier payment.
    direct = DirectServiceRepository().add({
        "company_name": "شركة العميل المباشر",
        "person_name": "ليلى",
        "service_type": "تذكرة",
        "sale_amount_original": 1000,
        "cost_amount_original": 700,
        "supplier_company_name": "شركة المورد المباشر",
        "currency_original": "USD",
        "date": "2026-07-27",
        "client_paid_amount": 400,
        "supplier_paid_amount": 300,
        "client_due_date": "2026-08-10",
        "supplier_due_date": "2026-08-12",
        "payment_method": "cash",
    })
    direct_full = DirectServiceRepository().get_by_reference(direct["reference"])
    client_entry = direct_full["client_entry"]
    supplier_entry = direct_full["supplier_entry"]
    approx(client_entry["paid_amount_original"], 400)
    approx(client_entry["remaining_amount_original"], 600)
    approx(supplier_entry["paid_amount_original"], 300)
    approx(supplier_entry["remaining_amount_original"], 400)

    # Service case: one client claim across multiple supplier components.
    case = ServiceCaseRepository().add({
        "client_company_name": "شركة الرحلات العميلة",
        "person_name": "محمد",
        "service_type": "فندق",
        "currency_original": "USD",
        "date": "2026-07-27",
        "client_paid_amount": 1200,
        "client_due_date": "2026-08-20",
        "payment_method": "card",
        "components": [
            {"service_type": "فندق", "supplier_company_name": "مورد الفندق", "sale_amount_original": 2000, "cost_amount_original": 1400},
            {"service_type": "نقل بري", "supplier_company_name": "مورد النقل", "sale_amount_original": 1000, "cost_amount_original": 600},
        ],
    })
    case_full = ServiceCaseRepository().get_by_reference(case["reference"])
    approx(case_full["client_entry"]["amount_original"], 3000)
    approx(case_full["client_entry"]["paid_amount_original"], 1200)
    approx(case_full["client_entry"]["remaining_amount_original"], 1800)
    assert case_full["client_entry"]["payment_status"] == "partial"

    # Completing a claim closes its open reminder dynamically.
    PaymentRepository().add(expense_id, 600, date="2026-08-15", payment_method="cash")
    complete = PaymentRepository().get_summary(expense_id)
    approx(complete["remaining_amount_original"], 0)
    assert complete["payment_status"] == "paid"
    reminders = ExpenseRepository().get_pending_payment_reminders()
    assert not any(int(x["expense_id"]) == expense_id for x in reminders)

    # A total cannot be reduced below posted payments.
    try:
        ExpenseRepository().update(expense_id, "شركة عميلة", 900, "incoming", "2026-07-27", "", "USD", 1)
        raise AssertionError("Expected total-below-paid validation")
    except ValueError as exc:
        assert "أقل من مجموع الدفعات" in str(exc)

    # Hard delete of linked operations removes payments and settlement rows too.
    direct_target_ids = [direct["client_expense_id"], direct["supplier_expense_id"]]
    direct_payment_count = conn.execute(
        "SELECT COUNT(*) c FROM payments WHERE target_expense_id IN (?,?)", direct_target_ids
    ).fetchone()["c"]
    assert direct_payment_count == 2
    DirectServiceRepository().delete(direct["reference"], user_id=1, reason="اختبار حذف العملية كاملة")
    assert conn.execute("SELECT COUNT(*) c FROM payments WHERE target_expense_id IN (?,?)", direct_target_ids).fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM expenses WHERE id IN (?,?)", direct_target_ids).fetchone()["c"] == 0

    case_target_ids = [case["client_expense_id"], *case.get("supplier_expense_ids", [])]
    ServiceCaseRepository().delete(case["reference"], reason="اختبار حذف ملف الخدمة", user_id=1)
    placeholders = ",".join("?" for _ in case_target_ids)
    assert conn.execute(f"SELECT COUNT(*) c FROM payments WHERE target_expense_id IN ({placeholders})", tuple(case_target_ids)).fetchone()["c"] == 0
    assert conn.execute(f"SELECT COUNT(*) c FROM expenses WHERE id IN ({placeholders})", tuple(case_target_ids)).fetchone()["c"] == 0

    # Settlement rows are explicitly non-settleable and cannot receive payments.
    settlement = conn.execute("SELECT * FROM expenses WHERE source_type IN ('payment_received','payment_paid') LIMIT 1").fetchone()
    assert settlement is not None and int(settlement["is_settleable"] or 0) == 0
    try:
        PaymentRepository().add(settlement["id"], 1)
        raise AssertionError("Expected non-settleable validation")
    except ValueError as exc:
        assert "غير قابل" in str(exc)

    print("PHASE107_PARTIAL_PAYMENTS_SMOKE_OK")
    print(f"database={DATA_DIR / 'hawaa_data.db'}")
    print("normal=1000/400/600 -> paid")
    print("direct=client 1000/400/600; supplier 700/300/400")
    print("service_case=3000/1200/1800")


if __name__ == "__main__":
    main()
