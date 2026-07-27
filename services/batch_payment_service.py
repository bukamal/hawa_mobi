# -*- coding: utf-8 -*-
"""Batch payments, multi-claim allocations, and excess-credit handling."""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Dict, Iterable, List

from services.ledger_operation_service import normalize_expense_metadata
from services.payment_service import (
    PAYMENT_EPSILON,
    PAYMENT_STATUS_NOT_APPLICABLE,
    PAYMENT_STATUS_UNPAID,
    _money,
    get_payment_summary,
    insert_payment_in_transaction,
    sync_payment_state,
)

BATCH_STATUS_POSTED = "posted"
BATCH_STATUS_DELETED = "deleted"
BATCH_MODE_OLDEST = "oldest"
BATCH_MODE_MANUAL = "manual"
CREDIT_SOURCE_CUSTOMER = "customer_credit"
CREDIT_SOURCE_SUPPLIER = "supplier_advance"


def new_batch_reference() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"BATCH-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def _base_amount(amount: Decimal, currency_code: str, rate: float) -> float:
    return float(amount) if currency_code == "USD" else float(amount) / float(rate or 1.0)


def _target_type(direction: str) -> str:
    if direction == "received":
        return "incoming"
    if direction == "paid":
        return "outgoing"
    raise ValueError("اتجاه الدفعة المجمعة غير صالح")


def _rate_for_currency(conn, currency_code: str) -> float:
    if currency_code == "USD":
        return 1.0
    row = conn.execute(
        "SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?",
        (currency_code,),
    ).fetchone()
    rate = float(row["rate_to_usd"] if row else 0)
    if rate <= 0:
        raise ValueError(f"لا يوجد سعر صرف صالح للعملة {currency_code}")
    return rate


def list_outstanding_claims(
    conn,
    *,
    company_name: str | None = None,
    person_name: str | None = None,
    direction: str | None = None,
    currency_code: str | None = None,
) -> List[Dict[str, Any]]:
    """Return settleable claims with their current remaining balances."""
    clauses = ["e.is_settleable=1", "e.amount_original > 0"]
    params: List[Any] = []
    if company_name:
        clauses.append("e.company_name=?")
        params.append(str(company_name).strip())
    if person_name is not None:
        clauses.append("COALESCE(e.person_name,'')=?")
        params.append(str(person_name).strip())
    if direction:
        clauses.append("e.type=?")
        params.append(_target_type(direction))
    if currency_code:
        clauses.append("e.currency_original=?")
        params.append(str(currency_code).strip().upper())
    rows = conn.execute(
        f"""SELECT e.*,
                   COALESCE((SELECT SUM(p.amount_original) FROM payments p
                             WHERE p.target_expense_id=e.id AND p.status='posted'),0) AS paid_amount_original
            FROM expenses e
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(NULLIF(e.payment_due_date,''), e.date) ASC, e.date ASC, e.id ASC""",
        tuple(params),
    ).fetchall()
    result: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        total = _money(row.get("amount_original") or 0)
        paid = _money(row.get("paid_amount_original") or 0)
        remaining = max(Decimal("0.00"), total - paid)
        if remaining <= PAYMENT_EPSILON:
            continue
        row["paid_amount_original"] = float(paid)
        row["remaining_amount_original"] = float(remaining)
        result.append(row)
    return result


def _insert_new_credit_expense(
    conn,
    batch: Dict[str, Any],
    amount: Decimal,
    *,
    user_id: int,
    now: str,
) -> int:
    """Create a ledger claim representing unapplied customer credit/supplier advance."""
    direction = batch["direction"]
    currency_code = batch["currency_original"]
    rate = float(batch["exchange_rate_to_usd"] or 1.0)
    amount_base = _base_amount(amount, currency_code, rate)
    if direction == "received":
        expense_type = "outgoing"
        source_type = CREDIT_SOURCE_CUSTOMER
        service_type = "رصيد دائن للعميل"
        description = "رصيد دائن غير موزع"
    else:
        expense_type = "incoming"
        source_type = CREDIT_SOURCE_SUPPLIER
        service_type = "دفعة مقدمة للمورد"
        description = "دفعة مقدمة غير موزعة"
    payload = normalize_expense_metadata({
        "company_name": batch["company_name"],
        "amount": amount_base,
        "amount_base": amount_base,
        "type": expense_type,
        "date": batch["date"],
        "notes": f"{description} من الدفعة المجمعة {batch['reference']}",
        "currency": currency_code,
        "amount_original": float(amount),
        "currency_original": currency_code,
        "exchange_rate_to_usd": rate,
        "status": "approved",
        "source_type": source_type,
        "source_ref": batch["reference"],
        "counterparty_company_name": batch["company_name"],
        "person_name": batch.get("person_name"),
        "service_type": service_type,
        "operation_type": source_type,
        "is_locked": 1,
        "print_description": f"{service_type} - {batch['company_name']}",
        "internal_note": f"المبلغ الزائد غير الموزع من {batch['reference']}",
        "service_case_role": "credit",
        "linked_company_name": batch["company_name"],
    })
    cur = conn.execute(
        """INSERT INTO expenses
        (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
         updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
         status, payment_due_date, payment_reminder_note, source_type, source_ref, counterparty_company_name,
         person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by,
         print_description, internal_note, service_case_role, linked_company_name, is_settleable, payment_status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            payload["company_name"], payload["amount"], payload["amount_base"], payload["type"], payload["date"], payload.get("notes", ""), payload["currency"],
            user_id, now, user_id, now, payload["amount_original"], payload["currency_original"], payload["exchange_rate_to_usd"],
            "approved", None, None, source_type, batch["reference"], payload.get("counterparty_company_name"),
            payload.get("person_name"), payload.get("person_name_search"), service_type, source_type, 1, None, None,
            payload.get("print_description"), payload.get("internal_note"), "credit", payload.get("linked_company_name"), 1, PAYMENT_STATUS_UNPAID,
        ),
    )
    return int(cur.lastrowid)


def ensure_batch_credit(
    conn,
    batch: Dict[str, Any],
    amount: Any,
    *,
    user_id: int,
    now: str,
) -> int | None:
    amount_dec = _money(amount)
    if amount_dec <= PAYMENT_EPSILON:
        return int(batch.get("credit_expense_id") or 0) or None
    credit_id = int(batch.get("credit_expense_id") or 0)
    if credit_id:
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (credit_id,)).fetchone()
        if row:
            current = _money(row["amount_original"] or 0)
            new_total = current + amount_dec
            rate = float(row["exchange_rate_to_usd"] or 1.0)
            amount_base = _base_amount(new_total, row["currency_original"], rate)
            conn.execute(
                "UPDATE expenses SET amount_original=?, amount_base=?, amount=?, updated_by=?, updated_at=? WHERE id=?",
                (float(new_total), amount_base, amount_base, user_id, now, credit_id),
            )
            sync_payment_state(conn, credit_id, now=now)
            return credit_id
    return _insert_new_credit_expense(conn, batch, amount_dec, user_id=user_id, now=now)


def create_payment_batch_in_transaction(
    conn,
    *,
    company_name: str,
    person_name: str = "",
    direction: str,
    amount: Any,
    currency_code: str,
    date: str,
    payment_method: str = "cash",
    reference_number: str = "",
    notes: str = "",
    allocation_mode: str = BATCH_MODE_OLDEST,
    allocations: Iterable[Dict[str, Any]] | None = None,
    user_id: int = 1,
    username: str = "",
    reference: str | None = None,
    now: str | None = None,
) -> Dict[str, Any]:
    company_name = str(company_name or "").strip()
    person_name = str(person_name or "").strip()
    currency_code = str(currency_code or "USD").strip().upper()
    direction = str(direction or "").strip()
    if not company_name:
        raise ValueError("اسم الطرف مطلوب")
    _target_type(direction)
    amount_dec = _money(amount)
    if amount_dec <= 0:
        raise ValueError("مبلغ الدفعة المجمعة يجب أن يكون أكبر من صفر")
    allocation_mode = str(allocation_mode or BATCH_MODE_OLDEST)
    if allocation_mode not in {BATCH_MODE_OLDEST, BATCH_MODE_MANUAL}:
        raise ValueError("طريقة توزيع الدفعة غير صالحة")

    now = now or datetime.datetime.now().isoformat()
    date = str(date or now[:10])[:10]
    reference = reference or new_batch_reference()
    rate = _rate_for_currency(conn, currency_code)
    amount_base = _base_amount(amount_dec, currency_code, rate)

    cur = conn.execute(
        """INSERT INTO payment_batches
        (reference, company_name, person_name, direction, amount_original, currency_original,
         exchange_rate_to_usd, amount_base, payment_method, date, reference_number, notes,
         allocation_mode, allocated_amount_original, credit_amount_original, credit_expense_id,
         status, created_by, created_at, updated_by, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            reference, company_name, person_name or None, direction, float(amount_dec), currency_code,
            rate, amount_base, str(payment_method or "cash"), date, str(reference_number or "").strip(),
            str(notes or "").strip(), allocation_mode, 0.0, 0.0, None, BATCH_STATUS_POSTED,
            user_id, now, user_id, now,
        ),
    )
    batch_id = int(cur.lastrowid)

    candidates = list_outstanding_claims(
        conn,
        company_name=company_name,
        person_name=person_name if person_name else None,
        direction=direction,
        currency_code=currency_code,
    )
    by_id = {int(row["id"]): row for row in candidates}
    allocation_plan: List[tuple[Dict[str, Any], Decimal]] = []

    if allocation_mode == BATCH_MODE_MANUAL:
        requested: Dict[int, Decimal] = {}
        for item in allocations or []:
            expense_id = int(item.get("expense_id") or 0)
            allocated = _money(item.get("amount") or 0)
            if allocated <= PAYMENT_EPSILON:
                continue
            requested[expense_id] = requested.get(expense_id, Decimal("0.00")) + allocated
        for expense_id, allocated in requested.items():
            target = by_id.get(expense_id)
            if not target:
                raise ValueError(f"القيد {expense_id} لا يخص الطرف أو العملة المحددين")
            remaining = _money(target["remaining_amount_original"])
            if allocated - remaining > PAYMENT_EPSILON:
                raise ValueError(f"توزيع القيد {expense_id} أكبر من المتبقي")
            allocation_plan.append((target, allocated))
        if sum((value for _, value in allocation_plan), Decimal("0.00")) - amount_dec > PAYMENT_EPSILON:
            raise ValueError("مجموع التوزيع اليدوي أكبر من مبلغ الدفعة")
    else:
        available = amount_dec
        for target in candidates:
            if available <= PAYMENT_EPSILON:
                break
            allocated = min(available, _money(target["remaining_amount_original"]))
            if allocated > PAYMENT_EPSILON:
                allocation_plan.append((target, allocated))
                available -= allocated

    allocated_total = Decimal("0.00")
    allocation_results: List[Dict[str, Any]] = []
    for index, (target, allocated) in enumerate(allocation_plan, start=1):
        payment = insert_payment_in_transaction(
            conn,
            target,
            allocated,
            date=date,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=(f"دفعة مجمعة {reference}. {notes}".strip()),
            user_id=user_id,
            username=username,
            reference=f"{reference}-A{index:03d}",
            now=now,
        )
        conn.execute("UPDATE payments SET batch_id=? WHERE id=?", (batch_id, int(payment["id"])))
        conn.execute(
            "INSERT INTO payment_allocations (batch_id, target_expense_id, payment_id, amount_original, created_at) VALUES (?,?,?,?,?)",
            (batch_id, int(target["id"]), int(payment["id"]), float(allocated), now),
        )
        allocated_total += allocated
        allocation_results.append({
            "expense_id": int(target["id"]),
            "payment_id": int(payment["id"]),
            "amount_original": float(allocated),
            "remaining_amount_original": payment["remaining_amount_original"],
            "source_type": target.get("source_type"),
            "source_ref": target.get("source_ref"),
            "service_type": target.get("service_type"),
            "person_name": target.get("person_name"),
        })

    credit_amount = max(Decimal("0.00"), amount_dec - allocated_total)
    batch_row = dict(conn.execute("SELECT * FROM payment_batches WHERE id=?", (batch_id,)).fetchone())
    credit_expense_id = ensure_batch_credit(conn, batch_row, credit_amount, user_id=user_id, now=now)
    conn.execute(
        "UPDATE payment_batches SET allocated_amount_original=?, credit_amount_original=?, credit_expense_id=?, updated_by=?, updated_at=? WHERE id=?",
        (float(allocated_total), float(credit_amount), credit_expense_id, user_id, now, batch_id),
    )
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (
            user_id, username or "", "تسجيل دفعة مجمعة", "payment_batches", batch_id,
            f"{reference} | {company_name} | {float(amount_dec):.2f} {currency_code} | موزع {float(allocated_total):.2f} | رصيد {float(credit_amount):.2f}",
            "127.0.0.1", now,
        ),
    )
    return {
        "ok": True,
        "id": batch_id,
        "reference": reference,
        "company_name": company_name,
        "person_name": person_name,
        "direction": direction,
        "amount_original": float(amount_dec),
        "currency_original": currency_code,
        "allocated_amount_original": float(allocated_total),
        "credit_amount_original": float(credit_amount),
        "credit_expense_id": credit_expense_id,
        "allocations": allocation_results,
    }


def get_payment_batch(conn, batch_id_or_reference: int | str) -> Dict[str, Any]:
    if isinstance(batch_id_or_reference, int) or str(batch_id_or_reference).isdigit():
        row = conn.execute("SELECT * FROM payment_batches WHERE id=?", (int(batch_id_or_reference),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM payment_batches WHERE reference=?", (str(batch_id_or_reference),)).fetchone()
    if not row:
        raise ValueError("لم يتم العثور على الدفعة المجمعة")
    batch = dict(row)
    allocations = conn.execute(
        """SELECT a.*, p.reference AS payment_reference, e.service_type, e.source_type, e.source_ref,
                  e.person_name, e.payment_due_date, e.date AS claim_date
           FROM payment_allocations a
           JOIN payments p ON p.id=a.payment_id
           JOIN expenses e ON e.id=a.target_expense_id
           WHERE a.batch_id=? ORDER BY a.id""",
        (int(batch["id"]),),
    ).fetchall()
    batch["allocations"] = [dict(item) for item in allocations]
    return batch


def delete_payment_batch_in_transaction(
    conn,
    batch_id: int,
    *,
    reason: str,
    user_id: int,
    username: str = "",
    now: str | None = None,
) -> Dict[str, Any]:
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("سبب حذف الدفعة المجمعة مطلوب")
    batch = get_payment_batch(conn, int(batch_id))
    credit_id = int(batch.get("credit_expense_id") or 0)
    if credit_id:
        used = conn.execute(
            "SELECT COUNT(*) AS c FROM payments WHERE target_expense_id=? AND status='posted'",
            (credit_id,),
        ).fetchone()
        if int(used["c"] if used else 0) > 0:
            raise ValueError("لا يمكن حذف الدفعة لأن الرصيد الدائن استُخدم أو رُدّ جزئياً")
    target_ids: List[int] = []
    for item in batch.get("allocations") or []:
        target_ids.append(int(item["target_expense_id"]))
        payment = conn.execute("SELECT ledger_expense_id FROM payments WHERE id=?", (int(item["payment_id"]),)).fetchone()
        if payment and payment["ledger_expense_id"]:
            conn.execute("DELETE FROM expenses WHERE id=?", (int(payment["ledger_expense_id"]),))
        conn.execute("DELETE FROM payments WHERE id=?", (int(item["payment_id"]),))
    conn.execute("DELETE FROM payment_allocations WHERE batch_id=?", (int(batch_id),))
    if credit_id:
        conn.execute("DELETE FROM payment_reminders WHERE expense_id=?", (credit_id,))
        conn.execute("DELETE FROM expenses WHERE id=?", (credit_id,))
    conn.execute("DELETE FROM payment_batches WHERE id=?", (int(batch_id),))
    now = now or datetime.datetime.now().isoformat()
    for target_id in sorted(set(target_ids)):
        if conn.execute("SELECT id FROM expenses WHERE id=?", (target_id,)).fetchone():
            sync_payment_state(conn, target_id, now=now)
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, username or "", "حذف دفعة مجمعة", "payment_batches", int(batch_id), f"{batch['reference']} | السبب: {reason}", "127.0.0.1", now),
    )
    return {"ok": True, "reference": batch["reference"], "targets_updated": len(set(target_ids))}


def reclassify_allocations_as_credit(
    conn,
    target_expense_ids: Iterable[int],
    *,
    user_id: int = 1,
    now: str | None = None,
) -> Dict[str, Any]:
    """Move deleted-claim allocations back to their batch's unapplied credit."""
    ids = sorted({int(value) for value in target_expense_ids if value not in (None, "")})
    if not ids:
        return {"payment_ids": [], "ledger_ids": [], "reclassified_amount": 0.0}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""SELECT a.id AS allocation_id, a.batch_id, a.payment_id, a.amount_original,
                   p.ledger_expense_id
            FROM payment_allocations a
            JOIN payments p ON p.id=a.payment_id
            WHERE a.target_expense_id IN ({placeholders})""",
        tuple(ids),
    ).fetchall()
    if not rows:
        return {"payment_ids": [], "ledger_ids": [], "reclassified_amount": 0.0}
    now = now or datetime.datetime.now().isoformat()
    by_batch: Dict[int, Decimal] = {}
    payment_ids: List[int] = []
    ledger_ids: List[int] = []
    allocation_ids: List[int] = []
    for raw in rows:
        row = dict(raw)
        batch_id = int(row["batch_id"])
        by_batch[batch_id] = by_batch.get(batch_id, Decimal("0.00")) + _money(row["amount_original"])
        payment_ids.append(int(row["payment_id"]))
        allocation_ids.append(int(row["allocation_id"]))
        if row.get("ledger_expense_id"):
            ledger_ids.append(int(row["ledger_expense_id"]))
    if ledger_ids:
        q = ",".join("?" for _ in ledger_ids)
        conn.execute(f"DELETE FROM payment_reminders WHERE expense_id IN ({q})", tuple(ledger_ids))
        conn.execute(f"DELETE FROM expenses WHERE id IN ({q})", tuple(ledger_ids))
    if allocation_ids:
        q = ",".join("?" for _ in allocation_ids)
        conn.execute(f"DELETE FROM payment_allocations WHERE id IN ({q})", tuple(allocation_ids))
    if payment_ids:
        q = ",".join("?" for _ in payment_ids)
        conn.execute(f"DELETE FROM payments WHERE id IN ({q})", tuple(payment_ids))
    total = Decimal("0.00")
    for batch_id, removed in by_batch.items():
        batch_row = conn.execute("SELECT * FROM payment_batches WHERE id=?", (batch_id,)).fetchone()
        if not batch_row:
            continue
        batch = dict(batch_row)
        credit_id = ensure_batch_credit(conn, batch, removed, user_id=user_id, now=now)
        new_allocated = max(Decimal("0.00"), _money(batch["allocated_amount_original"]) - removed)
        new_credit = _money(batch["credit_amount_original"]) + removed
        conn.execute(
            "UPDATE payment_batches SET allocated_amount_original=?, credit_amount_original=?, credit_expense_id=?, updated_by=?, updated_at=? WHERE id=?",
            (float(new_allocated), float(new_credit), credit_id, user_id, now, batch_id),
        )
        total += removed
    return {
        "payment_ids": payment_ids,
        "ledger_ids": ledger_ids,
        "reclassified_amount": float(total),
    }
