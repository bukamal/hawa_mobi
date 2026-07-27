# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Any, Dict, List

from auth.session import UserSession
from database.repositories.base_repo import BaseRepository
from services.payment_service import (
    delete_payments_for_targets,
    get_payment_summary,
    insert_payment_in_transaction,
    sync_payment_state,
)


class PaymentRepository(BaseRepository):
    def get_summary(self, expense_id: int) -> Dict[str, Any]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_payment_summary(int(expense_id))
        return get_payment_summary(self.db.get_connection(), int(expense_id))

    def list_for_expense(self, expense_id: int) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_payments(int(expense_id))
        rows = self.db.get_connection().execute(
            "SELECT * FROM payments WHERE target_expense_id=? AND status='posted' ORDER BY date DESC, id DESC",
            (int(expense_id),),
        ).fetchall()
        return [dict(row) for row in rows]

    def add(
        self,
        expense_id: int,
        amount: float,
        *,
        date: str | None = None,
        payment_method: str = "cash",
        reference_number: str = "",
        notes: str = "",
        user_id: int | None = None,
    ) -> Dict[str, Any]:
        payload = {
            "amount": amount,
            "date": date or datetime.datetime.now().strftime("%Y-%m-%d"),
            "payment_method": payment_method,
            "reference_number": reference_number,
            "notes": notes,
        }
        if self.data.is_remote():
            return self.db.get_rest_client().add_payment(int(expense_id), payload)
        conn = self.db.get_connection()
        user = UserSession.get_current() or {}
        uid = int(user_id or user.get("id") or 1)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM expenses WHERE id=?", (int(expense_id),)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على القيد")
            result = insert_payment_in_transaction(
                conn,
                dict(row),
                amount,
                date=payload["date"],
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                user_id=uid,
                username=user.get("username", ""),
            )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise

    def delete(self, payment_id: int, *, reason: str, user_id: int | None = None) -> Dict[str, Any]:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب حذف الدفعة مطلوب")
        if self.data.is_remote():
            return self.db.get_rest_client().delete_payment(int(payment_id), {"reason": clean_reason})
        conn = self.db.get_connection()
        user = UserSession.get_current() or {}
        uid = int(user_id or user.get("id") or 1)
        now = datetime.datetime.now().isoformat()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM payments WHERE id=?", (int(payment_id),)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على الدفعة")
            payment = dict(row)
            if payment.get("ledger_expense_id"):
                conn.execute("DELETE FROM expenses WHERE id=?", (int(payment["ledger_expense_id"]),))
            conn.execute("DELETE FROM payments WHERE id=?", (int(payment_id),))
            summary = sync_payment_state(conn, int(payment["target_expense_id"]), now=now)
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "حذف دفعة", "payments", int(payment_id), f"{payment.get('reference')} | السبب: {clean_reason}", "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, **summary}
        except Exception:
            conn.rollback()
            raise

    def delete_for_targets(self, conn, target_expense_ids):
        return delete_payments_for_targets(conn, target_expense_ids)
