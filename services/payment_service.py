# -*- coding: utf-8 -*-
"""Partial-payment accounting primitives.

A receivable/payable expense is the immutable claim total.  Payments are stored
separately and create opposite ledger rows so company balances decrease without
mutating or replacing the original claim.
"""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List

from services.ledger_operation_service import normalize_expense_metadata

PAYMENT_SOURCE_RECEIVED = "payment_received"
PAYMENT_SOURCE_PAID = "payment_paid"
PAYMENT_STATUS_UNPAID = "unpaid"
PAYMENT_STATUS_PARTIAL = "partial"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_NOT_APPLICABLE = "not_applicable"
PAYMENT_EPSILON = Decimal("0.005")


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("مبلغ الدفعة غير صالح")


def new_payment_reference() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"PAY-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def payment_status_label(status: str) -> str:
    return {
        PAYMENT_STATUS_UNPAID: "غير مدفوع",
        PAYMENT_STATUS_PARTIAL: "مدفوع جزئياً",
        PAYMENT_STATUS_PAID: "مدفوع بالكامل",
        PAYMENT_STATUS_NOT_APPLICABLE: "غير قابل للسداد",
    }.get(str(status or ""), "غير مدفوع")


def _paid_amount(conn, expense_id: int) -> Decimal:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_original), 0) AS paid FROM payments WHERE target_expense_id=? AND status='posted'",
        (int(expense_id),),
    ).fetchone()
    return _money(row["paid"] if row else 0)


def get_payment_summary(conn, expense_or_id: int | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(expense_or_id, dict):
        target = dict(expense_or_id)
    else:
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (int(expense_or_id),)).fetchone()
        if not row:
            raise ValueError("لم يتم العثور على القيد المرتبط بالدفع")
        target = dict(row)
    total = _money(target.get("amount_original") or 0)
    settleable = int(target.get("is_settleable", 1) or 0) == 1 and total > 0
    paid = _paid_amount(conn, int(target["id"])) if settleable else Decimal("0.00")
    remaining = total - paid
    overpayment = max(Decimal("0.00"), -remaining)
    remaining = max(Decimal("0.00"), remaining)
    if not settleable:
        status = PAYMENT_STATUS_NOT_APPLICABLE
    elif paid <= PAYMENT_EPSILON:
        status = PAYMENT_STATUS_UNPAID
    elif remaining <= PAYMENT_EPSILON:
        status = PAYMENT_STATUS_PAID
    else:
        status = PAYMENT_STATUS_PARTIAL
    return {
        "expense_id": int(target["id"]),
        "is_settleable": settleable,
        "total_amount_original": float(total),
        "paid_amount_original": float(paid),
        "remaining_amount_original": float(remaining),
        "overpayment_amount_original": float(overpayment),
        "payment_status": status,
        "payment_status_label": payment_status_label(status),
        "currency_original": target.get("currency_original") or target.get("currency") or "USD",
    }


def sync_payment_state(conn, expense_id: int, *, now: str | None = None) -> Dict[str, Any]:
    now = now or datetime.datetime.now().isoformat()
    summary = get_payment_summary(conn, int(expense_id))
    conn.execute(
        "UPDATE expenses SET payment_status=?, updated_at=COALESCE(updated_at, ?) WHERE id=?",
        (summary["payment_status"], now, int(expense_id)),
    )
    target = conn.execute(
        "SELECT payment_due_date, payment_reminder_note FROM expenses WHERE id=?",
        (int(expense_id),),
    ).fetchone()
    if not target:
        return summary
    if summary["payment_status"] in (PAYMENT_STATUS_PAID, PAYMENT_STATUS_NOT_APPLICABLE):
        conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (int(expense_id),))
    elif target["payment_due_date"]:
        existing = conn.execute(
            "SELECT id FROM payment_reminders WHERE expense_id=? AND is_done=0 ORDER BY id DESC LIMIT 1",
            (int(expense_id),),
        ).fetchone()
        reminder_date = str(target["payment_due_date"])[:10]
        reminder_note = target["payment_reminder_note"] or "تذكير بمتابعة المبلغ المتبقي"
        if existing:
            conn.execute(
                "UPDATE payment_reminders SET reminder_date=?, note=?, is_done=0 WHERE id=?",
                (reminder_date, reminder_note, int(existing["id"])),
            )
        else:
            conn.execute(
                "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                (int(expense_id), reminder_date, reminder_note, 0, now),
            )
    else:
        conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (int(expense_id),))
    return summary


def enrich_expenses_with_payments(conn, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = [dict(row) for row in rows]
    ids = [int(row["id"]) for row in result if row.get("id") is not None]
    paid_by_id: Dict[int, float] = {}
    if ids:
        placeholders = ",".join("?" for _ in ids)
        paid_rows = conn.execute(
            f"SELECT target_expense_id, COALESCE(SUM(amount_original),0) AS paid FROM payments WHERE status='posted' AND target_expense_id IN ({placeholders}) GROUP BY target_expense_id",
            tuple(ids),
        ).fetchall()
        paid_by_id = {int(row["target_expense_id"]): float(row["paid"] or 0) for row in paid_rows}
    for row in result:
        total = _money(row.get("amount_original") or 0)
        settleable = int(row.get("is_settleable", 1) or 0) == 1 and total > 0
        paid = _money(paid_by_id.get(int(row.get("id") or 0), 0)) if settleable else Decimal("0.00")
        remaining = max(Decimal("0.00"), total - paid)
        if not settleable:
            status = PAYMENT_STATUS_NOT_APPLICABLE
        elif paid <= PAYMENT_EPSILON:
            status = PAYMENT_STATUS_UNPAID
        elif remaining <= PAYMENT_EPSILON:
            status = PAYMENT_STATUS_PAID
        else:
            status = PAYMENT_STATUS_PARTIAL
        row.update({
            "is_settleable": int(settleable),
            "paid_amount_original": float(paid),
            "remaining_amount_original": float(remaining),
            "overpayment_amount_original": float(max(Decimal("0.00"), paid - total)),
            "payment_status": status,
            "payment_status_label": payment_status_label(status),
        })
    return result


def insert_payment_in_transaction(
    conn,
    target: Dict[str, Any],
    amount: Any,
    *,
    date: str,
    payment_method: str = "cash",
    reference_number: str = "",
    notes: str = "",
    user_id: int = 1,
    username: str = "",
    reference: str | None = None,
    now: str | None = None,
) -> Dict[str, Any]:
    """Insert a payment and its opposite ledger row using an existing transaction."""
    target = dict(target or {})
    if not target.get("id"):
        raise ValueError("القيد المستهدف للدفع غير موجود")
    summary_before = get_payment_summary(conn, target)
    if not summary_before["is_settleable"]:
        raise ValueError("هذا القيد غير قابل لتسجيل دفعات")
    amount_dec = _money(amount)
    if amount_dec <= 0:
        raise ValueError("مبلغ الدفعة يجب أن يكون أكبر من صفر")
    remaining = _money(summary_before["remaining_amount_original"])
    if amount_dec - remaining > PAYMENT_EPSILON:
        raise ValueError(f"الدفعة أكبر من المتبقي ({float(remaining):.2f} {summary_before['currency_original']})")
    if str(target.get("source_type") or "") in {PAYMENT_SOURCE_RECEIVED, PAYMENT_SOURCE_PAID}:
        raise ValueError("لا يمكن تسجيل دفعة على حركة دفع")

    now = now or datetime.datetime.now().isoformat()
    date = str(date or datetime.datetime.now().strftime("%Y-%m-%d"))[:10]
    reference = reference or new_payment_reference()
    currency_code = target.get("currency_original") or target.get("currency") or "USD"
    rate = float(target.get("exchange_rate_to_usd") or 1.0)
    amount_base = float(amount_dec) if currency_code == "USD" else float(amount_dec) / rate
    direction = "received" if target.get("type") == "incoming" else "paid"
    settlement_type = "outgoing" if direction == "received" else "incoming"
    source_type = PAYMENT_SOURCE_RECEIVED if direction == "received" else PAYMENT_SOURCE_PAID
    action_label = "دفعة مستلمة" if direction == "received" else "دفعة مدفوعة"
    print_description = f"{action_label} - {target.get('person_name') or target.get('company_name') or ''}".strip(" -")
    settlement_notes = f"{action_label} للقيد #{target['id']}"
    if target.get("source_ref"):
        settlement_notes += f" / {target.get('source_ref')}"
    if notes:
        settlement_notes += f". {notes}"
    payload = normalize_expense_metadata({
        "company_name": target.get("company_name"),
        "amount": amount_base,
        "amount_base": amount_base,
        "type": settlement_type,
        "date": date,
        "notes": settlement_notes,
        "currency": currency_code,
        "created_by": user_id,
        "created_at": now,
        "updated_by": user_id,
        "updated_at": now,
        "amount_original": float(amount_dec),
        "currency_original": currency_code,
        "exchange_rate_to_usd": rate,
        "status": "approved",
        "source_type": source_type,
        "source_ref": reference,
        "counterparty_company_name": target.get("company_name"),
        "person_name": target.get("person_name"),
        "service_type": target.get("service_type") or "دفعة",
        "operation_type": source_type,
        "is_locked": 1,
        "print_description": print_description,
        "internal_note": f"تسوية جزئية للقيد {target['id']} / {target.get('source_ref') or '-'}",
        "service_case_role": "payment",
        "linked_company_name": target.get("linked_company_name") or target.get("company_name"),
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
            "approved", None, None, source_type, reference, payload.get("counterparty_company_name"),
            payload.get("person_name"), payload.get("person_name_search"), payload.get("service_type"), payload.get("operation_type"), 1, None, None,
            payload.get("print_description"), payload.get("internal_note"), "payment", payload.get("linked_company_name"), 0, PAYMENT_STATUS_NOT_APPLICABLE,
        ),
    )
    ledger_expense_id = int(cur.lastrowid)
    cur = conn.execute(
        """INSERT INTO payments
        (reference, target_expense_id, company_name, person_name, source_type, source_ref, party_role,
         amount_original, currency_original, exchange_rate_to_usd, amount_base, direction, payment_method,
         date, reference_number, notes, ledger_expense_id, status, created_by, created_at, updated_by, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            reference, int(target["id"]), target.get("company_name"), target.get("person_name"), target.get("source_type"), target.get("source_ref"), target.get("service_case_role") or "normal",
            float(amount_dec), currency_code, rate, amount_base, direction, str(payment_method or "cash"), date,
            str(reference_number or "").strip(), str(notes or "").strip(), ledger_expense_id, "posted", user_id, now, user_id, now,
        ),
    )
    payment_id = int(cur.lastrowid)
    summary_after = sync_payment_state(conn, int(target["id"]), now=now)
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (
            user_id, username or "", action_label, "payments", payment_id,
            f"{reference} | القيد {target['id']} | {float(amount_dec):.2f} {currency_code} | المتبقي {summary_after['remaining_amount_original']:.2f}",
            "127.0.0.1", now,
        ),
    )
    return {
        "ok": True,
        "id": payment_id,
        "reference": reference,
        "ledger_expense_id": ledger_expense_id,
        **summary_after,
    }


def delete_payments_for_targets(conn, target_expense_ids: Iterable[int]) -> Dict[str, int]:
    ids = sorted({int(value) for value in target_expense_ids if value not in (None, "")})
    if not ids:
        return {"payments": 0, "ledger_expenses": 0}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, ledger_expense_id FROM payments WHERE target_expense_id IN ({placeholders})",
        tuple(ids),
    ).fetchall()
    ledger_ids = sorted({int(row["ledger_expense_id"]) for row in rows if row["ledger_expense_id"] not in (None, "")})
    if ledger_ids:
        ledger_placeholders = ",".join("?" for _ in ledger_ids)
        conn.execute(f"DELETE FROM payment_reminders WHERE expense_id IN ({ledger_placeholders})", tuple(ledger_ids))
        conn.execute(f"DELETE FROM expenses WHERE id IN ({ledger_placeholders})", tuple(ledger_ids))
    conn.execute(f"DELETE FROM payments WHERE target_expense_id IN ({placeholders})", tuple(ids))
    return {"payments": len(rows), "ledger_expenses": len(ledger_ids)}
