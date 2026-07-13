# -*- coding: utf-8 -*-
"""Comprehensive integrated audit for Android/Windows contract.

Covers:
- stored original currency vs accounting base amount
- displayed currency conversion using current rate
- immutable historical exchange-rate snapshot
- exchange-rate history
- local ledger operation/service-case workflow
- report/reconciliation output
- language dictionaries and RTL/LTR switching
- live Flask API contract through test_client
"""
from __future__ import annotations

import importlib
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def approx(a, b, eps=1e-6):
    assert math.isclose(float(a), float(b), rel_tol=eps, abs_tol=eps), f"{a!r} != {b!r}"


def reset_singletons():
    try:
        from database.connection import DatabaseConnection
        DatabaseConnection.reset_after_restore()
    except Exception:
        pass
    try:
        from currency import currency
        currency.invalidate_cache()
    except Exception:
        pass


def local_currency_and_reports(tmp: Path) -> None:
    os.environ["HAWAA_DATA_DIR"] = str(tmp / "local")
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    reset_singletons()

    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from currency import currency
    from database import ExpenseRepository, ServiceCaseRepository
    from reports.account_statement import (
        build_rows,
        export_account_statement_html,
        export_reconciliation_statement_html,
        export_service_profit_report_html,
    )
    from reports.config import get_report_settings, save_report_settings

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    currency.save_runtime_settings(base_currency="USD", display_currency="USD", decimals=2, number_format="western", abbreviate_numbers=False)
    currency.update_rate("SYP", 14000)

    repo = ExpenseRepository()
    eid = repo.add(
        "بلو ستار",
        140000,
        "incoming",
        "2026-07-12",
        "تأشيرة أحمد محمد",
        "SYP",
        1,
        person_name="أحمد محمد",
        service_type="تأشيرة سياحية",
        operation_type="normal",
    )
    row = repo.get_by_company("بلو ستار", convert_to_display=False)[0]
    assert row["id"] == eid
    assert row["currency_original"] == "SYP"
    approx(row["amount_original"], 140000)
    approx(row["exchange_rate_to_usd"], 14000)
    approx(row["amount_base"], 10)
    approx(row["amount"], 10)

    # Historical snapshot must remain frozen when the current display rate changes.
    currency.update_rate("SYP", 15000)
    row_after_rate = repo.get_by_company("بلو ستار", convert_to_display=False)[0]
    approx(row_after_rate["exchange_rate_to_usd"], 14000)
    approx(row_after_rate["amount_base"], 10)
    approx(currency.convert(row_after_rate["amount_base"], "USD", "SYP"), 150000)

    # Editing without changing the original currency preserves the historical rate.
    repo.update(eid, "بلو ستار", 280000, "incoming", "2026-07-12", "تعديل مبلغ بنفس العملة", "SYP", 1, person_name="أحمد محمد", service_type="تأشيرة سياحية")
    edited = repo.get_by_company("بلو ستار", convert_to_display=False)[0]
    approx(edited["exchange_rate_to_usd"], 14000)
    approx(edited["amount_original"], 280000)
    approx(edited["amount_base"], 20)

    settings = get_report_settings()
    cols = settings["account_statement_columns"]
    for col in cols:
        if col.get("key") in {"historical_currency_value", "person_name", "service_type"}:
            col["visible"] = True
    save_report_settings({"account_statement_columns": cols})
    rows, totals = build_rows([edited], display_currency="SYP")
    assert rows[0]["debit"].endswith("ل.س"), rows[0]
    assert "14,000" in rows[0]["historical_currency_value"], rows[0]["historical_currency_value"]
    assert "300,000" in rows[0]["running_balance"], rows[0]["running_balance"]
    approx(totals["net_usd"], 20)
    statement = Path(export_account_statement_html("بلو ستار", [edited])).read_text(encoding="utf-8")
    assert "القيمة التاريخية للعملة" in statement
    assert "أحمد محمد" in statement
    assert "تأشيرة سياحية" in statement

    service_repo = ServiceCaseRepository()
    currency.update_rate("SYP", 14000)
    result = service_repo.add({
        "client_company_name": "بلو ستار",
        "supplier_company_name": "سيف الشام",
        "person_name": "ليان الفيداوي",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 280000,
        "cost_amount_original": 210000,
        "currency_original": "SYP",
        "date": "2026-07-13",
        "notes": "ملف اختبار شامل",
    })
    assert result["reference"].startswith("SVC-")
    approx(result["profit_base"], 5)
    cases = service_repo.list_cases()
    case = cases[0]
    approx(case["sale_amount_base"], 20)
    approx(case["cost_amount_base"], 15)
    approx(case["exchange_rate_to_usd"], 14000)

    client_rows = repo.get_by_company("بلو ستار", convert_to_display=False)
    supplier_rows = repo.get_by_company("سيف الشام", convert_to_display=False)
    assert any(r.get("service_case_role") == "client" for r in client_rows)
    assert any(r.get("service_case_role") == "supplier" for r in supplier_rows)
    assert all(int(r.get("is_locked") or 0) == 1 for r in client_rows + supplier_rows if r.get("source_ref") == result["reference"])

    rec_html = Path(export_reconciliation_statement_html("بلو ستار", client_rows)).read_text(encoding="utf-8")
    assert "كشف حساب للمطابقة" in rec_html
    assert "ليان الفيداوي" in rec_html
    assert "تكلفة تأشيرة" not in rec_html  # client reconciliation must not expose supplier-side cost wording
    profit_html = Path(export_service_profit_report_html(cases)).read_text(encoding="utf-8")
    assert "تقرير أرباح الخدمات الداخلي" in profit_html
    assert "بلو ستار" in profit_html and "سيف الشام" in profit_html

    history = __import__("database.connection", fromlist=["DatabaseConnection"]).DatabaseConnection().get_exchange_rate_history()
    assert len([h for h in history if h["currency_code"] == "SYP"]) >= 3


def language_checks() -> None:
    from i18n import translator as tr
    langs = ["ar", "en", "fr"]
    key_sets = {lang: set(tr._translations[lang]) for lang in langs}
    assert key_sets["ar"] == key_sets["en"] == key_sets["fr"], "language dictionaries must share the same keys"
    for lang in langs:
        tr.set_language(lang)
        assert tr.get_language() == lang
        assert tr.translate("app_title") != "app_title"
        assert tr.translate("company_deep_search_hint") != "company_deep_search_hint"
    tr.set_language("ar")
    assert tr.is_rtl() is True
    tr.set_language("en")
    assert tr.is_rtl() is False
    assert tr.language_code_from_label("Français") == "fr"
    assert tr.language_label("ar") == "العربية"


def static_api_contract_checks() -> None:
    import re
    server_text = (ROOT / "server" / "flask_server.py").read_text(encoding="utf-8")
    rest_text = (ROOT / "database" / "connection_rest.py").read_text(encoding="utf-8")

    required_flags = [
        "supports_historic_currency_snapshot",
        "supports_amount_base",
        "supports_exchange_rate_history",
        "supports_service_cases",
        "supports_reconciliation_statement",
        "supports_company_deep_search",
        "supports_ledger_operation_core",
    ]
    for flag in required_flags:
        assert flag in server_text, f"server capabilities missing {flag}"
    required_routes = [
        "/api/capabilities",
        "/api/expenses",
        "/api/expenses/summary",
        "/api/search/company-ledger",
        "/api/service_cases",
        "/api/service_cases/{reference}/reverse",
        "/api/third_party_payments",
        "/api/exchange_rates",
        "/api/exchange_rate_history",
        "/api/exchange_rates/{currency_code}",
    ]
    for route in required_routes:
        assert route in server_text, f"server route declaration missing {route}"

    for token in [
        "def add_service_case",
        "def get_service_cases",
        "def reverse_service_case",
        "def update_exchange_rate",
        "def get_exchange_rate_history",
        "normalize_expense_payload",
        "exchange_rate_to_usd",
        "amount_base",
        "is_locked",
    ]:
        assert token in server_text, f"server implementation missing {token}"
    for token in [
        "def add_service_case",
        "def reverse_service_case",
        "def get_exchange_rate_history",
        "def update_exchange_rate",
        "'/api/service_cases'",
        "'/api/exchange_rate_history'",
    ]:
        assert token in rest_text, f"RestClient implementation missing {token}"

    route_decorators = set(re.findall(r"""@app\.(?:get|post|put|delete)\(\s*["']([^"']+)["']""", server_text))
    for route in ["/api/capabilities", "/api/exchange_rate_history", "/api/service_cases"]:
        assert route in route_decorators, f"missing Flask decorator for {route}"


def live_api_checks(tmp: Path) -> None:
    try:
        import flask  # noqa: F401
    except Exception:
        static_api_contract_checks()
        print("live Flask API test skipped: flask is not installed; static API contract passed")
        return

    os.environ["HAWAA_DATA_DIR"] = str(tmp / "api")
    os.environ["HAWAA_SERVER_PROCESS"] = "1"
    reset_singletons()

    # Import server after setting HAWAA_DATA_DIR so it uses the isolated DB.
    server = importlib.import_module("server.flask_server")
    server.ensure_db()
    client = server.app.test_client()

    cap = client.get("/api/capabilities")
    assert cap.status_code == 200, cap.data
    cap_json = cap.get_json()
    for key in [
        "supports_historic_currency_snapshot",
        "supports_amount_base",
        "supports_exchange_rate_history",
        "supports_service_cases",
        "supports_reconciliation_statement",
        "supports_company_deep_search",
    ]:
        assert cap_json.get(key) is True, f"capabilities missing {key}"

    login = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200, login.data
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.put("/api/exchange_rates/SYP", json={"rate_to_usd": 14000}, headers=headers)
    assert r.status_code == 200, r.data
    add = client.post("/api/expenses", json={
        "company_name": "API بلو ستار",
        "amount": 140000,
        "type": "incoming",
        "date": "2026-07-14",
        "currency": "SYP",
        "person_name": "أحمد API",
        "service_type": "تأشيرة سياحية",
        "operation_type": "normal",
        "notes": "API historical currency test",
    }, headers=headers)
    assert add.status_code == 200, add.data
    eid = add.get_json()["id"]
    r = client.put("/api/exchange_rates/SYP", json={"rate_to_usd": 16000}, headers=headers)
    assert r.status_code == 200, r.data
    got = client.get(f"/api/expenses/{eid}", headers=headers)
    assert got.status_code == 200, got.data
    expense = got.get_json()
    approx(expense["amount_original"], 140000)
    approx(expense["exchange_rate_to_usd"], 14000)
    approx(expense["amount_base"], 10)

    svc = client.post("/api/service_cases", json={
        "client_company_name": "API بلو ستار",
        "supplier_company_name": "API سيف الشام",
        "person_name": "مسافر API",
        "service_type": "فيزا",
        "sale_amount_original": 320000,
        "cost_amount_original": 160000,
        "currency_original": "SYP",
        "date": "2026-07-15",
        "notes": "API service case",
    }, headers=headers)
    assert svc.status_code == 200, svc.data
    svc_json = svc.get_json()
    approx(svc_json["profit_base"], 10)

    search = client.get("/api/search/company-ledger?q=مسافر%20API&limit=20", headers=headers)
    assert search.status_code == 200, search.data
    companies = {r.get("company_name") for r in search.get_json()}
    assert {"API بلو ستار", "API سيف الشام"} <= companies

    hist = client.get("/api/exchange_rate_history", headers=headers)
    assert hist.status_code == 200, hist.data
    assert len([h for h in hist.get_json() if h["currency_code"] == "SYP"]) >= 2

    # Locked service-case expenses must not be editable/deletable through API.
    all_rows = client.get("/api/expenses", headers=headers).get_json()
    locked = next(r for r in all_rows if r.get("source_ref") == svc_json["reference"])
    del_resp = client.delete(f"/api/expenses/{locked['id']}", headers=headers)
    assert del_resp.status_code == 409, del_resp.data


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="hawaa_comprehensive_"))
    try:
        language_checks()
        local_currency_and_reports(tmp)
        live_api_checks(tmp)
        print("comprehensive_currency_language_api_test passed")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
