# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def reset_singleton() -> None:
    from database.connection import DatabaseConnection
    try:
        DatabaseConnection().close()
    except Exception:
        pass
    DatabaseConnection._instance = None
    DatabaseConnection._local_conn = None
    try:
        DatabaseConnection._connections.clear()
    except Exception:
        pass


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hawaa_linked_svc_edit_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    try:
        reset_singleton()
        from database.migrations import init_database
        from database.connection import DatabaseConnection
        from auth.session import UserSession
        from database import ExpenseRepository, ServiceCaseRepository

        init_database()
        UserSession.login({"id": 1, "username": "admin", "role": "admin"})
        db = DatabaseConnection()
        service_repo = ServiceCaseRepository()
        expense_repo = ExpenseRepository()

        created = service_repo.add({
            "client_company_name": "بلو ستار",
            "supplier_company_name": "سيف الشام",
            "person_name": "أحمد محمد",
            "service_type": "تأشيرة سياحية",
            "currency_original": "USD",
            "date": "2026-07-10",
            "notes": "قبل التعديل",
            "components": [
                {"service_type": "تأشيرة سياحية", "supplier_company_name": "سيف الشام", "sale_amount_original": 150, "cost_amount_original": 120},
                {"service_type": "نقل بري", "supplier_company_name": "شركة النقل", "sale_amount_original": 50, "cost_amount_original": 40},
            ],
        })
        ref = created["reference"]
        original_client_id = created["client_expense_id"]
        rows = expense_repo.get_all(convert_to_display=False)
        linked = [r for r in rows if r.get("source_ref") == ref]
        assert len(linked) == 3, linked
        client = next(r for r in linked if r["source_type"] == "service_case_client")
        try:
            expense_repo.update(client["id"], client["company_name"], 999, client["type"], client["date"], "تعديل منفرد", client["currency_original"], 1)
        except ValueError as exc:
            assert "لا يُعدّل منفرد" in str(exc) or "مولّدة" in str(exc) or "مرتبط" in str(exc)
        else:
            raise AssertionError("service-case generated entries must not be editable individually")

        updated = service_repo.update_service_case(ref, {
            "client_company_name": "بلو ستار المعدلة",
            "supplier_company_name": "المورد الجديد",
            "person_name": "أحمد محمد المعدل",
            "service_type": "تأشيرة سياحية",
            "currency_original": "USD",
            "date": "2026-07-12",
            "notes": "بعد التعديل",
            "components": [
                {"service_type": "تأشيرة سياحية", "supplier_company_name": "المورد الجديد", "sale_amount_original": 180, "cost_amount_original": 130},
                {"service_type": "سفارة / رسوم سفارة", "supplier_company_name": "رسوم سفارات", "sale_amount_original": 30, "cost_amount_original": 20},
            ],
        }, edit_reason="تصحيح العميل والمورد والتكلفة", user_id=1)
        assert updated["ok"] is True
        assert updated["client_expense_id"] == original_client_id
        conn = db.get_connection()
        case = conn.execute("SELECT * FROM service_cases WHERE reference=?", (ref,)).fetchone()
        assert case is not None
        assert case["client_company_name"] == "بلو ستار المعدلة"
        assert case["supplier_company_name"] == "المورد الجديد، رسوم سفارات"
        assert case["person_name"] == "أحمد محمد المعدل"
        assert float(case["sale_amount_original"]) == 210.0
        assert float(case["cost_amount_original"]) == 150.0
        assert float(case["sale_amount_base"]) == 210.0
        assert float(case["cost_amount_base"]) == 150.0
        assert case["date"] == "2026-07-12"

        linked_after = [dict(r) for r in conn.execute("SELECT * FROM expenses WHERE source_ref=? ORDER BY source_type, id", (ref,)).fetchall()]
        assert len(linked_after) == 3, linked_after
        client_after = next(r for r in linked_after if r["source_type"] == "service_case_client")
        suppliers_after = [r for r in linked_after if r["source_type"] == "service_case_supplier"]
        assert client_after["id"] == original_client_id
        assert client_after["company_name"] == "بلو ستار المعدلة"
        assert client_after["type"] == "incoming"
        assert float(client_after["amount_original"]) == 210.0
        assert client_after["date"] == "2026-07-12"
        assert all(int(r["is_locked"] or 0) == 1 for r in linked_after)
        assert {r["company_name"] for r in suppliers_after} == {"المورد الجديد", "رسوم سفارات"}
        assert sum(float(r["amount_original"] or 0) for r in suppliers_after) == 150.0
        stale = conn.execute("SELECT COUNT(*) AS c FROM expenses WHERE source_ref=? AND company_name IN ('سيف الشام','شركة النقل')", (ref,)).fetchone()["c"]
        assert int(stale) == 0, "old supplier-side linked rows must not remain after editing suppliers"

        comps = [dict(r) for r in conn.execute("SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index", (ref,)).fetchall()]
        assert len(comps) == 2
        assert {c["supplier_company_name"] for c in comps} == {"المورد الجديد", "رسوم سفارات"}
        assert all(c.get("supplier_expense_id") for c in comps)

        audit = conn.execute("SELECT * FROM audit_log WHERE action='تعديل ملف خدمة' ORDER BY id DESC LIMIT 1").fetchone()
        assert audit is not None
        assert ref in audit["details"] and "تصحيح العميل" in audit["details"]

        service_repo.reverse(ref)
        try:
            service_repo.update_service_case(ref, {
                "client_company_name": "أ",
                "supplier_company_name": "ب",
                "person_name": "ج",
                "service_type": "تأشيرة سياحية",
                "sale_amount_original": 10,
                "cost_amount_original": 5,
                "currency_original": "USD",
                "date": "2026-07-13",
            }, edit_reason="لا يجب", user_id=1)
        except ValueError as exc:
            assert "معكوسة" in str(exc)
        else:
            raise AssertionError("reversed service case must not be editable")

        dialog_src = open(os.path.join(ROOT, "views", "dialogs", "service_case_dialog.py"), encoding="utf-8").read()
        assert "update_service_case" in dialog_src
        assert "سبب تعديل الخدمة" in dialog_src
        details_src = open(os.path.join(ROOT, "views", "company_details_mobile_view.py"), encoding="utf-8").read()
        assert "تعديل الخدمة" in details_src and "_edit_service_case" in details_src
        rest_src = open(os.path.join(ROOT, "database", "connection_rest.py"), encoding="utf-8").read()
        assert "update_service_case" in rest_src and "get_service_case" in rest_src
        server_src = open(os.path.join(ROOT, "server", "flask_server.py"), encoding="utf-8").read()
        assert '@app.put("/api/service_cases/<path:reference>")' in server_src
        print("linked_service_case_edit_smoke_test passed")
        return 0
    finally:
        reset_singleton()
        if old_data_dir is None:
            os.environ.pop("HAWAA_DATA_DIR", None)
        else:
            os.environ["HAWAA_DATA_DIR"] = old_data_dir
        if old_server_flag is None:
            os.environ.pop("HAWAA_SERVER_PROCESS", None)
        else:
            os.environ["HAWAA_SERVER_PROCESS"] = old_server_flag
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
