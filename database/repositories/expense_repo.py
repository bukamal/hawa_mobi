from database.repositories.base_repo import BaseRepository
from auth.session import UserSession
import datetime
from typing import List, Dict, Optional
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import (
    normalize_expense_metadata,
    is_generated_source,
)


class ExpenseRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _base_amount(self, row: Dict) -> float:
        return float(row.get("amount_base", row.get("amount", 0)) or 0)

    def get_all(self, convert_to_display: bool = True) -> List[Dict]:
        expenses = self.data.get_expenses()
        if convert_to_display:
            for e in expenses:
                e["amount_display"] = e.get("amount_original", e["amount"])
                e["currency_display"] = e.get(
                    "currency_original", e.get("currency", "SAR")
                )
        return expenses

    def get_by_company(
        self, company_name: str, convert_to_display: bool = True
    ) -> List[Dict]:
        all_exp = self.get_all(convert_to_display=False)
        filtered = [e for e in all_exp if e["company_name"] == company_name]
        if convert_to_display:
            for e in filtered:
                e["amount_display"] = e.get("amount_original", e["amount"])
                e["currency_display"] = e.get(
                    "currency_original", e.get("currency", "SAR")
                )
        return filtered

    def search_company_ledger(self, query: str, limit: int = 100) -> List[Dict]:
        query = (query or "").strip()
        if not query:
            return []
        if hasattr(self.data, "search_company_ledger"):
            return self.data.search_company_ledger(query, limit=limit)
        from services.company_search_service import search_expense_rows

        return search_expense_rows(
            self.get_all(convert_to_display=False), query, limit=limit
        )

    def add(
        self,
        company_name: str,
        amount: float,
        type_val: str,
        date: str,
        notes: str,
        currency_code: str,
        user_id: int,
        payment_due_date: Optional[str] = None,
        payment_note: Optional[str] = None,
        person_name: str = "",
        service_type: str = "غير محدد",
        operation_type: str = "normal",
    ) -> int:
        amount = float(amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        now = datetime.datetime.now().isoformat()
        data = {
            "company_name": company_name,
            "amount": amount,
            "type": type_val,
            "date": date,
            "notes": notes,
            "currency": currency_code,
            "created_by": user_id,
            "created_at": now,
            "updated_by": user_id,
            "updated_at": now,
            "payment_due_date": payment_due_date,
            "payment_reminder_note": payment_note,
            "person_name": person_name,
            "service_type": service_type,
            "operation_type": operation_type,
        }
        data = normalize_expense_metadata(self.ledger.normalize_expense_payload(data))
        status = data["status"]
        if self.data.is_remote():
            return self.data.add_expense(data)
        else:
            user = UserSession.get_current()
            audit = {
                "user_id": user_id,
                "username": user["username"] if user else "",
                "action": "إضافة قيد",
                "table_name": "expenses",
                "record_id": None,
                "details": f"الشركة: {company_name}, المبلغ: {amount} {currency_code}",
            }
            conn = self.db.get_connection()
            cur = conn.execute(
                """INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status, payment_due_date, payment_reminder_note, person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by, print_description, internal_note, service_case_role, linked_company_name)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    data["company_name"],
                    data["amount"],
                    data["amount_base"],
                    data["type"],
                    data["date"],
                    data["notes"],
                    data["currency"],
                    data["created_by"],
                    data["created_at"],
                    data["updated_by"],
                    data["updated_at"],
                    data["amount_original"],
                    data["currency_original"],
                    data["exchange_rate_to_usd"],
                    data["status"],
                    data["payment_due_date"],
                    data["payment_reminder_note"],
                    data.get("person_name"),
                    data.get("person_name_search"),
                    data.get("service_type"),
                    data.get("operation_type"),
                    data.get("is_locked", 0),
                    data.get("reversal_of"),
                    data.get("reversed_by"),
                    data.get("print_description"),
                    data.get("internal_note"),
                    data.get("service_case_role"),
                    data.get("linked_company_name"),
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
            if status == "waiting_payment" and payment_due_date:
                conn.execute(
                    "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                    (
                        new_id,
                        payment_due_date,
                        payment_note or "بانتظار إدخال الدفعة الأولى",
                        0,
                        now,
                    ),
                )
                conn.commit()
            audit["record_id"] = new_id
            self.db._log_audit_local(
                audit["user_id"],
                audit["username"],
                audit["action"],
                audit["table_name"],
                audit["record_id"],
                audit["details"],
            )
            return new_id

    def update(
        self,
        expense_id: int,
        company_name: str,
        amount: float,
        type_val: str,
        date: str,
        notes: str,
        currency_code: str,
        user_id: int,
        payment_due_date: Optional[str] = None,
        payment_note: Optional[str] = None,
        person_name: str = "",
        service_type: str = "غير محدد",
        operation_type: str = "normal",
    ):
        if expense_id is None:
            raise ValueError("لا يمكن تعديل قيد دون معرّف id")
        expense_id = int(expense_id)
        amount = float(amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        now = datetime.datetime.now().isoformat()
        existing = None
        if not self.data.is_remote():
            existing = (
                self.db.get_connection()
                .execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
                .fetchone()
            )
            existing = dict(existing) if existing else None
            if existing and (
                is_generated_source(existing.get("source_type"))
                or int(existing.get("is_locked") or 0)
            ):
                raise ValueError(
                    "هذا القيد مرتبط بعملية مولّدة ولا يُعدّل منفرداً. استخدم عكس العملية عند الحاجة."
                )
        data = {
            "company_name": company_name,
            "amount": amount,
            "type": type_val,
            "date": date,
            "notes": notes,
            "currency": currency_code,
            "updated_by": user_id,
            "updated_at": now,
            "payment_due_date": payment_due_date,
            "payment_reminder_note": payment_note,
            "person_name": person_name,
            "service_type": service_type,
            "operation_type": operation_type,
            "is_locked": existing.get("is_locked", 0) if existing else 0,
            "source_type": existing.get("source_type") if existing else None,
            "source_ref": existing.get("source_ref") if existing else None,
            "reversal_of": existing.get("reversal_of") if existing else None,
            "reversed_by": existing.get("reversed_by") if existing else None,
            "print_description": existing.get("print_description")
            if existing
            else None,
            "internal_note": existing.get("internal_note") if existing else None,
            "service_case_role": existing.get("service_case_role")
            if existing
            else None,
            "linked_company_name": existing.get("linked_company_name")
            if existing
            else None,
        }
        data = normalize_expense_metadata(
            self.ledger.normalize_expense_payload(data, existing=existing)
        )
        status = data["status"]
        if self.data.is_remote():
            self.data.update_expense(expense_id, data)
        else:
            user = UserSession.get_current()
            audit = {
                "user_id": user_id,
                "username": user["username"] if user else "",
                "action": "تعديل قيد",
                "table_name": "expenses",
                "record_id": expense_id,
                "details": f"الشركة: {company_name}, المبلغ: {amount} {currency_code}",
            }
            conn = self.db.get_connection()
            cur = conn.execute(
                """UPDATE expenses SET company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?, person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?, print_description=?, internal_note=?, service_case_role=?, linked_company_name=? WHERE id=?""",
                (
                    data["company_name"],
                    data["amount"],
                    data["amount_base"],
                    data["type"],
                    data["date"],
                    data["notes"],
                    data["currency"],
                    data["updated_by"],
                    data["updated_at"],
                    data["amount_original"],
                    data["currency_original"],
                    data["exchange_rate_to_usd"],
                    data["status"],
                    data["payment_due_date"],
                    data["payment_reminder_note"],
                    data.get("person_name"),
                    data.get("person_name_search"),
                    data.get("service_type"),
                    data.get("operation_type"),
                    data.get("is_locked", 0),
                    data.get("reversal_of"),
                    data.get("reversed_by"),
                    data.get("print_description"),
                    data.get("internal_note"),
                    data.get("service_case_role"),
                    data.get("linked_company_name"),
                    expense_id,
                ),
            )
            if cur.rowcount != 1:
                conn.rollback()
                raise ValueError(
                    f"لم يتم العثور على القيد المطلوب تعديله id={expense_id}"
                )
            if status == "waiting_payment" and payment_due_date:
                conn.execute(
                    "DELETE FROM payment_reminders WHERE expense_id=? AND is_done=0",
                    (expense_id,),
                )
                conn.execute(
                    "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                    (
                        expense_id,
                        payment_due_date,
                        payment_note or "بانتظار إدخال الدفعة الأولى",
                        0,
                        now,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0",
                    (expense_id,),
                )
            conn.commit()
            self.db._log_audit_local(
                audit["user_id"],
                audit["username"],
                audit["action"],
                audit["table_name"],
                audit["record_id"],
                audit["details"],
            )

    def delete(self, expense_id: int, user_id: int = None):
        if expense_id is None:
            raise ValueError("لا يمكن حذف قيد دون معرّف id")
        expense_id = int(expense_id)
        if user_id is None:
            u = UserSession.get_current()
            user_id = u["id"] if u else None
        if self.data.is_remote():
            self.data.delete_expense(expense_id)
        else:
            conn = self.db.get_connection()
            row = conn.execute(
                "SELECT company_name, amount_original, currency_original, source_type, source_ref, is_locked, operation_type FROM expenses WHERE id=?",
                (expense_id,),
            ).fetchone()
            if row and (
                is_generated_source(row["source_type"]) or int(row["is_locked"] or 0)
            ):
                raise ValueError(
                    "هذا القيد مرتبط بعملية محاسبية ولا يُحذف منفرداً. استخدم عكس العملية بدلاً من الحذف."
                )
            details = (
                f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}"
                if row
                else ""
            )
            cur = conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
            if cur.rowcount != 1:
                conn.rollback()
                raise ValueError(
                    f"لم يتم العثور على القيد المطلوب حذفه id={expense_id}"
                )
            conn.execute(
                "DELETE FROM payment_reminders WHERE expense_id=?", (expense_id,)
            )
            conn.commit()
            u = UserSession.get_current()
            self.db._log_audit_local(
                user_id,
                u["username"] if u else "",
                "حذف قيد",
                "expenses",
                expense_id,
                details,
            )

    def get_pending_payment_reminders(self) -> List[Dict]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_pending_payment_reminders()
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT r.*, e.company_name, e.amount_original, e.currency_original, e.type
            FROM payment_reminders r
            JOIN expenses e ON e.id = r.expense_id
            WHERE r.is_done = 0
            ORDER BY r.reminder_date ASC, r.id DESC
        """).fetchall()
        return [dict(row) for row in rows]

    def count_waiting_payment(self) -> int:
        if self.data.is_remote():
            return self.db.get_rest_client().count_waiting_payment()
        row = (
            self.db.get_connection()
            .execute(
                "SELECT COUNT(*) AS c FROM expenses WHERE status='waiting_payment'"
            )
            .fetchone()
        )
        return int(row["c"] if row else 0)

    def summarize_persons_by_company(self, company_name: str) -> List[Dict]:
        rows = self.get_by_company(company_name, convert_to_display=False)
        buckets = {}
        for row in rows:
            person = (row.get("person_name") or "").strip()
            if not person:
                continue
            item = buckets.setdefault(
                person,
                {
                    "person_name": person,
                    "incoming": 0.0,
                    "outgoing": 0.0,
                    "count": 0,
                    "last_date": "",
                },
            )
            item["count"] += 1
            if row.get("status") != "waiting_payment":
                amount = float(row.get("amount_base", row.get("amount", 0)) or 0)
                if row.get("type") == "incoming":
                    item["incoming"] += amount
                else:
                    item["outgoing"] += amount
            date = str(row.get("date") or "")
            if date > item["last_date"]:
                item["last_date"] = date
        return sorted(
            buckets.values(),
            key=lambda x: (x["last_date"], x["person_name"]),
            reverse=True,
        )

    def get_summary(self, convert_to_display: bool = True) -> Dict:
        expenses = self.get_all(convert_to_display=False)
        approved = [
            e for e in expenses if e.get("status", "approved") != "waiting_payment"
        ]
        total_in = sum(
            self._base_amount(e) for e in approved if e["type"] == "incoming"
        )
        total_out = sum(
            self._base_amount(e) for e in approved if e["type"] == "outgoing"
        )
        companies_count = len(set(e["company_name"] for e in expenses))
        return {
            "total_incoming": total_in,
            "total_outgoing": total_out,
            "net": total_in - total_out,
            "companies_count": companies_count,
        }
