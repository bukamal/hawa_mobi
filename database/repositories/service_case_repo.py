# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import json
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
        return cases

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
            "notes": f"عكس ملف خدمة {reference}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
            "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["supplier_company_name"],
            "person_name": row["person_name"], "service_type": row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
            "is_locked": 1, "print_description": f"عكس {row.get('print_description_client') or row.get('service_type')}", "service_case_role": "client_reversal", "linked_company_name": row["supplier_company_name"], "internal_note": f"عكس ملف خدمة {reference}",
        })
        supplier_revs = []
        for comp in components:
            cost = float(comp.get("cost_amount_original") or 0)
            if cost <= 0 or not comp.get("supplier_company_name"):
                continue
            supplier_revs.append(self.ledger.normalize_expense_payload({
                "company_name": comp["supplier_company_name"], "amount": cost, "type": "incoming", "date": date,
                "notes": f"عكس ملف خدمة {reference}", "currency": row["currency_original"], "created_by": uid, "created_at": now, "updated_by": uid, "updated_at": now,
                "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["client_company_name"],
                "person_name": row["person_name"], "service_type": comp.get("service_type") or row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
                "is_locked": 1, "print_description": f"عكس {comp.get('print_description_supplier') or comp.get('service_type') or row.get('service_type')}", "service_case_role": "supplier_reversal", "linked_company_name": row["client_company_name"], "internal_note": f"عكس ملف خدمة {reference}",
            }))
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._insert_expense(conn, client_rev)
            for supplier_rev in supplier_revs:
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
