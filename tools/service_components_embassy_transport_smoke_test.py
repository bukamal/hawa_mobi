# -*- coding: utf-8 -*-
"""Smoke test for Phase 70 service components: embassy fees and ground transport."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_service_components_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db

    ensure_db()
    from auth.session import UserSession
    from database import ExpenseRepository, ServiceCaseRepository
    from reports.account_statement import (
        export_reconciliation_statement_html,
        export_service_profit_report_html,
    )

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    service_repo = ServiceCaseRepository()
    result = service_repo.add(
        {
            "client_company_name": "بلو ستار",
            "supplier_company_name": "سيف الشام",
            "person_name": "أحمد محمد",
            "service_type": "تأشيرة سياحية",
            "currency_original": "USD",
            "date": "2026-07-12",
            "notes": "اختبار بنود متعددة",
            "components": [
                {
                    "service_type": "تأشيرة سياحية",
                    "supplier_company_name": "سيف الشام",
                    "sale_amount_original": 150,
                    "cost_amount_original": 120,
                },
                {
                    "service_type": "سفارة / رسوم سفارة",
                    "supplier_company_name": "رسوم سفارات",
                    "sale_amount_original": 45,
                    "cost_amount_original": 40,
                },
                {
                    "service_type": "نقل بري",
                    "supplier_company_name": "شركة نقل الشام",
                    "sale_amount_original": 25,
                    "cost_amount_original": 20,
                },
            ],
        }
    )
    assert result["reference"].startswith("SVC-"), result
    assert len(result.get("supplier_expense_ids") or []) == 3, result

    repo = ExpenseRepository()
    client_rows = repo.get_by_company("بلو ستار", convert_to_display=False)
    visa_rows = repo.get_by_company("سيف الشام", convert_to_display=False)
    embassy_rows = repo.get_by_company("رسوم سفارات", convert_to_display=False)
    transport_rows = repo.get_by_company("شركة نقل الشام", convert_to_display=False)

    assert len(client_rows) == 1, client_rows
    assert float(client_rows[0]["amount_original"]) == 220.0, client_rows[0]
    assert "تأشيرة سياحية" in client_rows[0]["print_description"], client_rows[0][
        "print_description"
    ]
    assert "سفارة" in client_rows[0]["print_description"], client_rows[0][
        "print_description"
    ]
    assert "نقل بري" in client_rows[0]["print_description"], client_rows[0][
        "print_description"
    ]
    assert len(visa_rows) == 1 and float(visa_rows[0]["amount_original"]) == 120.0
    assert len(embassy_rows) == 1 and float(embassy_rows[0]["amount_original"]) == 40.0
    assert (
        len(transport_rows) == 1 and float(transport_rows[0]["amount_original"]) == 20.0
    )

    cases = service_repo.list_cases()
    assert cases and len(cases[0].get("components") or []) == 3, cases
    assert abs(float(cases[0]["sale_amount_original"]) - 220.0) < 0.01
    assert abs(float(cases[0]["cost_amount_original"]) - 180.0) < 0.01

    rec = export_reconciliation_statement_html("بلو ستار", client_rows)
    rec_html = Path(rec).read_text(encoding="utf-8")
    assert "كشف حساب للمطابقة" in rec_html
    assert "220" in rec_html
    assert (
        "سيف الشام" not in rec_html
    )  # customer statement must not expose suppliers/profit

    profit = export_service_profit_report_html(cases)
    profit_html = Path(profit).read_text(encoding="utf-8")
    assert "تقرير أرباح الخدمات الداخلي" in profit_html
    assert "شركة نقل الشام" in profit_html
    assert "رسوم سفارات" in profit_html

    print("service_components_embassy_transport_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
