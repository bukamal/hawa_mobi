# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
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
    tmp = tempfile.mkdtemp(prefix="hawaa_linked_tpp_edit_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)
    try:
        reset_singleton()
        from database.migrations import init_database
        from database.connection import DatabaseConnection
        from database import ExpenseRepository, ThirdPartyPaymentRepository

        init_database()
        db = DatabaseConnection()
        repo = ThirdPartyPaymentRepository()
        expense_repo = ExpenseRepository()

        created = repo.add_payment_on_behalf("شركة دفعت", "شركة دُفع لها", 100, "USD", "2026-07-01", "قبل", 1)
        ref = created["reference"]
        rows = expense_repo.get_all(convert_to_display=False)
        assert len(rows) == 2, rows
        generated = next(r for r in rows if r["source_ref"] == ref)
        try:
            expense_repo.update(generated["id"], generated["company_name"], 200, generated["type"], generated["date"], "تعديل منفرد", generated["currency_original"], 1)
        except ValueError as exc:
            assert "لا يُعدّل منفرد" in str(exc) or "مولّدة" in str(exc)
        else:
            raise AssertionError("generated linked entries must not be editable individually")

        updated = repo.update_payment_on_behalf(
            reference=ref,
            payer_company_name="شركة دفعت معدلة",
            paid_to_company_name="شركة دُفع لها معدلة",
            amount=250,
            currency_code="USD",
            date="2026-07-02",
            notes="بعد",
            edit_reason="تصحيح مبلغ وشركات السداد",
            user_id=1,
        )
        assert updated["ok"] is True
        conn = db.get_connection()
        tpp = conn.execute("SELECT * FROM third_party_payments WHERE reference=?", (ref,)).fetchone()
        assert tpp is not None
        assert tpp["payer_company_name"] == "شركة دفعت معدلة"
        assert tpp["paid_to_company_name"] == "شركة دُفع لها معدلة"
        assert float(tpp["amount_original"]) == 250.0
        assert tpp["date"] == "2026-07-02"
        assert tpp["edit_reason"] == "تصحيح مبلغ وشركات السداد"

        linked = conn.execute("SELECT * FROM expenses WHERE source_ref=? AND source_type='third_party_payment' ORDER BY type", (ref,)).fetchall()
        assert len(linked) == 2, [dict(r) for r in linked]
        by_type = {r["type"]: r for r in linked}
        assert by_type["incoming"]["company_name"] == "شركة دُفع لها معدلة"
        assert by_type["incoming"]["counterparty_company_name"] == "شركة دفعت معدلة"
        assert by_type["outgoing"]["company_name"] == "شركة دفعت معدلة"
        assert by_type["outgoing"]["counterparty_company_name"] == "شركة دُفع لها معدلة"
        assert all(float(r["amount_original"]) == 250.0 for r in linked)
        assert all(r["date"] == "2026-07-02" for r in linked)
        assert all(int(r["is_locked"] or 0) == 1 for r in linked)
        assert all(r["source_type"] == "third_party_payment" for r in linked)
        assert abs(float(by_type["incoming"]["amount_base"]) - float(by_type["outgoing"]["amount_base"])) < 1e-9

        old_count = conn.execute("SELECT COUNT(*) AS c FROM expenses WHERE company_name IN ('شركة دفعت','شركة دُفع لها')").fetchone()["c"]
        assert int(old_count) == 0, "changing companies must move both ledger entries, not duplicate them"

        audit = conn.execute("SELECT * FROM audit_log WHERE action='تعديل سداد بالنيابة' ORDER BY id DESC LIMIT 1").fetchone()
        assert audit is not None
        assert ref in audit["details"] and "تصحيح مبلغ" in audit["details"]

        repo.reverse_payment_on_behalf(ref, 1, "2026-07-03")
        try:
            repo.update_payment_on_behalf(ref, "أ", "ب", 10, "USD", "2026-07-04", "", "لا يجب", 1)
        except ValueError as exc:
            assert "معكوسة" in str(exc)
        else:
            raise AssertionError("reversed third-party payment must not be editable")

        dialog_src = open(os.path.join(ROOT, "views", "dialogs", "third_party_payment_dialog.py"), encoding="utf-8").read()
        assert "update_payment_on_behalf" in dialog_src
        assert "سبب التعديل" in dialog_src
        details_src = open(os.path.join(ROOT, "views", "company_details_mobile_view.py"), encoding="utf-8").read()
        assert "تعديل العملية" in details_src and "_edit_third_party" in details_src
        print("linked_intercompany_entry_edit_smoke_test passed")
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
