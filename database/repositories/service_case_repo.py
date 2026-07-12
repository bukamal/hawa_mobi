# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Any, Dict, List

from database.repositories.base_repo import BaseRepository
from auth.session import UserSession
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import normalize_expense_metadata
from services.service_case_service import (
    SERVICE_CASE_SOURCE_CLIENT,
    SERVICE_CASE_SOURCE_SUPPLIER,
    SERVICE_CASE_REVERSAL,
    SERVICE_CASE_OPERATION_CLIENT,
    SERVICE_CASE_OPERATION_SUPPLIER,
    SERVICE_CASE_OPERATION_REVERSAL,
    SERVICE_CASE_STATUS_REVERSED,
    build_client_note,
    build_supplier_note,
    client_print_description,
    supplier_print_description,
    internal_note,
    new_service_case_reference,
    validate_service_case_payload,
)


class ServiceCaseRepository(BaseRepository):
    """Create and reverse intermediary travel-service cases.

    A service case creates two locked ledger rows with one reference:
    - client row: incoming / لنا على الشركة العميلة
    - supplier row: outgoing / له للشركة المورّدة
    """

    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _insert_expense(self, conn, payload: Dict[str, Any]) -> int:
        payload = normalize_expense_metadata(payload)
        cur = conn.execute(
            """INSERT INTO expenses
            (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note, source_type, source_ref, counterparty_company_name,
             person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by,
             print_description, internal_note, service_case_role, linked_company_name)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                payload["company_name"], payload["amount"], payload.get("amount_base", payload["amount"]), payload["type"], payload["date"], payload.get("notes", ""), payload["currency"],
                payload.get("created_by"), payload.get("created_at"), payload.get("updated_by"), payload.get("updated_at"),
                payload.get("amount_original", payload["amount"]), payload.get("currency_original", payload["currency"]), payload.get("exchange_rate_to_usd", 1.0),
                payload.get("status", "approved"), payload.get("payment_due_date"), payload.get("payment_reminder_note"),
                payload.get("source_type"), payload.get("source_ref"), payload.get("counterparty_company_name"),
                payload.get("person_name"), payload.get("person_name_search"), payload.get("service_type"), payload.get("operation_type"),
                payload.get("is_locked", 1), payload.get("reversal_of"), payload.get("reversed_by"),
                payload.get("print_description"), payload.get("internal_note"), payload.get("service_case_role"), payload.get("linked_company_name"),
            ),
        )
        return int(cur.lastrowid)

    def add(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = validate_service_case_payload(data)
        user = UserSession.get_current() or {}
        uid = user.get("id") or data.get("created_by") or 1
        now = datetime.datetime.now().isoformat()

        if self.data.is_remote():
            return self.db.get_rest_client().add_service_case(dict(payload, created_by=uid))

        reference = new_service_case_reference()
        conn = self.db.get_connection()
        client_payload = self.ledger.normalize_expense_payload({
            "company_name": payload["client_company_name"],
            "amount": payload["sale_amount_original"],
            "type": "incoming",
            "date": payload["date"],
            "notes": build_client_note(reference, payload),
            "currency": payload["currency_original"],
            "created_by": uid,
            "created_at": now,
            "updated_by": uid,
            "updated_at": now,
            "source_type": SERVICE_CASE_SOURCE_CLIENT,
            "source_ref": reference,
            "counterparty_company_name": payload["supplier_company_name"],
            "person_name": payload["person_name"],
            "service_type": payload["service_type"],
            "operation_type": SERVICE_CASE_OPERATION_CLIENT,
            "is_locked": 1,
            "print_description": client_print_description(payload),
            "service_case_role": "client",
            "linked_company_name": payload["supplier_company_name"],
        })
        supplier_payload = self.ledger.normalize_expense_payload({
            "company_name": payload["supplier_company_name"],
            "amount": payload["cost_amount_original"],
            "type": "outgoing",
            "date": payload["date"],
            "notes": build_supplier_note(reference, payload),
            "currency": payload["currency_original"],
            "created_by": uid,
            "created_at": now,
            "updated_by": uid,
            "updated_at": now,
            "source_type": SERVICE_CASE_SOURCE_SUPPLIER,
            "source_ref": reference,
            "counterparty_company_name": payload["client_company_name"],
            "person_name": payload["person_name"],
            "service_type": payload["service_type"],
            "operation_type": SERVICE_CASE_OPERATION_SUPPLIER,
            "is_locked": 1,
            "print_description": supplier_print_description(payload),
            "service_case_role": "supplier",
            "linked_company_name": payload["client_company_name"],
        })
        note = internal_note(reference, payload, client_payload.get("amount_base"), supplier_payload.get("amount_base"))
        client_payload["internal_note"] = note
        supplier_payload["internal_note"] = note
        try:
            conn.execute("BEGIN IMMEDIATE")
            client_expense_id = self._insert_expense(conn, client_payload)
            supplier_expense_id = self._insert_expense(conn, supplier_payload)
            conn.execute(
                """INSERT INTO service_cases
                (reference, client_company_name, supplier_company_name, person_name, service_type,
                 sale_amount_original, cost_amount_original, currency_original, exchange_rate_to_usd,
                 sale_amount_base, cost_amount_base, date, notes, status, client_expense_id, supplier_expense_id,
                 created_by, created_at, print_description_client, print_description_supplier, internal_note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference, payload["client_company_name"], payload["supplier_company_name"], payload["person_name"], payload["service_type"],
                    payload["sale_amount_original"], payload["cost_amount_original"], payload["currency_original"], client_payload.get("exchange_rate_to_usd", 1.0),
                    client_payload.get("amount_base", 0), supplier_payload.get("amount_base", 0), payload["date"], payload.get("notes", ""), "open",
                    client_expense_id, supplier_expense_id, uid, now, client_print_description(payload), supplier_print_description(payload), note,
                ),
            )
            self.db._log_audit_local(uid, user.get("username", ""), "إضافة ملف خدمة", "service_cases", None, f"{reference}: {payload['client_company_name']} / {payload['supplier_company_name']}")
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": client_expense_id, "supplier_expense_id": supplier_expense_id, "profit_base": client_payload.get("amount_base", 0) - supplier_payload.get("amount_base", 0)}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def list_cases(self) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_service_cases()
        rows = self.db.get_connection().execute("SELECT * FROM service_cases ORDER BY date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

    def reverse(self, reference: str) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع ملف الخدمة مطلوب")
        if self.data.is_remote():
            return self.db.get_rest_client().reverse_service_case(reference)
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على ملف الخدمة")
        row = dict(row)
        if row.get("status") == SERVICE_CASE_STATUS_REVERSED:
            raise ValueError("ملف الخدمة معكوس مسبقاً")
        user = UserSession.get_current() or {}
        uid = user.get("id") or 1
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        now = datetime.datetime.now().isoformat()
        reversal_ref = f"REV-{reference}"
        client_rev = self.ledger.normalize_expense_payload({
            "company_name": row["client_company_name"], "amount": row["sale_amount_original"], "type": "outgoing", "date": date,
            "notes": f"عكس ملف خدمة {reference}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
            "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["supplier_company_name"],
            "person_name": row["person_name"], "service_type": row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
            "is_locked": 1, "print_description": f"عكس {row.get('print_description_client') or row.get('service_type')}", "service_case_role": "client_reversal", "linked_company_name": row["supplier_company_name"], "internal_note": f"عكس ملف خدمة {reference}",
        })
        supplier_rev = self.ledger.normalize_expense_payload({
            "company_name": row["supplier_company_name"], "amount": row["cost_amount_original"], "type": "incoming", "date": date,
            "notes": f"عكس ملف خدمة {reference}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
            "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["client_company_name"],
            "person_name": row["person_name"], "service_type": row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
            "is_locked": 1, "print_description": f"عكس {row.get('print_description_supplier') or row.get('service_type')}", "service_case_role": "supplier_reversal", "linked_company_name": row["client_company_name"], "internal_note": f"عكس ملف خدمة {reference}",
        })
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._insert_expense(conn, client_rev)
            self._insert_expense(conn, supplier_rev)
            conn.execute("UPDATE service_cases SET status=?, reversed_at=?, reversal_ref=? WHERE reference=?", (SERVICE_CASE_STATUS_REVERSED, now, reversal_ref, reference))
            self.db._log_audit_local(uid, user.get("username", ""), "عكس ملف خدمة", "service_cases", row.get("id"), reference)
            conn.commit()
            return {"ok": True, "reference": reference, "reversal_ref": reversal_ref}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
