# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import sqlite3
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


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hawaa_deep_search_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    os.environ["HAWAA_DATA_DIR"] = tmp
    try:
        reset_singleton()
        from database.migrations import init_database
        from database import ExpenseRepository
        from services.company_search_service import normalize_search_text

        init_database()
        repo = ExpenseRepository()
        repo.add("شركة النور", 100, "outgoing", "2026-07-10", "تم السداد عن طريق أبو محمد للفاتورة 45", "USD", 1)
        repo.add("شركة الشام", 500000, "incoming", "2026-07-11", "ملاحظة عادية", "SYP", 1)

        assert normalize_search_text("أبو محمد") == normalize_search_text("ابو محمد")
        results = repo.search_company_ledger("ابو محمد", limit=10)
        assert results, "Search should find Arabic name inside notes"
        assert results[0]["company_name"] == "شركة النور", results
        assert results[0]["matched_field"] == "notes", results
        assert "أبو محمد" in results[0]["snippet"], results[0]
        assert results[0].get("currency_original") == "USD"
        assert results[0].get("amount_original") == 100

        by_ref_or_amount = repo.search_company_ledger("500000", limit=10)
        assert any(r["company_name"] == "شركة الشام" for r in by_ref_or_amount), by_ref_or_amount

        by_company = repo.search_company_ledger("النور", limit=10)
        assert by_company and by_company[0]["company_name"] == "شركة النور"

        # Static UI guard: the Accounts screen must use the deep-search repository method,
        # not only company_name.lower() filtering.
        with open(os.path.join(ROOT, "views", "accounts_mobile_view.py"), "r", encoding="utf-8") as f:
            ui = f.read()
        assert "search_company_ledger" in ui
        assert "matches_inside_company" in ui
        assert "company_name'].lower()" not in ui

        print("company_deep_search_smoke_test passed")
        return 0
    finally:
        reset_singleton()
        if old_data_dir is None:
            os.environ.pop("HAWAA_DATA_DIR", None)
        else:
            os.environ["HAWAA_DATA_DIR"] = old_data_dir
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
