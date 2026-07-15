# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Any, Dict, List

from auth.session import UserSession
from database.repositories.base_repo import BaseRepository
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import normalize_expense_metadata
from services.direct_customer_service import (
    DIRECT_SERVICE_OPERATION_CLIENT,
    DIRECT_SERVICE_OPERATION_SUPPLIER,
    DIRECT_SERVICE_REVERSAL,
    DIRECT_SERVICE_SOURCE_CLIENT,
    DIRECT_SERVICE_SOURCE_SUPPLIER,
    DIRECT_SERVICE_STATUS_OPEN,
    DIRECT_SERVICE_STATUS_REVERSED,
    client_note,
    internal_note,
    new_direct_service_reference,
    supplier_note,
    validate_direct_service_payload,
)


class DirectServiceRepository(BaseRepository):
    """Direct customer profit workflow.

    Normal ledger rows remain pure receivable/payable entries.  Profit is tracked
    only for direct-service records that include sale/cost metadata.
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
        payload = validate_direct_service_payload(data)
        user = UserSession.get_current() or {}
        uid = user.get("id") or data.get("created_by") or 1
        now = datetime.datetime.now().isoformat()
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "add_direct_service"):
                return client.add_direct_service(dict(payload, created_by=uid))
            raise RuntimeError("الخدمة المباشرة تحتاج تحديث Windows Server/API قبل استخدامها في وضع العميل")

        reference = new_direct_service_reference()
        conn = self.db.get_connection()

        client_payload = self.ledger.normalize_expense_payload({
            "company_name": payload["company_name"],
            "amount": payload["sale_amount_original"],
            "type": "incoming",
            "date": payload["date"],
            "notes": client_note(reference, payload),
            "currency": payload["currency_original"],
            "created_by": uid,
            "created_at": now,
            "updated_by": uid,
            "updated_at": now,
            "source_type": DIRECT_SERVICE_SOURCE_CLIENT,
            "source_ref": reference,
            "counterparty_company_name": payload.get("supplier_company_name") or "تكلفة داخلية",
            "person_name": payload["person_name"],
            "service_type": payload["service_type"],
            "operation_type": DIRECT_SERVICE_OPERATION_CLIENT,
            "is_locked": 1,
            "print_description": payload.get("print_description"),
            "service_case_role": "direct_client",
            "linked_company_name": payload.get("supplier_company_name") or "",
        })

        supplier_payload = None
        if payload.get("supplier_company_name") and float(payload.get("cost_amount_original") or 0) > 0:
            supplier_payload = self.ledger.normalize_expense_payload({
                "company_name": payload["supplier_company_name"],
                "amount": payload["cost_amount_original"],
                "type": "outgoing",
                "date": payload["date"],
                "notes": supplier_note(reference, payload),
                "currency": payload["currency_original"],
                "created_by": uid,
                "created_at": now,
                "updated_by": uid,
                "updated_at": now,
                "source_type": DIRECT_SERVICE_SOURCE_SUPPLIER,
                "source_ref": reference,
                "counterparty_company_name": payload["company_name"],
                "person_name": payload["person_name"],
                "service_type": payload["service_type"],
                "operation_type": DIRECT_SERVICE_OPERATION_SUPPLIER,
                "is_locked": 1,
                "print_description": f"تكلفة {payload.get('service_type')} - {payload.get('person_name')}",
                "service_case_role": "direct_supplier",
                "linked_company_name": payload["company_name"],
            })

        sale_base = float(client_payload.get("amount_base") or 0)
        if supplier_payload:
            cost_base = float(supplier_payload.get("amount_base") or 0)
            rate = float(supplier_payload.get("exchange_rate_to_usd") or client_payload.get("exchange_rate_to_usd") or 1.0)
        else:
            rate = float(client_payload.get("exchange_rate_to_usd") or 1.0)
            cost_base = self.ledger.to_base(float(payload.get("cost_amount_original") or 0), payload["currency_original"], rate)
        note = internal_note(reference, payload, sale_base, cost_base)
        client_payload["internal_note"] = note
        if supplier_payload:
            supplier_payload["internal_note"] = note

        try:
            conn.execute("BEGIN IMMEDIATE")
            client_expense_id = self._insert_expense(conn, client_payload)
            supplier_expense_id = self._insert_expense(conn, supplier_payload) if supplier_payload else None
            conn.execute(
                """INSERT INTO direct_services
                (reference, company_name, person_name, service_type, sale_amount_original, cost_amount_original,
                 currency_original, exchange_rate_to_usd, sale_amount_base, cost_amount_base, date, notes, status,
                 client_expense_id, supplier_company_name, supplier_expense_id, created_by, created_at, internal_note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference, payload["company_name"], payload["person_name"], payload["service_type"],
                    payload["sale_amount_original"], payload["cost_amount_original"], payload["currency_original"],
                    rate, sale_base, cost_base, payload["date"], payload.get("notes", ""), DIRECT_SERVICE_STATUS_OPEN,
                    client_expense_id, payload.get("supplier_company_name") or "", supplier_expense_id, uid, now, note,
                ),
            )
            self.db._log_audit_local(uid, user.get("username", ""), "إضافة خدمة مباشرة", "direct_services", None, f"{reference}: {payload['company_name']} / {payload['person_name']}")
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": client_expense_id, "supplier_expense_id": supplier_expense_id, "profit_base": sale_base - cost_base}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def list_services(self) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            # Remote API has not exposed this workflow yet; keep local app stable.
            return []
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM direct_services ORDER BY date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

    def get_by_reference(self, reference: str) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع الخدمة المباشرة مطلوب")
        row = self.db.get_connection().execute("SELECT * FROM direct_services WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على الخدمة المباشرة")
        return dict(row)
