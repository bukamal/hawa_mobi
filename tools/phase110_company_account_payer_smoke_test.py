#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 110: the company owns the ledger; the traveler can pay on its behalf."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase110-payer-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

try:
    from auth.session import UserSession
    from database.connection import DatabaseConnection
    from database.migrations import ensure_db
    from database.repositories.batch_payment_repo import BatchPaymentRepository
    from database.repositories.direct_service_repo import DirectServiceRepository
    from database.repositories.expense_repo import ExpenseRepository
    from database.repositories.payment_repo import PaymentRepository
    from database.repositories.service_case_repo import ServiceCaseRepository
    from reports.account_statement import build_rows, export_account_statement_html

    ensure_db()
    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})
    conn = DatabaseConnection().get_connection()

    version = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()["value"]
    assert version == "27", version
    expense_cols = {r[1] for r in conn.execute("PRAGMA table_info(expenses)").fetchall()}
    payment_cols = {r[1] for r in conn.execute("PRAGMA table_info(payments)").fetchall()}
    assert {"payment_payer_type", "payment_payer_name"} <= expense_cols
    assert {"payer_type", "payer_name"} <= payment_cols

    # The financial relationship is with Blue Star. Mohammad is only the
    # beneficiary and the person who physically hands over the first payment.
    created = DirectServiceRepository().add({
        "company_name": "بلو ستار",
        "person_name": "محمد منصور",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 35,
        "cost_amount_original": 0,
        "supplier_company_name": "",
        "currency_original": "USD",
        "date": "2026-07-28",
        "client_paid_amount": 10,
        "client_payer_type": "traveler",
        "client_payer_name": "محمد منصور",
        "client_due_date": "2026-07-28",
        "payment_method": "cash",
    })
    target_id = int(created["client_expense_id"])

    target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (target_id,)).fetchone())
    assert target["company_name"] == "بلو ستار"
    assert target["person_name"] == "محمد منصور"
    assert target["type"] == "incoming"
    assert abs(float(target["amount_original"]) - 35.0) < 0.001

    payments = [dict(r) for r in conn.execute(
        "SELECT * FROM payments WHERE target_expense_id=? ORDER BY id", (target_id,)
    ).fetchall()]
    assert len(payments) == 1, payments
    payment = payments[0]
    assert payment["company_name"] == "بلو ستار"
    assert payment["person_name"] == "محمد منصور"
    assert payment["payer_type"] == "traveler"
    assert payment["payer_name"] == "محمد منصور"
    assert abs(float(payment["amount_original"]) - 10.0) < 0.001

    settlement = dict(conn.execute(
        "SELECT * FROM expenses WHERE id=?", (int(payment["ledger_expense_id"]),)
    ).fetchone())
    assert settlement["company_name"] == "بلو ستار"
    assert settlement["person_name"] == "محمد منصور"
    assert settlement["type"] == "outgoing"
    assert settlement["payment_payer_type"] == "traveler"
    assert settlement["payment_payer_name"] == "محمد منصور"
    assert settlement["print_description"] == "دفعة مستلمة من محمد منصور نيابة عن بلو ستار"

    company_rows = ExpenseRepository().get_by_company("بلو ستار", convert_to_display=False)
    assert len([r for r in company_rows if int(r.get("id") or 0) in {target_id, int(payment["ledger_expense_id"])}]) == 2
    assert not conn.execute("SELECT 1 FROM expenses WHERE company_name='محمد منصور' LIMIT 1").fetchone()

    statement_rows, totals = build_rows(company_rows, "USD")
    assert abs(totals["total_debit_usd"] - 35.0) < 0.001, totals
    assert abs(totals["total_credit_usd"] - 10.0) < 0.001, totals
    assert abs(totals["net_usd"] - 25.0) < 0.001, totals
    payer_row = next(row for row in statement_rows if row["payer_type"] == "traveler")
    assert payer_row["payer_name"] == "محمد منصور"
    assert "نيابة عن بلو ستار" in payer_row["description"]
    statement_path = DATA_DIR / "blue-star-statement.html"
    export_account_statement_html("بلو ستار", company_rows, str(statement_path), layout_mode="cards")
    statement_html = statement_path.read_text(encoding="utf-8")
    assert "دفعة مستلمة من محمد منصور نيابة عن بلو ستار" in statement_html
    assert "الدافع الفعلي" in statement_html

    summary = PaymentRepository().get_summary(target_id)
    assert abs(float(summary["paid_amount_original"]) - 10.0) < 0.001
    assert abs(float(summary["remaining_amount_original"]) - 25.0) < 0.001

    # A later payment made by the company itself still settles the same company
    # claim, while the actual payer is recorded differently.
    PaymentRepository().add(
        target_id, 5, date="2026-07-29", payer_type="company", payer_name="بلو ستار"
    )
    later = dict(conn.execute(
        "SELECT * FROM payments WHERE target_expense_id=? ORDER BY id DESC LIMIT 1", (target_id,)
    ).fetchone())
    later_ledger = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (later["ledger_expense_id"],)).fetchone())
    assert later["payer_type"] == "company"
    assert later["payer_name"] == "بلو ستار"
    assert later_ledger["company_name"] == "بلو ستار"
    assert later_ledger["print_description"] == "دفعة مستلمة من بلو ستار"

    updated_rows = ExpenseRepository().get_by_company("بلو ستار", convert_to_display=False)
    _, updated_totals = build_rows(updated_rows, "USD")
    assert abs(updated_totals["net_usd"] - 20.0) < 0.001, updated_totals

    # Normal entry: the traveler can pay the company claim without becoming a
    # separate account owner.
    normal_id = ExpenseRepository().add(
        "شركة القيد العادي", 50, "incoming", "2026-07-28", "رسوم إدارية", "USD", 1,
        person_name="زبون القيد", service_type="قيد عادي", initial_paid_amount=10,
        initial_payer_type="traveler", initial_payer_name="زبون القيد",
    )
    normal_payment = dict(conn.execute(
        "SELECT * FROM payments WHERE target_expense_id=?", (normal_id,)
    ).fetchone())
    assert normal_payment["company_name"] == "شركة القيد العادي"
    assert normal_payment["payer_type"] == "traveler"
    assert normal_payment["payer_name"] == "زبون القيد"

    # Service file: the account remains the client company and the beneficiary
    # is never promoted into a company ledger account.
    case = ServiceCaseRepository().add({
        "client_company_name": "شركة ملف الخدمة",
        "person_name": "مسافر الملف",
        "service_type": "فندق",
        "currency_original": "USD",
        "date": "2026-07-28",
        "client_paid_amount": 20,
        "client_payer_type": "other",
        "client_payer_name": "والد المسافر",
        "components": [
            {"service_type": "فندق", "supplier_company_name": "مورد الفندق", "sale_amount_original": 100, "cost_amount_original": 60},
        ],
    })
    case_payment = dict(conn.execute(
        "SELECT * FROM payments WHERE target_expense_id=?", (int(case["client_expense_id"]),)
    ).fetchone())
    assert case_payment["company_name"] == "شركة ملف الخدمة"
    assert case_payment["person_name"] == "مسافر الملف"
    assert case_payment["payer_type"] == "other"
    assert case_payment["payer_name"] == "والد المسافر"
    case_ledger = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (case_payment["ledger_expense_id"],)).fetchone())
    assert case_ledger["print_description"] == "دفعة مستلمة من والد المسافر نيابة عن شركة ملف الخدمة"
    assert not conn.execute("SELECT 1 FROM expenses WHERE company_name IN ('مسافر الملف','والد المسافر') LIMIT 1").fetchone()

    # One batch payment can be made by a traveler and allocated to several
    # claims of the same company. Every allocation remains in that company.
    batch_claim_1 = ExpenseRepository().add(
        "شركة الدفعة المجمعة", 30, "incoming", "2026-07-01", "مطالبة أولى", "USD", 1,
        person_name="مسافر الدفعة", service_type="قيد عادي",
    )
    batch_claim_2 = ExpenseRepository().add(
        "شركة الدفعة المجمعة", 40, "incoming", "2026-07-02", "مطالبة ثانية", "USD", 1,
        person_name="مسافر الدفعة", service_type="قيد عادي",
    )
    batch = BatchPaymentRepository().add({
        "company_name": "شركة الدفعة المجمعة",
        "person_name": "مسافر الدفعة",
        "direction": "received",
        "amount": 50,
        "currency_original": "USD",
        "date": "2026-07-29",
        "allocation_mode": "oldest",
        "payer_type": "traveler",
        "payer_name": "مسافر الدفعة",
    })
    assert abs(float(batch["allocated_amount_original"]) - 50.0) < 0.001, batch
    batch_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM payments WHERE batch_id=? ORDER BY id", (int(batch["id"]),)
    ).fetchall()]
    assert len(batch_rows) == 2, batch_rows
    assert {int(r["target_expense_id"]) for r in batch_rows} == {batch_claim_1, batch_claim_2}
    assert all(r["company_name"] == "شركة الدفعة المجمعة" for r in batch_rows)
    assert all(r["payer_type"] == "traveler" and r["payer_name"] == "مسافر الدفعة" for r in batch_rows)

    print("phase110_company_account_payer_smoke_test passed")
    print("company=بلو ستار; beneficiary=محمد منصور; claim=35; traveler-paid=10; company-paid=5; balance=20")
finally:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
