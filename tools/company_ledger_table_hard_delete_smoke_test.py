# -*- coding: utf-8 -*-
"""Acceptance test for company ledger table and destructive linked-operation deletion."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_company_table_delete_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)
os.environ.pop("HAWAA_SERVER_PROCESS", None)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import (
        DirectServiceRepository,
        ExpenseRepository,
        ServiceCaseRepository,
        ThirdPartyPaymentRepository,
    )

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    expense_repo = ExpenseRepository()

    # Ordinary entries remain directly deletable and never create reversals.
    ordinary_id = expense_repo.add(
        "شركة عادية", 125, "incoming", "2026-07-20", "قيد للحذف", "USD", 1
    )
    expense_repo.delete(ordinary_id, 1)
    assert not [r for r in expense_repo.get_all(convert_to_display=False) if r.get("id") == ordinary_id]

    # Direct service: delete the source operation and all client/supplier rows.
    direct_repo = DirectServiceRepository()
    direct = direct_repo.add({
        "company_name": "عميل مباشر للحذف",
        "person_name": "مسافر مباشر",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 300,
        "cost_amount_original": 210,
        "supplier_company_name": "مورد مباشر للحذف",
        "currency_original": "USD",
        "date": "2026-07-21",
        "notes": "اختبار حذف",
    })
    direct_ref = direct["reference"]
    assert len([r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == direct_ref]) == 2
    deleted_direct = direct_repo.delete(direct_ref, user_id=1, reason="إدخال مكرر")
    assert deleted_direct["deleted_expenses"] == 2
    assert not [r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == direct_ref]
    try:
        direct_repo.get_by_reference(direct_ref)
        raise AssertionError("direct service source row still exists")
    except ValueError:
        pass

    # Existing historical operations that were reversed by an older release
    # must also be removable as one complete group.
    historical = direct_repo.add({
        "company_name": "عميل تاريخي للحذف",
        "person_name": "مسافر تاريخي",
        "service_type": "حجز فندق",
        "sale_amount_original": 240,
        "cost_amount_original": 160,
        "supplier_company_name": "مورد تاريخي للحذف",
        "currency_original": "USD",
        "date": "2026-07-21",
        "notes": "عملية تاريخية",
    })
    historical_ref = historical["reference"]
    direct_repo.reverse(historical_ref, user_id=1, date="2026-07-24", reason="عكس قديم للاختبار")
    historical_rows = [
        r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True)
        if r.get("source_ref") == historical_ref
    ]
    assert len(historical_rows) == 4, historical_rows
    deleted_historical = direct_repo.delete(historical_ref, user_id=1, reason="تنظيف عملية تاريخية")
    assert deleted_historical["deleted_expenses"] == 4
    assert not [
        r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True)
        if r.get("source_ref") == historical_ref
    ]

    # Service case with multiple components: every generated supplier row and
    # the source/component records must disappear together.
    service_repo = ServiceCaseRepository()
    service = service_repo.add({
        "client_company_name": "عميل ملف للحذف",
        "supplier_company_name": "مورد أول للحذف",
        "person_name": "مسافر ملف",
        "service_type": "متعدد الخدمات",
        "sale_amount_original": 500,
        "cost_amount_original": 330,
        "currency_original": "USD",
        "date": "2026-07-22",
        "notes": "اختبار حذف متعدد",
        "components": [
            {"service_type": "فيزا", "supplier_company_name": "مورد أول للحذف", "sale_amount_original": 300, "cost_amount_original": 200},
            {"service_type": "نقل بري", "supplier_company_name": "مورد ثان للحذف", "sale_amount_original": 200, "cost_amount_original": 130},
        ],
    })
    service_ref = service["reference"]
    service_rows = [r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == service_ref]
    assert len(service_rows) == 3, service_rows
    deleted_service = service_repo.delete(service_ref, reason="ملف أضيف بالخطأ", user_id=1)
    assert deleted_service["deleted_expenses"] == 3
    assert deleted_service["deleted_components"] == 2
    assert not [r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == service_ref]
    try:
        service_repo.get_by_reference(service_ref)
        raise AssertionError("service-case source row still exists")
    except ValueError:
        pass

    # Third-party payment: both sides are deleted as one operation.
    third_repo = ThirdPartyPaymentRepository()
    third = third_repo.add_payment_on_behalf(
        "شركة دفعت للحذف", "شركة مستفيدة للحذف", 700, "USD", "2026-07-23", "اختبار", 1
    )
    third_ref = third["reference"]
    assert len([r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == third_ref]) == 2
    deleted_third = third_repo.delete_payment_on_behalf(third_ref, user_id=1, reason="عملية مكررة")
    assert deleted_third["deleted_expenses"] == 2
    assert not [r for r in expense_repo.get_all(convert_to_display=False, include_reversed=True) if r.get("source_ref") == third_ref]
    try:
        third_repo.get_by_reference(third_ref)
        raise AssertionError("third-party source row still exists")
    except ValueError:
        pass

    # No delete path may manufacture reversal rows.
    remaining = expense_repo.get_all(convert_to_display=False, include_reversed=True)
    assert not [r for r in remaining if str(r.get("source_type") or "").endswith("_reversal")], remaining

    conn = expense_repo.db.get_connection()
    audit = "\n".join(str(dict(r)) for r in conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall())
    assert "حذف خدمة مباشرة" in audit
    assert "حذف ملف خدمة" in audit
    assert "حذف سداد بالنيابة" in audit
    assert "إدخال مكرر" in audit and "ملف أضيف بالخطأ" in audit and "عملية مكررة" in audit

    company_source = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
    rest_source = (ROOT / "database" / "connection_rest.py").read_text(encoding="utf-8")
    server_source = (ROOT / "server" / "flask_server.py").read_text(encoding="utf-8")
    assert "ft.DataTable(" in company_source
    assert 'ft.DataColumn(ft.Text("لنا"' in company_source
    assert 'ft.DataColumn(ft.Text("له"' in company_source
    assert 'ft.DataColumn(ft.Text("الرصيد"' in company_source
    assert "chronological = sorted(self._all_records" in company_source
    assert 'add_action("عكس العملية"' not in company_source
    assert 'add_action("عكس ملف الخدمة"' not in company_source
    assert 'add_action("عكس الخدمة"' not in company_source
    assert "delete_direct_service" in rest_source
    assert "delete_service_case" in rest_source
    assert "delete_third_party_payment" in rest_source
    assert '@app.delete("/api/direct_services/<path:reference>")' in server_source
    assert '@app.delete("/api/service_cases/<path:reference>")' in server_source
    assert '@app.delete("/api/third_party_payments/<path:reference>")' in server_source

    print("company_ledger_table_hard_delete_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
