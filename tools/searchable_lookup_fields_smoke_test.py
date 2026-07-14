# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    tmp = tempfile.mkdtemp(prefix="hawaa_lookup_fields_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    try:
        reset_singleton()
        from database.migrations import init_database
        from auth.session import UserSession
        from database import ExpenseRepository, ServiceCaseRepository
        from services.lookup_service import (
            normalize_search_text,
            search_company_options,
            search_person_options,
            search_service_type_options,
            has_company_option,
        )

        init_database()
        UserSession.login({"id": 1, "username": "admin", "role": "admin"})
        expense_repo = ExpenseRepository()
        expense_repo.add("أبو تيم", 100, "incoming", "2026-07-01", "قيد تجريبي", "USD", 1, person_name="أحمد محمد", service_type="تذكرة سفر")
        service_repo = ServiceCaseRepository()
        service_repo.add({
            "client_company_name": "بلو ستار",
            "supplier_company_name": "سيف الشام",
            "person_name": "أحمد محمود",
            "service_type": "تأشيرة سياحية",
            "currency_original": "USD",
            "date": "2026-07-02",
            "notes": "بحث تجريبي",
            "components": [
                {"service_type": "تأشيرة سياحية", "supplier_company_name": "سيف الشام", "sale_amount_original": 150, "cost_amount_original": 120},
                {"service_type": "نقل بري", "supplier_company_name": "شركة النقل", "sale_amount_original": 50, "cost_amount_original": 40},
            ],
        })

        assert normalize_search_text("أحمد") == normalize_search_text("احمد")
        assert normalize_search_text("شركة") == normalize_search_text("شركه")
        companies = search_company_options("بلو", limit=5)
        assert any(o["value"] == "بلو ستار" for o in companies), companies
        suppliers = search_company_options("سيف", limit=5)
        assert any(o["value"] == "سيف الشام" for o in suppliers), suppliers
        assert has_company_option("أبو تيم") is True
        people = search_person_options("احمد", limit=10)
        values = {o["value"] for o in people}
        assert "أحمد محمد" in values and "أحمد محمود" in values, people
        services = search_service_type_options("تأش", limit=5)
        assert any(o["value"] == "تأشيرة سياحية" for o in services), services

        component = (ROOT / "views" / "searchable_lookup_field.py").read_text(encoding="utf-8")
        assert "class SearchableLookupField" in component
        assert "company_lookup_field" in component and "person_lookup_field" in component and "service_type_lookup_field" in component
        service_src = (ROOT / "services" / "lookup_service.py").read_text(encoding="utf-8")
        assert "search_company_options" in service_src and "search_person_options" in service_src and "search_service_type_options" in service_src
        add_edit = (ROOT / "views" / "dialogs" / "add_edit_expense_dialog.py").read_text(encoding="utf-8")
        service_dialog = (ROOT / "views" / "dialogs" / "service_case_dialog.py").read_text(encoding="utf-8")
        third_party = (ROOT / "views" / "dialogs" / "third_party_payment_dialog.py").read_text(encoding="utf-8")
        assert "company_lookup_field" in add_edit and "person_lookup_field" in add_edit and "service_type_lookup_field" in add_edit
        assert "company_lookup_field" in service_dialog and "person_lookup_field" in service_dialog and "service_type_lookup_field" in service_dialog
        assert "self.client_field = ft.TextField" not in service_dialog
        assert "self.supplier_field = ft.TextField" not in service_dialog
        assert "self.payer_field = ft.TextField" not in third_party
        assert "self.paid_to_field = ft.TextField" not in third_party
        quality = (ROOT / "tools" / "quality_gate.py").read_text(encoding="utf-8")
        assert "tools/searchable_lookup_fields_smoke_test.py" in quality
        print("searchable_lookup_fields_smoke_test passed")
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
