# -*- coding: utf-8 -*-
"""Static guard that financial dialogs use one operation-date component."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _normalize_probe(value: str) -> str:
    return dt.datetime.strptime(str(value or "").strip(), "%Y-%m-%d").strftime("%Y-%m-%d")


def main() -> None:
    component = _read("views/financial_date_field.py")
    add_edit = _read("views/dialogs/add_edit_expense_dialog.py")
    service = _read("views/dialogs/service_case_dialog.py")
    third = _read("views/dialogs/third_party_payment_dialog.py")
    quality = _read("tools/quality_gate.py")

    assert "class FinancialDateField" in component
    assert "normalize_financial_date" in component
    assert "finance/last_operation_date" in component
    assert "اليوم" in component and "أمس" in component and "آخر تاريخ" in component
    assert "ft.DatePicker" in component and "open_control" in component and "close_control" in component
    assert _normalize_probe("2026-07-14") == "2026-07-14"
    try:
        _normalize_probe("14/07/2026")
    except Exception:
        pass
    else:
        raise AssertionError("invalid date format was accepted by probe")

    for name, src in {
        "قيد عادي": add_edit,
        "خدمة عبر مورد": service,
        "سداد عني": third,
    }.items():
        assert "from views.financial_date_field import FinancialDateField" in src, f"{name} لا يستورد FinancialDateField"
        assert "FinancialDateField(" in src, f"{name} لا يستخدم FinancialDateField"
        assert ".require_value(" in src, f"{name} لا يتحقق من تاريخ العملية"
        assert ".remember()" in src, f"{name} لا يحفظ آخر تاريخ مستخدم"
        assert ".close()" in src, f"{name} لا يغلق DatePicker التابع للمكوّن"

    assert "self.date_field = ft.TextField" not in service, "خدمة عبر مورد ما زالت تستخدم TextField تاريخ مستقل"
    assert "self.date_field = ft.TextField" not in third, "سداد عني ما زال يستخدم TextField تاريخ مستقل"
    assert "self.date_picker = ft.DatePicker" not in add_edit, "القيد العادي يجب أن يأخذ DatePicker من المكوّن الموحد"
    assert "tools/unified_financial_date_picker_smoke_test.py" in quality

    print("✅ unified_financial_date_picker_smoke_test passed")


if __name__ == "__main__":
    main()
