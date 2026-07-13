# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_ledger_core_")

from database.migrations import ensure_db
from database.connection import DatabaseConnection
from database.repositories.expense_repo import ExpenseRepository
from services.company_search_service import normalize_search_text

ensure_db()
repo = ExpenseRepository()
eid = repo.add(
    "أبو تيم",
    295,
    "incoming",
    "2026-07-12",
    "تسديد تذكرة عمان الشارقة",
    "USD",
    1,
    person_name="محمد المصري",
    service_type="تذكرة سفر",
    operation_type="ticket",
)
row = (
    DatabaseConnection()
    .get_connection()
    .execute("SELECT * FROM expenses WHERE id=?", (eid,))
    .fetchone()
)
assert row is not None
row = dict(row)
assert row["person_name"] == "محمد المصري"
assert row["person_name_search"] == normalize_search_text("محمد المصري")
assert row["service_type"] == "تذكرة سفر"
assert row["operation_type"] == "ticket"
assert int(row["is_locked"] or 0) == 0
matches = repo.search_company_ledger("محمد", limit=5)
assert any(m["id"] == eid for m in matches), matches

# Old compatible row with no metadata remains valid.
old_id = repo.add("البتلاء", 100, "outgoing", "2026-07-12", "قيد قديم الشكل", "USD", 1)
old = dict(
    DatabaseConnection()
    .get_connection()
    .execute("SELECT * FROM expenses WHERE id=?", (old_id,))
    .fetchone()
)
assert old["operation_type"] == "normal"
assert old["service_type"] == "غير محدد"

print("ledger_operation_core_smoke_test passed")
