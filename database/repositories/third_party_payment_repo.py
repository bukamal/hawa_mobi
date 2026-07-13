# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import uuid
from typing import Dict

from auth.session import UserSession
from database.repositories.base_repo import BaseRepository
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import normalize_expense_metadata


class ThirdPartyPaymentRepository(BaseRepository):
    """سداد بالنيابة: شركة تسدد عني لشركة أخرى.

    الأثر المحاسبي داخل دفتر المستخدم:
    - الشركة المسدَّد لها: قيد incoming لتخفيض رصيدها المستحق.
    - الشركة التي سدّدت عني: قيد outgoing لزيادة الرصيد المستحق لها.
    """

    SOURCE_TYPE = "third_party_payment"
    REVERSAL_SOURCE_TYPE = "third_party_payment_reversal"

    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _normalize_company(self, value: str, label: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError(f"{label} مطلوب")
        return value

    def _reference(self) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"TPP-{ts}-{uuid.uuid4().hex[:6].upper()}"

    def _current_user(self):
        return UserSession.get_current() or {}

    def _expense_payload(self, company_name: str, amount: float, type_val: str, date: str, notes: str, currency_code: str, user_id: int, *, source_ref: str, counterparty: str, source_type: str) -> Dict:
        now = datetime.datetime.now().isoformat()
        data = {
            "company_name": company_name,
            "amount": float(amount),
            "type": type_val,
            "date": date,
            "notes": notes,
            "currency": currency_code,
            "created_by": user_id,
            "created_at": now,
            "updated_by": user_id,
            "updated_at": now,
            "status": "approved",
            "payment_due_date": None,
            "payment_reminder_note": None,
            "source_type": source_type,
            "source_ref": source_ref,
            "counterparty_company_name": counterparty,
        }
        data["service_type"] = "سداد بالنيابة"
        data["operation_type"] = source_type
        data["is_locked"] = 1
        normalized = normalize_expense_metadata(self.ledger.normalize_expense_payload(data))
        normalized["source_type"] = source_type
        normalized["source_ref"] = source_ref
        normalized["counterparty_company_name"] = counterparty
        normalized["is_locked"] = 1
        return normalized

    def _insert_expense(self, conn, data: Dict) -> int:
        cur = conn.execute(
            """INSERT INTO expenses
            (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note, source_type, source_ref, counterparty_company_name,
             person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["company_name"], data["amount"], data["amount_base"], data["type"], data["date"], data.get("notes", ""), data["currency"],
                data.get("created_by"), data.get("created_at"), data.get("updated_by"), data.get("updated_at"),
                data["amount_original"], data["currency_original"], data["exchange_rate_to_usd"], data.get("status", "approved"),
                data.get("payment_due_date"), data.get("payment_reminder_note"), data.get("source_type"), data.get("source_ref"), data.get("counterparty_company_name"),
                data.get("person_name"), data.get("person_name_search"), data.get("service_type"), data.get("operation_type"), data.get("is_locked", 1), data.get("reversal_of"), data.get("reversed_by"),
            ),
        )
        return int(cur.lastrowid)

    def add_payment_on_behalf(self, payer_company_name: str, paid_to_company_name: str, amount: float, currency_code: str, date: str, notes: str = "", user_id: int | None = None) -> Dict:
        payer = self._normalize_company(payer_company_name, "الشركة التي سدّدت عني")
        paid_to = self._normalize_company(paid_to_company_name, "الشركة التي تم السداد لها")
        if payer == paid_to:
            raise ValueError("لا يمكن اختيار نفس الشركة للطرفين")
        amount = float(amount or 0)
        if amount <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
        currency_code = (currency_code or "USD").upper().strip()
        date = str(date or datetime.datetime.now().strftime("%Y-%m-%d")).strip()
        if user_id is None:
            user_id = (self._current_user() or {}).get("id")
        user_id = user_id or 1
        reference = self._reference()
        clean_notes = str(notes or "").strip()

        if self.data.is_remote():
            return self.db.get_rest_client().add_third_party_payment({
                "payer_company_name": payer,
                "paid_to_company_name": paid_to,
                "amount": amount,
                "currency": currency_code,
                "date": date,
                "notes": clean_notes,
                "created_by": user_id,
            })

        paid_to_notes = f"سداد بالنيابة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {clean_notes}".strip()
        payer_notes = f"ذمة مستحقة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {clean_notes}".strip()
        paid_to_payload = self._expense_payload(
            paid_to, amount, "incoming", date, paid_to_notes, currency_code, user_id,
            source_ref=reference, counterparty=payer, source_type=self.SOURCE_TYPE,
        )
        payer_payload = self._expense_payload(
            payer, amount, "outgoing", date, payer_notes, currency_code, user_id,
            source_ref=reference, counterparty=paid_to, source_type=self.SOURCE_TYPE,
        )
        conn = self.db.get_connection()
        user = self._current_user()
        try:
            conn.execute("BEGIN IMMEDIATE")
            paid_to_expense_id = self._insert_expense(conn, paid_to_payload)
            payer_expense_id = self._insert_expense(conn, payer_payload)
            conn.execute(
                """INSERT INTO third_party_payments
                (reference, payer_company_name, paid_to_company_name, amount_original, currency_original,
                 exchange_rate_to_usd, amount_base, date, notes, status, payer_expense_id, paid_to_expense_id,
                 created_by, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference, payer, paid_to, amount, currency_code, paid_to_payload["exchange_rate_to_usd"],
                    paid_to_payload["amount_base"], date, clean_notes, "approved", payer_expense_id, paid_to_expense_id,
                    user_id, datetime.datetime.now().isoformat(),
                ),
            )
            details = f"{payer} سدّد عني إلى {paid_to}: {amount} {currency_code} | {reference}"
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, user.get("username", ""), "سداد بالنيابة", "third_party_payments", None, details, "127.0.0.1", datetime.datetime.now().isoformat()),
            )
            conn.commit()
            return {
                "ok": True,
                "reference": reference,
                "payer_expense_id": payer_expense_id,
                "paid_to_expense_id": paid_to_expense_id,
                "amount_base": paid_to_payload["amount_base"],
                "exchange_rate_to_usd": paid_to_payload["exchange_rate_to_usd"],
            }
        except Exception:
            conn.rollback()
            raise

    def reverse_payment_on_behalf(self, reference: str, user_id: int | None = None, date: str | None = None) -> Dict:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع عملية السداد بالنيابة مطلوب")
        if self.data.is_remote():
            return self.db.get_rest_client().reverse_third_party_payment(reference)
        if user_id is None:
            user_id = (self._current_user() or {}).get("id") or 1
        date = date or datetime.datetime.now().strftime("%Y-%m-%d")
        conn = self.db.get_connection()
        user = self._current_user()
        row = conn.execute("SELECT * FROM third_party_payments WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على عملية السداد بالنيابة")
        row = dict(row)
        if row.get("status") == "reversed":
            raise ValueError("هذه العملية معكوسة مسبقاً")
        amount = float(row["amount_original"])
        code = row["currency_original"]
        payer = row["payer_company_name"]
        paid_to = row["paid_to_company_name"]
        reversal_ref = f"REV-{reference}"
        try:
            conn.execute("BEGIN IMMEDIATE")
            payer_payload = self._expense_payload(
                payer, amount, "incoming", date, f"عكس سداد بالنيابة: {reference}", code, user_id,
                source_ref=reference, counterparty=paid_to, source_type=self.REVERSAL_SOURCE_TYPE,
            )
            paid_to_payload = self._expense_payload(
                paid_to, amount, "outgoing", date, f"عكس سداد بالنيابة: {reference}", code, user_id,
                source_ref=reference, counterparty=payer, source_type=self.REVERSAL_SOURCE_TYPE,
            )
            self._insert_expense(conn, payer_payload)
            self._insert_expense(conn, paid_to_payload)
            conn.execute("UPDATE third_party_payments SET status='reversed', reversed_at=?, reversal_ref=? WHERE reference=?", (datetime.datetime.now().isoformat(), reversal_ref, reference))
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, user.get("username", ""), "عكس سداد بالنيابة", "third_party_payments", row.get("id"), reference, "127.0.0.1", datetime.datetime.now().isoformat()),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "reversal_ref": reversal_ref}
        except Exception:
            conn.rollback()
            raise
