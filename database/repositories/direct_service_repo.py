# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from auth.session import UserSession
from database.repositories.base_repo import BaseRepository
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import normalize_expense_metadata
from services.payment_service import delete_payments_for_targets, enrich_expenses_with_payments, get_payment_summary, insert_payment_in_transaction, sync_payment_state
from services.direct_customer_service import (
    DIRECT_SERVICE_OPERATION_CLIENT,
    DIRECT_SERVICE_OPERATION_SUPPLIER,
    DIRECT_SERVICE_OPERATION_REVERSAL,
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

    Normal ledger rows remain pure receivable/payable entries. Profit is tracked
    only for direct-service records that include sale/cost metadata.

    Phase 91 adds safe correction support: edit/reverse the direct service as a
    single linked operation, never the generated ledger entries individually.
    """

    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _current_user(self) -> Dict[str, Any]:
        return UserSession.get_current() or {}

    def _uid(self, data: Optional[Dict[str, Any]] = None, key: str = "created_by") -> int:
        data = data or {}
        user = self._current_user()
        return int(user.get("id") or data.get(key) or data.get("user_id") or 1)

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

    def _update_expense(self, conn, expense_id: int, payload: Dict[str, Any]) -> None:
        payload = normalize_expense_metadata(payload)
        cur = conn.execute(
            """UPDATE expenses SET
            company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?,
            updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?,
            status=?, payment_due_date=?, payment_reminder_note=?, source_type=?, source_ref=?, counterparty_company_name=?,
            person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?,
            print_description=?, internal_note=?, service_case_role=?, linked_company_name=?
            WHERE id=?""",
            (
                payload["company_name"], payload["amount"], payload.get("amount_base", payload["amount"]), payload["type"], payload["date"], payload.get("notes", ""), payload["currency"],
                payload.get("updated_by"), payload.get("updated_at"), payload.get("amount_original", payload["amount"]), payload.get("currency_original", payload["currency"]), payload.get("exchange_rate_to_usd", 1.0),
                payload.get("status", "approved"), payload.get("payment_due_date"), payload.get("payment_reminder_note"), payload.get("source_type"), payload.get("source_ref"), payload.get("counterparty_company_name"),
                payload.get("person_name"), payload.get("person_name_search"), payload.get("service_type"), payload.get("operation_type"), payload.get("is_locked", 1), payload.get("reversal_of"), payload.get("reversed_by"),
                payload.get("print_description"), payload.get("internal_note"), payload.get("service_case_role"), payload.get("linked_company_name"), int(expense_id),
            ),
        )
        if cur.rowcount != 1:
            raise ValueError(f"تعذر تحديث القيد المرتبط id={expense_id}")

    def _build_payloads(self, reference: str, payload: Dict[str, Any], uid: int, now: str, *, existing_client: Optional[Dict[str, Any]] = None, existing_supplier: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], float, float, float]:
        supplier_only = bool(payload.get("supplier_only"))

        client_payload = None
        if not supplier_only:
            client_payload = self.ledger.normalize_expense_payload({
                "company_name": payload["company_name"],
                "amount": payload["sale_amount_original"],
                "type": "incoming",
                "date": payload["date"],
                "notes": client_note(reference, payload),
                "currency": payload["currency_original"],
                "created_by": (existing_client or {}).get("created_by") or uid,
                "created_at": (existing_client or {}).get("created_at") or now,
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
                "payment_due_date": payload.get("client_due_date") or None,
                "payment_reminder_note": payload.get("payment_reminder_note"),
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
                "created_by": (existing_supplier or {}).get("created_by") or uid,
                "created_at": (existing_supplier or {}).get("created_at") or now,
                "updated_by": uid,
                "updated_at": now,
                "source_type": DIRECT_SERVICE_SOURCE_SUPPLIER,
                "source_ref": reference,
                "counterparty_company_name": "زبون مباشر" if supplier_only else payload["company_name"],
                "person_name": payload["person_name"],
                "service_type": payload["service_type"],
                "operation_type": DIRECT_SERVICE_OPERATION_SUPPLIER,
                "is_locked": 1,
                "print_description": f"تكلفة {payload.get('service_type')} - {payload.get('person_name')}",
                "service_case_role": "direct_supplier",
                "linked_company_name": "زبون مباشر" if supplier_only else payload["company_name"],
                "payment_due_date": payload.get("supplier_due_date") or None,
                "payment_reminder_note": payload.get("payment_reminder_note"),
            })

        if client_payload:
            sale_base = float(client_payload.get("amount_base") or 0)
            rate = float(client_payload.get("exchange_rate_to_usd") or 1.0)
        elif supplier_payload:
            # Supplier-only direct service: no customer/company receivable row is
            # created.  Use the supplier row exchange-rate snapshot to convert
            # the internal sale value into base currency for profit reporting.
            rate = float(supplier_payload.get("exchange_rate_to_usd") or 1.0)
            sale_base = self.ledger.to_base(float(payload.get("sale_amount_original") or 0), payload["currency_original"], rate)
        else:
            # No supplier cost row either; still keep an internal profit record.
            rate = 1.0
            sale_base = self.ledger.to_base(float(payload.get("sale_amount_original") or 0), payload["currency_original"], rate)

        if supplier_payload:
            cost_base = float(supplier_payload.get("amount_base") or 0)
            rate = float(supplier_payload.get("exchange_rate_to_usd") or rate or 1.0)
        else:
            cost_base = self.ledger.to_base(float(payload.get("cost_amount_original") or 0), payload["currency_original"], rate)

        note = internal_note(reference, payload, sale_base, cost_base)
        if client_payload:
            client_payload["internal_note"] = note
        if supplier_payload:
            supplier_payload["internal_note"] = note
        return client_payload, supplier_payload, sale_base, cost_base, rate

    def _row_by_id(self, conn, expense_id) -> Optional[Dict[str, Any]]:
        if not expense_id:
            return None
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        return dict(row) if row else None

    def _linked_rows(self, conn, service: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        reference = service["reference"]
        client = self._row_by_id(conn, service.get("client_expense_id"))
        supplier = self._row_by_id(conn, service.get("supplier_expense_id"))
        rows = conn.execute("SELECT * FROM expenses WHERE source_ref=? AND source_type IN (?,?) ORDER BY id", (reference, DIRECT_SERVICE_SOURCE_CLIENT, DIRECT_SERVICE_SOURCE_SUPPLIER)).fetchall()
        for r in rows:
            rr = dict(r)
            if rr.get("source_type") == DIRECT_SERVICE_SOURCE_CLIENT and not client:
                client = rr
            elif rr.get("source_type") == DIRECT_SERVICE_SOURCE_SUPPLIER and not supplier:
                supplier = rr
        supplier_only = (not service.get("client_expense_id")) and bool(service.get("supplier_company_name"))
        if not supplier_only and not client:
            raise ValueError("تعذر العثور على قيد العميل المرتبط بالخدمة المباشرة")
        if client and (client.get("source_ref") != reference or client.get("source_type") != DIRECT_SERVICE_SOURCE_CLIENT or client.get("type") != "incoming"):
            raise ValueError("ترابط قيد العميل للخدمة المباشرة غير صحيح")
        if supplier:
            if supplier.get("source_ref") != reference or supplier.get("source_type") != DIRECT_SERVICE_SOURCE_SUPPLIER or supplier.get("type") != "outgoing":
                raise ValueError("ترابط قيد المورد للخدمة المباشرة غير صحيح")
        if supplier_only and float(service.get("cost_amount_original") or 0) > 0 and not supplier:
            raise ValueError("تعذر العثور على قيد المورد المرتبط بالخدمة المباشرة")
        return client, supplier

    def add(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = validate_direct_service_payload(data)
        uid = self._uid(data, "created_by")
        user = self._current_user()
        now = datetime.datetime.now().isoformat()
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "add_direct_service"):
                return client.add_direct_service(dict(payload, created_by=uid))
            raise RuntimeError("الخدمة المباشرة تحتاج تحديث Windows Server/API قبل استخدامها في وضع العميل")

        reference = new_direct_service_reference()
        conn = self.db.get_connection()
        client_payload, supplier_payload, sale_base, cost_base, rate = self._build_payloads(reference, payload, uid, now)

        try:
            conn.execute("BEGIN IMMEDIATE")
            client_expense_id = self._insert_expense(conn, client_payload) if client_payload else None
            supplier_expense_id = self._insert_expense(conn, supplier_payload) if supplier_payload else None
            if client_expense_id and float(payload.get("client_paid_amount") or 0) > 0:
                target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (client_expense_id,)).fetchone())
                insert_payment_in_transaction(conn, target, payload.get("client_paid_amount"), date=payload["date"], payment_method=payload.get("payment_method") or "cash", notes="دفعة أولى من المسافر", user_id=uid, username=user.get("username", ""), now=now)
            elif client_expense_id:
                sync_payment_state(conn, client_expense_id, now=now)
            if supplier_expense_id and float(payload.get("supplier_paid_amount") or 0) > 0:
                target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (supplier_expense_id,)).fetchone())
                insert_payment_in_transaction(conn, target, payload.get("supplier_paid_amount"), date=payload["date"], payment_method=payload.get("payment_method") or "cash", notes="دفعة أولى للمورد", user_id=uid, username=user.get("username", ""), now=now)
            elif supplier_expense_id:
                sync_payment_state(conn, supplier_expense_id, now=now)
            note_payload = client_payload or supplier_payload or {"internal_note": internal_note(reference, payload, sale_base, cost_base)}
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
                    client_expense_id, payload.get("supplier_company_name") or "", supplier_expense_id, uid, now, note_payload.get("internal_note", ""),
                ),
            )
            self.db._log_audit_local(uid, user.get("username", ""), "إضافة خدمة مباشرة", "direct_services", None, f"{reference}: {payload['company_name']} / {payload['person_name']}")
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": client_expense_id, "supplier_expense_id": supplier_expense_id, "profit_base": sale_base - cost_base, "supplier_only": bool(payload.get("supplier_only"))}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def list_services(self) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "get_direct_services"):
                return client.get_direct_services()
            return []
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM direct_services ORDER BY date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

    def get_by_reference(self, reference: str) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع الخدمة المباشرة مطلوب")
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "get_direct_service"):
                return client.get_direct_service(reference)
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM direct_services WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على الخدمة المباشرة")
        out = dict(row)
        entries = conn.execute("SELECT * FROM expenses WHERE source_ref=? AND source_type IN (?, ?, ?) ORDER BY id", (reference, DIRECT_SERVICE_SOURCE_CLIENT, DIRECT_SERVICE_SOURCE_SUPPLIER, DIRECT_SERVICE_REVERSAL)).fetchall()
        out["entries"] = enrich_expenses_with_payments(conn, [dict(r) for r in entries])
        for entry in out["entries"]:
            if int(entry.get("id") or 0) == int(out.get("client_expense_id") or 0):
                out["client_entry"] = entry
            if int(entry.get("id") or 0) == int(out.get("supplier_expense_id") or 0):
                out["supplier_entry"] = entry
        return out

    def update(self, reference: str, data: Dict[str, Any], edit_reason: str = "", user_id: int | None = None) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع الخدمة المباشرة مطلوب")
        reason = str(edit_reason or data.get("edit_reason") or "").strip()
        if not reason:
            raise ValueError("سبب تعديل الخدمة المباشرة مطلوب")
        payload = validate_direct_service_payload(data)
        uid = int(user_id or self._uid(data, "updated_by"))
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "update_direct_service"):
                return client.update_direct_service(reference, dict(payload, edit_reason=reason, updated_by=uid))
            raise RuntimeError("خادم ويندوز لا يدعم تعديل الخدمة المباشرة بعد. حدّث الخادم إلى النسخة الحالية.")
        conn = self.db.get_connection()
        user = self._current_user()
        row = conn.execute("SELECT * FROM direct_services WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على الخدمة المباشرة")
        service = dict(row)
        if service.get("status") == DIRECT_SERVICE_STATUS_REVERSED:
            raise ValueError("لا يمكن تعديل خدمة مباشرة معكوسة. أنشئ خدمة جديدة بدلاً منها.")
        client_entry, supplier_entry = self._linked_rows(conn, service)
        if client_entry:
            client_summary = get_payment_summary(conn, client_entry)
            if float(payload.get("sale_amount_original") or 0) + 0.005 < float(client_summary.get("paid_amount_original") or 0):
                raise ValueError("سعر البيع الجديد أقل من دفعات المسافر المسجلة")
            if payload.get("currency_original") != client_entry.get("currency_original") and float(client_summary.get("paid_amount_original") or 0) > 0:
                raise ValueError("لا يمكن تغيير عملة خدمة عليها دفعات مسافر")
        if supplier_entry:
            supplier_summary = get_payment_summary(conn, supplier_entry)
            if float(payload.get("cost_amount_original") or 0) + 0.005 < float(supplier_summary.get("paid_amount_original") or 0):
                raise ValueError("تكلفة المورد الجديدة أقل من الدفعات المسجلة للمورد")
            supplier_changed = (payload.get("supplier_company_name") or "") != (supplier_entry.get("company_name") or "")
            if (supplier_changed or not payload.get("supplier_company_name")) and float(supplier_summary.get("paid_amount_original") or 0) > 0:
                raise ValueError("لا يمكن تغيير أو إزالة المورد قبل حذف دفعاته المسجلة")
        before = {
            "company_name": service.get("company_name"), "person_name": service.get("person_name"), "service_type": service.get("service_type"),
            "sale_amount_original": service.get("sale_amount_original"), "cost_amount_original": service.get("cost_amount_original"),
            "currency_original": service.get("currency_original"), "date": service.get("date"), "supplier_company_name": service.get("supplier_company_name") or "", "notes": service.get("notes") or "",
        }
        now = datetime.datetime.now().isoformat()
        client_payload, supplier_payload, sale_base, cost_base, rate = self._build_payloads(reference, payload, uid, now, existing_client=client_entry, existing_supplier=supplier_entry)
        note_payload = client_payload or supplier_payload or {"internal_note": internal_note(reference, payload, sale_base, cost_base)}
        try:
            conn.execute("BEGIN IMMEDIATE")
            client_expense_id = service.get("client_expense_id")
            if client_payload:
                if client_entry:
                    self._update_expense(conn, int(client_entry["id"]), client_payload)
                    client_expense_id = int(client_entry["id"])
                else:
                    client_expense_id = self._insert_expense(conn, client_payload)
            elif client_entry:
                conn.execute("DELETE FROM expenses WHERE id=? AND source_ref=? AND source_type=?", (int(client_entry["id"]), reference, DIRECT_SERVICE_SOURCE_CLIENT))
                client_expense_id = None

            supplier_expense_id = service.get("supplier_expense_id")
            if supplier_payload:
                if supplier_entry:
                    self._update_expense(conn, int(supplier_entry["id"]), supplier_payload)
                    supplier_expense_id = int(supplier_entry["id"])
                else:
                    supplier_expense_id = self._insert_expense(conn, supplier_payload)
            elif supplier_entry:
                conn.execute("DELETE FROM expenses WHERE id=? AND source_ref=? AND source_type=?", (int(supplier_entry["id"]), reference, DIRECT_SERVICE_SOURCE_SUPPLIER))
                supplier_expense_id = None
            if client_expense_id:
                sync_payment_state(conn, int(client_expense_id), now=now)
            if supplier_expense_id:
                sync_payment_state(conn, int(supplier_expense_id), now=now)
            conn.execute(
                """UPDATE direct_services SET
                company_name=?, person_name=?, service_type=?, sale_amount_original=?, cost_amount_original=?,
                currency_original=?, exchange_rate_to_usd=?, sale_amount_base=?, cost_amount_base=?, date=?, notes=?,
                client_expense_id=?, supplier_company_name=?, supplier_expense_id=?, updated_by=?, updated_at=?, edit_reason=?, internal_note=?
                WHERE reference=?""",
                (
                    payload["company_name"], payload["person_name"], payload["service_type"], payload["sale_amount_original"], payload["cost_amount_original"],
                    payload["currency_original"], rate, sale_base, cost_base, payload["date"], payload.get("notes", ""),
                    client_expense_id, payload.get("supplier_company_name") or "", supplier_expense_id, uid, now, reason, note_payload.get("internal_note", ""), reference,
                ),
            )
            details = (
                f"{reference} | السبب: {reason} | قبل: {before['company_name']} / {before['person_name']} / "
                f"بيع {before['sale_amount_original']} {before['currency_original']} / تكلفة {before['cost_amount_original']} / مورد {before['supplier_company_name'] or 'داخلي'} بتاريخ {before['date']} | "
                f"بعد: {payload['company_name']} / {payload['person_name']} / بيع {payload['sale_amount_original']} {payload['currency_original']} / تكلفة {payload['cost_amount_original']} / مورد {payload.get('supplier_company_name') or 'داخلي'} بتاريخ {payload['date']}"
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "تعديل خدمة مباشرة", "direct_services", service.get("id"), details, "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": client_expense_id, "supplier_expense_id": supplier_expense_id, "profit_base": sale_base - cost_base, "supplier_only": bool(payload.get("supplier_only"))}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def delete(self, reference: str, user_id: int | None = None, reason: str = "") -> Dict[str, Any]:
        """Delete a direct-service operation and every generated ledger row.

        This is an explicit destructive correction requested by the user.  It
        never creates reversal entries.  The source record, client/supplier
        rows, historical reversal rows (if any), and reminders are removed in
        one SQLite transaction while a compact audit snapshot is retained.
        """
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع الخدمة المباشرة مطلوب")
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب حذف الخدمة المباشرة مطلوب")
        uid = int(user_id or self._uid({}, "updated_by"))
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "delete_direct_service"):
                return client.delete_direct_service(reference, {"reason": clean_reason})
            raise RuntimeError("خادم ويندوز لا يدعم حذف الخدمة المباشرة بعد. حدّث الخادم إلى النسخة الحالية.")

        conn = self.db.get_connection()
        user = self._current_user()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM direct_services WHERE reference=?", (reference,)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على الخدمة المباشرة")
            service = dict(row)
            expense_ids = {
                int(value) for value in (service.get("client_expense_id"), service.get("supplier_expense_id"))
                if value not in (None, "")
            }
            linked = conn.execute(
                "SELECT id FROM expenses WHERE source_ref=? AND source_type IN (?,?,?)",
                (reference, DIRECT_SERVICE_SOURCE_CLIENT, DIRECT_SERVICE_SOURCE_SUPPLIER, DIRECT_SERVICE_REVERSAL),
            ).fetchall()
            expense_ids.update(int(r["id"]) for r in linked)
            payment_counts = delete_payments_for_targets(conn, expense_ids)
            if expense_ids:
                placeholders = ",".join("?" for _ in expense_ids)
                params = tuple(sorted(expense_ids))
                conn.execute(f"DELETE FROM payment_reminders WHERE expense_id IN ({placeholders})", params)
                conn.execute(f"DELETE FROM expenses WHERE id IN ({placeholders})", params)
            conn.execute("DELETE FROM direct_services WHERE reference=?", (reference,))
            now = datetime.datetime.now().isoformat()
            details = (
                f"{reference} | السبب: {clean_reason} | الشركة: {service.get('company_name')} | "
                f"المورد: {service.get('supplier_company_name') or '-'} | القيود المحذوفة: {len(expense_ids)} | الدفعات المحذوفة: {payment_counts['payments']}"
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "حذف خدمة مباشرة", "direct_services", service.get("id"), details, "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "deleted_expenses": len(expense_ids)}
        except Exception:
            conn.rollback()
            raise

    def reverse(self, reference: str, user_id: int | None = None, date: str | None = None, reason: str = "") -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع الخدمة المباشرة مطلوب")
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب عكس الخدمة المباشرة مطلوب")
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "reverse_direct_service"):
                return client.reverse_direct_service(reference, {"reason": clean_reason, "date": date})
            raise RuntimeError("خادم ويندوز لا يدعم عكس الخدمة المباشرة بعد. حدّث الخادم إلى النسخة الحالية.")
        uid = int(user_id or self._uid({}, "updated_by"))
        conn = self.db.get_connection()
        user = self._current_user()
        try:
            # Lock before reading the status so a repeated tap or another
            # device cannot create a second reversal for this reference.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM direct_services WHERE reference=?", (reference,)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على الخدمة المباشرة")
            service = dict(row)
            if service.get("status") == DIRECT_SERVICE_STATUS_REVERSED:
                raise ValueError("هذه الخدمة المباشرة معكوسة مسبقاً")
            client_entry, supplier_entry = self._linked_rows(conn, service)
            date = str(date or datetime.datetime.now().strftime("%Y-%m-%d")).strip()[:10]
            now = datetime.datetime.now().isoformat()
            reversal_ref = f"REV-{reference}"
            client_rev_id = None
            if client_entry:
                client_rev = self.ledger.normalize_expense_payload({
                    "company_name": service["company_name"], "amount": service["sale_amount_original"], "type": "outgoing", "date": date,
                    "notes": f"عكس خدمة مباشرة: {reference}. السبب: {clean_reason}", "currency": service["currency_original"],
                    "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
                    "source_type": DIRECT_SERVICE_REVERSAL, "source_ref": reference, "counterparty_company_name": service.get("supplier_company_name") or "تكلفة داخلية",
                    "person_name": service["person_name"], "service_type": service["service_type"], "operation_type": DIRECT_SERVICE_OPERATION_REVERSAL,
                    "is_locked": 1, "print_description": f"عكس {service.get('service_type') or 'خدمة مباشرة'} - {service.get('person_name')}",
                    "service_case_role": "direct_client_reversal", "linked_company_name": service.get("supplier_company_name") or "", "internal_note": f"عكس خدمة مباشرة {reference}: {clean_reason}",
                })
                client_rev_id = self._insert_expense(conn, client_rev)
            supplier_rev_id = None
            if supplier_entry and float(service.get("cost_amount_original") or 0) > 0:
                supplier_rev = self.ledger.normalize_expense_payload({
                    "company_name": service.get("supplier_company_name") or supplier_entry.get("company_name"), "amount": service["cost_amount_original"], "type": "incoming", "date": date,
                    "notes": f"عكس تكلفة خدمة مباشرة: {reference}. السبب: {clean_reason}", "currency": service["currency_original"],
                    "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
                    "source_type": DIRECT_SERVICE_REVERSAL, "source_ref": reference, "counterparty_company_name": service["company_name"],
                    "person_name": service["person_name"], "service_type": service["service_type"], "operation_type": DIRECT_SERVICE_OPERATION_REVERSAL,
                    "is_locked": 1, "print_description": f"عكس تكلفة {service.get('service_type') or 'خدمة مباشرة'} - {service.get('person_name')}",
                    "service_case_role": "direct_supplier_reversal", "linked_company_name": service["company_name"], "internal_note": f"عكس خدمة مباشرة {reference}: {clean_reason}",
                })
                supplier_rev_id = self._insert_expense(conn, supplier_rev)
            changed = conn.execute(
                "UPDATE direct_services SET status=?, reversed_at=?, reversal_ref=?, updated_by=?, updated_at=?, edit_reason=? WHERE reference=? AND status<>?",
                (DIRECT_SERVICE_STATUS_REVERSED, now, reversal_ref, uid, now, clean_reason, reference, DIRECT_SERVICE_STATUS_REVERSED),
            )
            if changed.rowcount != 1:
                raise ValueError("تعذر عكس الخدمة؛ ربما عُكست من جهاز آخر")
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "عكس خدمة مباشرة", "direct_services", service.get("id"), f"{reference} | السبب: {clean_reason} | عكس القيود: {client_rev_id or '-'}/{supplier_rev_id or '-'}", "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "reversal_ref": reversal_ref, "client_reversal_expense_id": client_rev_id, "supplier_reversal_expense_id": supplier_rev_id}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
