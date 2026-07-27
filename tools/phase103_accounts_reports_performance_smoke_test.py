# -*- coding: utf-8 -*-
"""Regression checks for Phase 103 account/report UX improvements."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, text: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    assert text in content, f"missing {text!r} in {path}"


def static_checks() -> None:
    require("pyproject.toml", 'version = "1.0.49"')
    require("views/design_system/interaction.py", "class DebouncedAction")
    require("views/accounts_mobile_view.py", "self._search_debouncer")
    require("views/accounts_mobile_view.py", "self._visible_limit")
    require("views/accounts_mobile_view.py", "عرض المزيد")
    require("views/reports_center_mobile_view.py", "_CATEGORY_REPORTS")
    require("views/reports_center_mobile_view.py", "self._filters_dirty")
    require("views/reports_center_mobile_view.py", "تطبيق الفلاتر")
    require("views/reports_center_mobile_view.py", "تصدير ومشاركة التقرير")
    require("views/company_details_mobile_view.py", "self.direction_filter")
    require("views/company_details_mobile_view.py", "self.person_filter")
    require("views/company_details_mobile_view.py", "_open_record_actions")
    require("views/company_details_mobile_view.py", "_build_mobile_ledger_cards")
    require("views/company_details_mobile_view.py", 'return "compact" if page_width(self._page) < 720 else "table"')
    require("views/company_details_mobile_view.py", "تصدير ومشاركة كشف الحساب")




def _datatable_row_count(root_control) -> int:
    """Return the number of rendered rows in the first nested wide DataTable."""
    stack = [root_control]
    visited = set()
    while stack:
        control = stack.pop()
        if control is None or id(control) in visited:
            continue
        visited.add(id(control))

        rows = getattr(control, "rows", None)
        columns = getattr(control, "columns", None)
        if rows is not None and columns is not None:
            return len(rows)

        content = getattr(control, "content", None)
        if content is not None:
            stack.append(content)

        controls = getattr(control, "controls", None)
        if controls:
            stack.extend(list(controls))

    raise AssertionError("company ledger DataTable was not rendered")


def runtime_checks() -> None:
    try:
        import flet  # noqa: F401
    except ImportError:
        return

    tmp = tempfile.mkdtemp(prefix="hawaa_phase103_")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ["HAWAA_DB_PATH"] = str(Path(tmp) / "hawaa_data.db")

    from database.migrations import init_database
    from database import ExpenseRepository
    from auth.session import UserSession

    init_database()
    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"})
    repo = ExpenseRepository()
    for index in range(30):
        company = "شركة كثيفة" if index < 25 else f"شركة {index:02d}"
        repo.add(
            company_name=company,
            amount=10 + index,
            type_val="incoming" if index % 2 == 0 else "outgoing",
            date=f"2026-07-{(index % 28) + 1:02d}",
            notes=f"قيد اختبار {index}",
            currency_code="USD",
            user_id=1,
            person_name="أحمد" if index % 2 == 0 else "سارة",
            service_type="اختبار",
        )
    for index in range(24):
        repo.add(
            company_name=f"عميل {index:02d}",
            amount=20,
            type_val="incoming",
            date="2026-07-15",
            notes="صفحة الحسابات",
            currency_code="USD",
            user_id=1,
        )

    class FakePage:
        width = 360
        height = 800
        overlay = []
        dialog = None
        snack_bar = None
        theme_mode = None
        rtl = True
        floating_action_button = None
        def update(self):
            return None

    page = FakePage()
    from views.accounts_mobile_view import AccountsMobileView
    accounts = AccountsMobileView(page)
    assert accounts._filtered_company_count >= 25
    assert len(accounts.cards_container.controls) == 20
    assert accounts.pagination_bar.visible
    accounts._load_more()
    assert len(accounts.cards_container.controls) > 20

    from views.company_details_mobile_view import CompanyDetailsMobileView
    details = CompanyDetailsMobileView(page, "شركة كثيفة")
    assert details._last_ledger_layout_mode == "compact"
    assert details._desktop_ledger_table is None
    assert len(details._mobile_ledger_rows) == 20
    assert details.pagination_bar.visible
    details._load_more()
    assert len(details._mobile_ledger_rows) == 25
    details.direction_filter.value = "لنا"
    details._on_filter_changed()
    assert all(r.get("type") == "incoming" for r in details.records)
    details.person_filter.value = "أحمد"
    details._on_filter_changed()
    assert all((r.get("person_name") or "") == "أحمد" for r in details.records)

    class FakeWidePage(FakePage):
        width = 1024

    wide_details = CompanyDetailsMobileView(FakeWidePage(), "شركة كثيفة")
    assert wide_details._last_ledger_layout_mode == "table"
    assert wide_details._mobile_ledger_rows == []
    assert _datatable_row_count(wide_details.records_list) == 20

    from views.reports_center_mobile_view import ReportsCenterMobileView
    reports = ReportsCenterMobileView(page)
    assert reports.category_dropdown.options
    assert reports._current_report is not None
    reports.detail_dropdown.value = "detail"
    reports._on_filter_changed()
    assert reports._filters_dirty
    reports._on_view_report()
    assert not reports._filters_dirty
    assert reports._current_report is not None


if __name__ == "__main__":
    static_checks()
    runtime_checks()
    print("phase103_accounts_reports_performance_smoke_test passed")
