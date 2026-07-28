# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List, Optional, Tuple

from database.repositories.base_repo import BaseRepository
from auth.session import UserSession
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import normalize_expense_metadata
from services.payment_service import delete_payments_for_targets, enrich_expenses_with_payments, get_payment_summary, insert_payment_in_transaction, sync_payment_state
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
    """Create and reverse professional travel-service cases.

    A service case creates one locked client ledger row with the total sale and
    one locked supplier ledger row per cost component.  This keeps the external
    client statement clean while preserving internal supplier payables and
    profitability per component.
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

    def _row_by_id(self, conn, expense_id) -> Optional[Dict[str, Any]]:
        if not expense_id:
            return None
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        return dict(row) if row else None

    def _client_row(self, conn, service: Dict[str, Any]) -> Dict[str, Any]:
        reference = service["reference"]
        client = self._row_by_id(conn, service.get("client_expense_id"))
        if not client:
            row = conn.execute(
                "SELECT * FROM expenses WHERE source_ref=? AND source_type=? ORDER BY id LIMIT 1",
                (reference, SERVICE_CASE_SOURCE_CLIENT),
            ).fetchone()
            client = dict(row) if row else None
        if not client:
            raise ValueError("تعذر العثور على قيد العميل المرتبط بملف الخدمة")
        if client.get("source_ref") != reference or client.get("source_type") != SERVICE_CASE_SOURCE_CLIENT or client.get("type") != "incoming":
            raise ValueError("ترابط قيد العميل لملف الخدمة غير صحيح")
        return client

    def _build_payloads(self, reference: str, payload: Dict[str, Any], uid: int, now: str, *, existing_client: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]], float, float, float, str]:
        supplier_summary = payload.get("supplier_summary") or payload.get("supplier_company_name")
        client_payload = self.ledger.normalize_expense_payload({
            "company_name": payload["client_company_name"],
            "amount": payload["sale_amount_original"],
            "type": "incoming",
            "date": payload["date"],
            "notes": build_client_note(reference, payload),
            "currency": payload["currency_original"],
            "created_by": (existing_client or {}).get("created_by") or uid,
            "created_at": (existing_client or {}).get("created_at") or now,
            "updated_by": uid,
            "updated_at": now,
            "source_type": SERVICE_CASE_SOURCE_CLIENT,
            "source_ref": reference,
            "counterparty_company_name": supplier_summary,
            "person_name": payload["person_name"],
            "service_type": payload["service_type"],
            "operation_type": SERVICE_CASE_OPERATION_CLIENT,
            "is_locked": 1,
            "print_description": client_print_description(payload),
            "service_case_role": "client",
            "linked_company_name": supplier_summary,
            "payment_due_date": payload.get("client_due_date") or None,
            "payment_reminder_note": payload.get("payment_reminder_note"),
        })
        supplier_payloads: List[Dict[str, Any]] = []
        for component in payload.get("components") or []:
            if float(component.get("cost_amount_original") or 0) <= 0:
                continue
            supplier_payload = self.ledger.normalize_expense_payload({
                "company_name": component["supplier_company_name"],
                "amount": component["cost_amount_original"],
                "type": "outgoing",
                "date": payload["date"],
                "notes": build_supplier_note(reference, payload, component),
                "currency": payload["currency_original"],
                "created_by": uid,
                "created_at": now,
                "updated_by": uid,
                "updated_at": now,
                "source_type": SERVICE_CASE_SOURCE_SUPPLIER,
                "source_ref": reference,
                "counterparty_company_name": payload["client_company_name"],
                "person_name": payload["person_name"],
                "service_type": component["service_type"],
                "operation_type": SERVICE_CASE_OPERATION_SUPPLIER,
                "is_locked": 1,
                "print_description": supplier_print_description(payload, component),
                "service_case_role": "supplier",
                "linked_company_name": payload["client_company_name"],
            })
            supplier_payloads.append({"component": component, "payload": supplier_payload})
        sale_base = float(client_payload.get("amount_base") or 0)
        cost_base = sum(float(x["payload"].get("amount_base") or 0) for x in supplier_payloads)
        rate = float(client_payload.get("exchange_rate_to_usd") or 1.0)
        note = internal_note(reference, payload, sale_base, cost_base)
        client_payload["internal_note"] = note
        for item in supplier_payloads:
            item["payload"]["internal_note"] = note
        return client_payload, supplier_payloads, sale_base, cost_base, rate, note

    def _insert_component(self, conn, reference: str, idx: int, component: Dict[str, Any], payload: Dict[str, Any], supplier_expense_id: int | None, supplier_payload: Dict[str, Any] | None) -> int:
        cur = conn.execute(
            """INSERT INTO service_case_components
            (service_case_ref, component_index, service_type, supplier_company_name,
             sale_amount_original, cost_amount_original, currency_original, exchange_rate_to_usd,
             sale_amount_base, cost_amount_base, supplier_expense_id, print_description_client,
             print_description_supplier, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                reference,
                int(idx),
                component.get("service_type"),
                component.get("supplier_company_name"),
                float(component.get("sale_amount_original") or 0),
                float(component.get("cost_amount_original") or 0),
                payload.get("currency_original"),
                float((supplier_payload or {}).get("exchange_rate_to_usd") or 1.0),
                0.0,  # client total is stored on service_cases; component sale base can be derived/report-only later
                float((supplier_payload or {}).get("amount_base") or 0),
                supplier_expense_id,
                component.get("print_description_client") or "",
                component.get("print_description_supplier") or "",
                component.get("notes") or "",
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
        supplier_summary = payload.get("supplier_summary") or payload.get("supplier_company_name")
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
            "counterparty_company_name": supplier_summary,
            "person_name": payload["person_name"],
            "service_type": payload["service_type"],
            "operation_type": SERVICE_CASE_OPERATION_CLIENT,
            "is_locked": 1,
            "print_description": client_print_description(payload),
            "service_case_role": "client",
            "linked_company_name": supplier_summary,
            "payment_due_date": payload.get("client_due_date") or None,
            "payment_reminder_note": payload.get("payment_reminder_note"),
        })

        supplier_payloads: List[Dict[str, Any]] = []
        for component in payload.get("components") or []:
            if float(component.get("cost_amount_original") or 0) <= 0:
                continue
            supplier_payload = self.ledger.normalize_expense_payload({
                "company_name": component["supplier_company_name"],
                "amount": component["cost_amount_original"],
                "type": "outgoing",
                "date": payload["date"],
                "notes": build_supplier_note(reference, payload, component),
                "currency": payload["currency_original"],
                "created_by": uid,
                "created_at": now,
                "updated_by": uid,
                "updated_at": now,
                "source_type": SERVICE_CASE_SOURCE_SUPPLIER,
                "source_ref": reference,
                "counterparty_company_name": payload["client_company_name"],
                "person_name": payload["person_name"],
                "service_type": component["service_type"],
                "operation_type": SERVICE_CASE_OPERATION_SUPPLIER,
                "is_locked": 1,
                "print_description": supplier_print_description(payload, component),
                "service_case_role": "supplier",
                "linked_company_name": payload["client_company_name"],
            })
            supplier_payloads.append({"component": component, "payload": supplier_payload})

        note = internal_note(reference, payload, client_payload.get("amount_base"), sum(float(x["payload"].get("amount_base") or 0) for x in supplier_payloads))
        client_payload["internal_note"] = note
        for item in supplier_payloads:
            item["payload"]["internal_note"] = note

        try:
            conn.execute("BEGIN IMMEDIATE")
            client_expense_id = self._insert_expense(conn, client_payload)
            if float(payload.get("client_paid_amount") or 0) > 0:
                target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (client_expense_id,)).fetchone())
                insert_payment_in_transaction(conn, target, payload.get("client_paid_amount"), date=payload["date"], payment_method=payload.get("payment_method") or "cash", notes="دفعة أولى على حساب الشركة", payer_type=payload.get("client_payer_type") or "traveler", payer_name=payload.get("client_payer_name") or payload.get("person_name") or "", user_id=uid, username=user.get("username", ""), now=now)
            else:
                sync_payment_state(conn, client_expense_id, now=now)
            supplier_expense_ids: List[int] = []
            first_supplier_expense_id = None
            component_rows = []
            for idx, component in enumerate(payload.get("components") or [], 1):
                supplier_expense_id = None
                supplier_payload_for_component = None
                for item in supplier_payloads:
                    if item["component"] is component:
                        supplier_payload_for_component = item["payload"]
                        supplier_expense_id = self._insert_expense(conn, supplier_payload_for_component)
                        supplier_expense_ids.append(supplier_expense_id)
                        if first_supplier_expense_id is None:
                            first_supplier_expense_id = supplier_expense_id
                        break
                component_rows.append((idx, component, supplier_expense_id, supplier_payload_for_component))
            for idx, component, supplier_expense_id, supplier_payload_for_component in component_rows:
                self._insert_component(conn, reference, idx, component, payload, supplier_expense_id, supplier_payload_for_component)
            for supplier_expense_id in supplier_expense_ids:
                sync_payment_state(conn, supplier_expense_id, now=now)

            sale_base = float(client_payload.get("amount_base") or 0)
            cost_base = sum(float(x["payload"].get("amount_base") or 0) for x in supplier_payloads)
            conn.execute(
                """INSERT INTO service_cases
                (reference, client_company_name, supplier_company_name, person_name, service_type,
                 sale_amount_original, cost_amount_original, currency_original, exchange_rate_to_usd,
                 sale_amount_base, cost_amount_base, date, notes, status, client_expense_id, supplier_expense_id,
                 created_by, created_at, print_description_client, print_description_supplier, internal_note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference, payload["client_company_name"], supplier_summary, payload["person_name"], payload["service_type"],
                    payload["sale_amount_original"], payload["cost_amount_original"], payload["currency_original"], client_payload.get("exchange_rate_to_usd", 1.0),
                    sale_base, cost_base, payload["date"], payload.get("notes", ""), "open",
                    client_expense_id, first_supplier_expense_id, uid, now, client_print_description(payload), "تفاصيل حسب بنود الخدمة", note,
                ),
            )
            self.db._log_audit_local(uid, user.get("username", ""), "إضافة ملف خدمة", "service_cases", None, f"{reference}: {payload['client_company_name']} / {supplier_summary}")
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": client_expense_id, "supplier_expense_id": first_supplier_expense_id, "supplier_expense_ids": supplier_expense_ids, "profit_base": sale_base - cost_base}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def list_cases(self) -> List[Dict[str, Any]]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_service_cases()
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM service_cases ORDER BY date DESC, id DESC").fetchall()
        cases = [dict(r) for r in rows]
        for case in cases:
            comps = conn.execute("SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index", (case["reference"],)).fetchall()
            case["components"] = [dict(c) for c in comps]
            if case["components"]:
                case["components_summary"] = " ؛ ".join(
                    f"{c.get('service_type')} / {c.get('supplier_company_name') or '-'} / تكلفة {c.get('cost_amount_original')}"
                    for c in case["components"]
                )
            if case.get("client_expense_id"):
                client = conn.execute("SELECT * FROM expenses WHERE id=?", (case["client_expense_id"],)).fetchone()
                if client:
                    case["client_entry"] = enrich_expenses_with_payments(conn, [dict(client)])[0]
        return cases

    def get_by_reference(self, reference: str) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع ملف الخدمة مطلوب")
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "get_service_case"):
                return client.get_service_case(reference)
            cases = client.get_service_cases()
            for case in cases:
                if str(case.get("reference") or "") == reference:
                    return case
            raise ValueError("لم يتم العثور على ملف الخدمة")
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على ملف الخدمة")
        case = dict(row)
        comps = conn.execute("SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index", (reference,)).fetchall()
        case["components"] = [dict(c) for c in comps]
        if case.get("client_expense_id"):
            client = conn.execute("SELECT * FROM expenses WHERE id=?", (case["client_expense_id"],)).fetchone()
            if client:
                case["client_entry"] = enrich_expenses_with_payments(conn, [dict(client)])[0]
        return case

    def update(self, reference: str, data: Dict[str, Any], edit_reason: str = "", user_id: int | None = None) -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع ملف الخدمة مطلوب")
        reason = str(edit_reason or data.get("edit_reason") or "").strip()
        if not reason:
            raise ValueError("سبب تعديل ملف الخدمة مطلوب")
        payload = validate_service_case_payload(data)
        uid = int(user_id or (UserSession.get_current() or {}).get("id") or data.get("updated_by") or 1)
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "update_service_case"):
                return client.update_service_case(reference, dict(payload, edit_reason=reason, updated_by=uid))
            raise RuntimeError("خادم ويندوز لا يدعم تعديل ملف الخدمة بعد. حدّث الخادم إلى النسخة الحالية.")
        conn = self.db.get_connection()
        user = UserSession.get_current() or {}
        row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على ملف الخدمة")
        service = dict(row)
        if service.get("status") == SERVICE_CASE_STATUS_REVERSED:
            raise ValueError("لا يمكن تعديل ملف خدمة معكوس. أنشئ ملف خدمة جديداً بدلاً منه.")
        client_entry = self._client_row(conn, service)
        client_summary = get_payment_summary(conn, client_entry)
        if float(payload.get("sale_amount_original") or 0) + 0.005 < float(client_summary.get("paid_amount_original") or 0):
            raise ValueError("إجمالي البيع الجديد أقل من دفعات المسافر المسجلة")
        if payload.get("currency_original") != client_entry.get("currency_original") and float(client_summary.get("paid_amount_original") or 0) > 0:
            raise ValueError("لا يمكن تغيير عملة ملف خدمة عليه دفعات مسافر")
        supplier_payment_row = conn.execute(
            """SELECT COUNT(*) AS c FROM payments p JOIN expenses e ON e.id=p.target_expense_id
               WHERE e.source_ref=? AND e.source_type=? AND p.status='posted'""",
            (reference, SERVICE_CASE_SOURCE_SUPPLIER),
        ).fetchone()
        if supplier_payment_row and int(supplier_payment_row["c"] or 0) > 0:
            raise ValueError("لا يمكن تعديل بنود الموردين قبل حذف دفعات الموردين المسجلة لهذا الملف")
        before_components = [dict(r) for r in conn.execute("SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index", (reference,)).fetchall()]
        before = {
            "client_company_name": service.get("client_company_name"),
            "supplier_company_name": service.get("supplier_company_name"),
            "person_name": service.get("person_name"),
            "service_type": service.get("service_type"),
            "sale_amount_original": service.get("sale_amount_original"),
            "cost_amount_original": service.get("cost_amount_original"),
            "currency_original": service.get("currency_original"),
            "date": service.get("date"),
            "notes": service.get("notes") or "",
            "components": [
                {
                    "service_type": c.get("service_type"),
                    "supplier_company_name": c.get("supplier_company_name"),
                    "sale_amount_original": c.get("sale_amount_original"),
                    "cost_amount_original": c.get("cost_amount_original"),
                } for c in before_components
            ],
        }
        now = datetime.datetime.now().isoformat()
        supplier_summary = payload.get("supplier_summary") or payload.get("supplier_company_name")
        client_payload, supplier_payloads, sale_base, cost_base, rate, note = self._build_payloads(reference, payload, uid, now, existing_client=client_entry)
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._update_expense(conn, int(client_entry["id"]), client_payload)
            # A correction may change suppliers, remove a component, or add new components.
            # Replace only the generated supplier rows for this service-case reference;
            # keep reversals and unrelated ledger rows untouched.
            conn.execute("DELETE FROM expenses WHERE source_ref=? AND source_type=?", (reference, SERVICE_CASE_SOURCE_SUPPLIER))
            conn.execute("DELETE FROM service_case_components WHERE service_case_ref=?", (reference,))
            supplier_expense_ids: List[int] = []
            first_supplier_expense_id = None
            component_rows = []
            for idx, component in enumerate(payload.get("components") or [], 1):
                supplier_expense_id = None
                supplier_payload_for_component = None
                for item in supplier_payloads:
                    if item["component"] is component:
                        supplier_payload_for_component = item["payload"]
                        supplier_expense_id = self._insert_expense(conn, supplier_payload_for_component)
                        supplier_expense_ids.append(supplier_expense_id)
                        if first_supplier_expense_id is None:
                            first_supplier_expense_id = supplier_expense_id
                        break
                component_rows.append((idx, component, supplier_expense_id, supplier_payload_for_component))
            for idx, component, supplier_expense_id, supplier_payload_for_component in component_rows:
                self._insert_component(conn, reference, idx, component, payload, supplier_expense_id, supplier_payload_for_component)
            sync_payment_state(conn, int(client_entry["id"]), now=now)
            for supplier_expense_id in supplier_expense_ids:
                sync_payment_state(conn, supplier_expense_id, now=now)
            conn.execute(
                """UPDATE service_cases SET
                client_company_name=?, supplier_company_name=?, person_name=?, service_type=?, sale_amount_original=?, cost_amount_original=?,
                currency_original=?, exchange_rate_to_usd=?, sale_amount_base=?, cost_amount_base=?, date=?, notes=?,
                client_expense_id=?, supplier_expense_id=?, print_description_client=?, print_description_supplier=?, internal_note=?, updated_by=?, updated_at=?, edit_reason=?
                WHERE reference=?""",
                (
                    payload["client_company_name"], supplier_summary, payload["person_name"], payload["service_type"], payload["sale_amount_original"], payload["cost_amount_original"],
                    payload["currency_original"], rate, sale_base, cost_base, payload["date"], payload.get("notes", ""),
                    int(client_entry["id"]), first_supplier_expense_id, client_print_description(payload), "تفاصيل حسب بنود الخدمة", note, uid, now, reason, reference,
                ),
            )
            details = (
                f"{reference} | السبب: {reason} | قبل: {before['client_company_name']} / {before['person_name']} / "
                f"بيع {before['sale_amount_original']} {before['currency_original']} / تكلفة {before['cost_amount_original']} / موردون {before['supplier_company_name']} بتاريخ {before['date']} | "
                f"بعد: {payload['client_company_name']} / {payload['person_name']} / بيع {payload['sale_amount_original']} {payload['currency_original']} / تكلفة {payload['cost_amount_original']} / موردون {supplier_summary} بتاريخ {payload['date']}"
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "تعديل ملف خدمة", "service_cases", service.get("id"), details, "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "client_expense_id": int(client_entry["id"]), "supplier_expense_id": first_supplier_expense_id, "supplier_expense_ids": supplier_expense_ids, "profit_base": sale_base - cost_base}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def delete(self, reference: str, reason: str = "", user_id: int | None = None) -> Dict[str, Any]:
        """Delete a complete service case without generating reversal rows."""
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع ملف الخدمة مطلوب")
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب حذف ملف الخدمة مطلوب")
        user = UserSession.get_current() or {}
        uid = int(user_id or user.get("id") or 1)
        if self.data.is_remote():
            client = self.db.get_rest_client()
            if hasattr(client, "delete_service_case"):
                return client.delete_service_case(reference, {"reason": clean_reason})
            raise RuntimeError("خادم ويندوز لا يدعم حذف ملف الخدمة بعد. حدّث الخادم إلى النسخة الحالية.")

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على ملف الخدمة")
            service = dict(row)
            components = [dict(r) for r in conn.execute(
                "SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index",
                (reference,),
            ).fetchall()]
            expense_ids = {
                int(value) for value in (service.get("client_expense_id"), service.get("supplier_expense_id"))
                if value not in (None, "")
            }
            expense_ids.update(
                int(component["supplier_expense_id"])
                for component in components
                if component.get("supplier_expense_id") not in (None, "")
            )
            linked = conn.execute(
                "SELECT id FROM expenses WHERE source_ref=? AND source_type IN (?,?,?)",
                (reference, SERVICE_CASE_SOURCE_CLIENT, SERVICE_CASE_SOURCE_SUPPLIER, SERVICE_CASE_REVERSAL),
            ).fetchall()
            expense_ids.update(int(r["id"]) for r in linked)
            payment_counts = delete_payments_for_targets(conn, expense_ids)
            if expense_ids:
                placeholders = ",".join("?" for _ in expense_ids)
                params = tuple(sorted(expense_ids))
                conn.execute(f"DELETE FROM payment_reminders WHERE expense_id IN ({placeholders})", params)
                conn.execute(f"DELETE FROM expenses WHERE id IN ({placeholders})", params)
            conn.execute("DELETE FROM service_case_components WHERE service_case_ref=?", (reference,))
            conn.execute("DELETE FROM service_cases WHERE reference=?", (reference,))
            now = datetime.datetime.now().isoformat()
            details = (
                f"{reference} | السبب: {clean_reason} | العميل: {service.get('client_company_name')} | "
                f"الموردون/المكونات: {len(components)} | القيود المحذوفة: {len(expense_ids)} | الدفعات المحذوفة: {payment_counts['payments']}"
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (uid, user.get("username", ""), "حذف ملف خدمة", "service_cases", service.get("id"), details, "127.0.0.1", now),
            )
            conn.commit()
            return {"ok": True, "reference": reference, "deleted_expenses": len(expense_ids), "deleted_components": len(components)}
        except Exception:
            conn.rollback()
            raise

    def reverse(self, reference: str, reason: str = "") -> Dict[str, Any]:
        reference = str(reference or "").strip()
        if not reference:
            raise ValueError("مرجع ملف الخدمة مطلوب")
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValueError("سبب عكس ملف الخدمة مطلوب")
        if self.data.is_remote():
            return self.db.get_rest_client().reverse_service_case(reference, {"reason": clean_reason})
        conn = self.db.get_connection()
        try:
            # Lock before the status check so concurrent devices/threads cannot
            # create duplicate reversal groups for the same service reference.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
            if not row:
                raise ValueError("لم يتم العثور على ملف الخدمة")
            row = dict(row)
            if row.get("status") == SERVICE_CASE_STATUS_REVERSED:
                raise ValueError("ملف الخدمة معكوس مسبقاً")
            components = [dict(r) for r in conn.execute("SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index", (reference,)).fetchall()]
            if not components:
                components = [{
                    "service_type": row.get("service_type"),
                    "supplier_company_name": row.get("supplier_company_name"),
                    "cost_amount_original": row.get("cost_amount_original"),
                    "currency_original": row.get("currency_original"),
                    "print_description_supplier": row.get("print_description_supplier"),
                }]
            user = UserSession.get_current() or {}
            uid = user.get("id") or 1
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            now = datetime.datetime.now().isoformat()
            reversal_ref = f"REV-{reference}"
            client_rev = self.ledger.normalize_expense_payload({
                "company_name": row["client_company_name"], "amount": row["sale_amount_original"], "type": "outgoing", "date": date,
                "notes": f"عكس ملف خدمة {reference}. السبب: {clean_reason}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
                "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["supplier_company_name"],
                "person_name": row["person_name"], "service_type": row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
                "is_locked": 1, "print_description": f"عكس {row.get('print_description_client') or row.get('service_type')}", "service_case_role": "client_reversal", "linked_company_name": row["supplier_company_name"], "internal_note": f"عكس ملف خدمة {reference}: {clean_reason}",
            })
            supplier_revs = []
            for comp in components:
                cost = float(comp.get("cost_amount_original") or 0)
                if cost <= 0 or not comp.get("supplier_company_name"):
                    continue
                supplier_revs.append(self.ledger.normalize_expense_payload({
                    "company_name": comp["supplier_company_name"], "amount": cost, "type": "incoming", "date": date,
                    "notes": f"عكس ملف خدمة {reference}. السبب: {clean_reason}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
                    "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["client_company_name"],
                    "person_name": row["person_name"], "service_type": comp.get("service_type") or row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
                    "is_locked": 1, "print_description": f"عكس {comp.get('print_description_supplier') or comp.get('service_type') or row.get('service_type')}", "service_case_role": "supplier_reversal", "linked_company_name": row["client_company_name"], "internal_note": f"عكس ملف خدمة {reference}: {clean_reason}",
                }))
            client_reversal_id = self._insert_expense(conn, client_rev)
            supplier_reversal_ids = [self._insert_expense(conn, payload) for payload in supplier_revs]
            changed = conn.execute(
                "UPDATE service_cases SET status=?, reversed_at=?, reversal_ref=? WHERE reference=? AND status<>?",
                (SERVICE_CASE_STATUS_REVERSED, now, reversal_ref, reference, SERVICE_CASE_STATUS_REVERSED),
            )
            if changed.rowcount != 1:
                raise ValueError("تعذر عكس ملف الخدمة؛ ربما عُكس من جهاز آخر")
            self.db._log_audit_local(
                uid, user.get("username", ""), "عكس ملف خدمة", "service_cases", row.get("id"),
                f"{reference} | السبب: {clean_reason} | قيود العكس: {client_reversal_id}/" + ",".join(str(x) for x in supplier_reversal_ids),
            )
            conn.commit()
            return {
                "ok": True, "reference": reference, "reversal_ref": reversal_ref,
                "client_reversal_expense_id": client_reversal_id,
                "supplier_reversal_expense_ids": supplier_reversal_ids,
            }
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
