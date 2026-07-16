# -*- coding: utf-8 -*-
"""Guard searchable Android form fields.

The accounting dialogs must keep accepting new text, but company/person fields
need search suggestions once real data grows.  This test is intentionally mostly
static because the CI environment does not install Flet; it also checks the
repository-backed suggestion service with a temporary SQLite database.
"""
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


def assert_contains(path: str, *needles: str):
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path} must contain {needle!r}"
    return text


def main() -> int:
    # UI wiring: fields that select companies/customers in business workflows
    # must use the searchable wrapper, not a plain TextField.
    assert_contains(
        "views/dialogs/add_edit_expense_dialog.py",
        "SearchableTextField",
        "suggestions_provider=list_company_names",
        "suggestions_provider=lambda: list_person_names(self.company_field.value)",
    )
    assert_contains(
        "views/dialogs/third_party_payment_dialog.py",
        "SearchableTextField",
        "suggestions_provider=list_company_names",
        "self.payer_field.on_change = self._update_preview",
        "self.paid_to_field.on_change = self._update_preview",
    )
    assert_contains(
        "views/dialogs/service_case_dialog.py",
        "self.client_field = SearchableTextField",
        "self.supplier_field = SearchableTextField",
        "self.embassy_supplier_field = SearchableTextField",
        "self.transport_supplier_field = SearchableTextField",
        "list_person_names(self.client_field.value)",
    )
    assert_contains(
        "views/dialogs/direct_service_dialog.py",
        "self.company_field = SearchableTextField",
        "self.person_field = SearchableTextField",
        "self.supplier_field = SearchableTextField",
    )
    assert_contains(
        "views/reports_center_mobile_view.py",
        "SearchableTextField",
        "self._company_suggestions",
    )

    # Data source: suggestions come from existing ledger data and normalize
    # Arabic variants, but do not prevent typing new values.
    tmp = tempfile.mkdtemp(prefix="hawaa_searchable_fields_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    try:
        reset_singleton()
        from database.migrations import init_database
        from database.repositories.expense_repo import ExpenseRepository
        from services.form_suggestions_service import list_company_names, list_person_names, list_service_types

        init_database()
        repo = ExpenseRepository()
        repo.add("أبو تيم", 100, "incoming", "2026-07-01", "تذكرة", "USD", 1, person_name="أحمد محمد", service_type="تذكرة سفر")
        repo.add("بلو ستار", 50, "outgoing", "2026-07-02", "نقل", "USD", 1, person_name="محمد سالم", service_type="نقل بري")

        companies = list_company_names()
        assert "أبو تيم" in companies and "بلو ستار" in companies, companies
        people_abu = list_person_names("ابو تيم")
        assert "أحمد محمد" in people_abu, people_abu
        people_all = list_person_names()
        assert "محمد سالم" in people_all, people_all
        service_types = list_service_types()
        assert "تذكرة سفر" in service_types, service_types
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

    print("searchable_form_fields_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
