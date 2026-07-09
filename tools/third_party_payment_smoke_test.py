# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile

# Must be set before importing database.connection
os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_tpp_")

from database.migrations import ensure_db
from database import ExpenseRepository, ThirdPartyPaymentRepository

ensure_db()
repo = ThirdPartyPaymentRepository()
res = repo.add_payment_on_behalf("الشركة التي دفعت", "الشركة الدائنة", 1500, "SYP", "2026-07-10", "اختبار", 1)
assert res["ok"] and res["reference"].startswith("TPP-")
records = ExpenseRepository().get_all(convert_to_display=False)
assert len(records) == 2, records
by_company = {r["company_name"]: r for r in records}
assert by_company["الشركة الدائنة"]["type"] == "incoming"
assert by_company["الشركة التي دفعت"]["type"] == "outgoing"
assert all(r.get("source_type") == "third_party_payment" for r in records)
assert all(r.get("source_ref") == res["reference"] for r in records)
try:
    ExpenseRepository().delete(records[0]["id"], 1)
    raise AssertionError("generated third-party expense should not be deletable individually")
except ValueError:
    pass
repo.reverse_payment_on_behalf(res["reference"], 1, "2026-07-11")
records = ExpenseRepository().get_all(convert_to_display=False)
assert len(records) == 4, records
assert len([r for r in records if r.get("source_type") == "third_party_payment_reversal"]) == 2
print("third_party_payment_smoke_test passed")
