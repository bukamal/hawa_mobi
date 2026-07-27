from database.repositories.base_repo import BaseRepository
from auth.session import UserSession
import datetime
from typing import List, Dict, Optional
from services.currency_ledger_service import CurrencyLedgerService
from services.ledger_operation_service import (
    filter_operational_expenses,
    normalize_expense_metadata,
    is_generated_source,
)
from services.payment_service import (
    delete_payments_for_targets,
    enrich_expenses_with_payments,
    get_payment_summary,
    insert_payment_in_transaction,
    sync_payment_state,
)


class ExpenseRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _base_amount(self, row: Dict) -> float:
        return float(row.get('amount_base', row.get('amount', 0)) or 0)

    def get_all(self, convert_to_display: bool = True, include_reversed: bool = False) -> List[Dict]:
        raw = self.data.get_expenses()
        if not self.data.is_remote():
            raw = enrich_expenses_with_payments(self.db.get_connection(), raw)
        else:
            for row in raw:
                total = float(row.get('amount_original') or 0)
                paid = float(row.get('paid_amount_original') or 0)
                row.setdefault('remaining_amount_original', max(total - paid, 0.0))
                row.setdefault('payment_status', 'paid' if total > 0 and paid >= total else ('partial' if paid > 0 else 'unpaid'))
                row.setdefault('is_settleable', 1 if total > 0 else 0)
        expenses = filter_operational_expenses(raw, include_reversed=include_reversed)
        if convert_to_display:
            for e in expenses:
                e['amount_display'] = e.get('amount_original', e['amount'])
                e['currency_display'] = e.get('currency_original', e.get('currency', 'SAR'))
        return expenses

    def get_by_company(self, company_name: str, convert_to_display: bool = True, include_reversed: bool = False) -> List[Dict]:
        all_exp = self.get_all(convert_to_display=False, include_reversed=include_reversed)
        filtered = [e for e in all_exp if e['company_name'] == company_name]
        if convert_to_display:
            for e in filtered:
                e['amount_display'] = e.get('amount_original', e['amount'])
                e['currency_display'] = e.get('currency_original', e.get('currency', 'SAR'))
        return filtered

    def search_company_ledger(self, query: str, limit: int = 100, include_reversed: bool = False) -> List[Dict]:
        query = (query or '').strip()
        if not query:
            return []
        if hasattr(self.data, 'search_company_ledger'):
            rows = self.data.search_company_ledger(query, limit=max(int(limit or 100) * 4, int(limit or 100)))
            if not self.data.is_remote():
                rows = enrich_expenses_with_payments(self.db.get_connection(), rows)
            return filter_operational_expenses(rows, include_reversed=include_reversed)[:int(limit or 100)]
        from services.company_search_service import search_expense_rows
        return search_expense_rows(self.get_all(convert_to_display=False, include_reversed=include_reversed), query, limit=limit)

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
        person_name: str = '',
        service_type: str = 'غير محدد',
        operation_type: str = 'normal',
        initial_paid_amount: float = 0,
        payment_method: str = 'cash',
        payment_reference_number: str = '',
        is_settleable: bool = True,
    ) -> int:
        amount = float(amount or 0)
        initial_paid_amount = float(initial_paid_amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        if initial_paid_amount < 0 or initial_paid_amount > amount:
            raise ValueError("المبلغ المدفوع الآن يجب أن يكون بين صفر والإجمالي")
        now = datetime.datetime.now().isoformat()
        data = {
            'company_name': company_name, 'amount': amount, 'type': type_val, 'date': date, 'notes': notes,
            'currency': currency_code, 'created_by': user_id, 'created_at': now, 'updated_by': user_id, 'updated_at': now,
            'payment_due_date': payment_due_date, 'payment_reminder_note': payment_note,
            'person_name': person_name, 'service_type': service_type, 'operation_type': operation_type,
            'is_settleable': 1 if is_settleable and amount > 0 else 0,
        }
        data = normalize_expense_metadata(self.ledger.normalize_expense_payload(data))
        if self.data.is_remote():
            data.update({
                'initial_paid_amount': initial_paid_amount,
                'payment_method': payment_method,
                'payment_reference_number': payment_reference_number,
                'is_settleable': data['is_settleable'],
            })
            return self.data.add_expense(data)

        user = UserSession.get_current() or {}
        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                '''INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status, payment_due_date, payment_reminder_note, person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by, print_description, internal_note, service_case_role, linked_company_name, is_settleable, payment_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    data['company_name'], data['amount'], data['amount_base'], data['type'], data['date'], data['notes'], data['currency'],
                    data['created_by'], data['created_at'], data['updated_by'], data['updated_at'], data['amount_original'], data['currency_original'],
                    data['exchange_rate_to_usd'], data['status'], data['payment_due_date'], data['payment_reminder_note'], data.get('person_name'),
                    data.get('person_name_search'), data.get('service_type'), data.get('operation_type'), data.get('is_locked', 0), data.get('reversal_of'),
                    data.get('reversed_by'), data.get('print_description'), data.get('internal_note'), data.get('service_case_role'), data.get('linked_company_name'),
                    data['is_settleable'], 'unpaid' if data['is_settleable'] else 'not_applicable',
                ),
            )
            new_id = int(cur.lastrowid)
            target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (new_id,)).fetchone())
            if initial_paid_amount > 0:
                insert_payment_in_transaction(
                    conn, target, initial_paid_amount, date=date, payment_method=payment_method,
                    reference_number=payment_reference_number, notes="دفعة أولى عند إنشاء القيد",
                    user_id=int(user_id or user.get('id') or 1), username=user.get('username', ''), now=now,
                )
            else:
                sync_payment_state(conn, new_id, now=now)
            if amount <= 0.005 and payment_due_date:
                conn.execute("UPDATE expenses SET status='waiting_payment', payment_status='not_applicable' WHERE id=?", (new_id,))
                conn.execute(
                    "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                    (new_id, str(payment_due_date)[:10], payment_note or "بانتظار تحديد المبلغ / الدفع", 0, now),
                )
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, user.get('username', ''), "إضافة قيد", 'expenses', new_id, f"الشركة: {company_name}, الإجمالي: {amount} {currency_code}, المدفوع: {initial_paid_amount}", '127.0.0.1', now),
            )
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise

    def update(self, expense_id: int, company_name: str, amount: float, type_val: str, date: str, notes: str, currency_code: str, user_id: int, payment_due_date: Optional[str] = None, payment_note: Optional[str] = None, person_name: str = '', service_type: str = 'غير محدد', operation_type: str = 'normal'):
        if expense_id is None:
            raise ValueError("لا يمكن تعديل قيد دون معرّف id")
        expense_id = int(expense_id)
        amount = float(amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        now = datetime.datetime.now().isoformat()
        existing = None
        if not self.data.is_remote():
            existing_row = self.db.get_connection().execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
            existing = dict(existing_row) if existing_row else None
            if existing and (is_generated_source(existing.get('source_type')) or int(existing.get('is_locked') or 0)):
                raise ValueError('هذا القيد مرتبط بعملية مولّدة ولا يُعدّل منفرداً. عدّل العملية الأصلية من إجراءات القيد.')
            if existing:
                summary = get_payment_summary(self.db.get_connection(), existing)
                if amount + 0.005 < float(summary['paid_amount_original']):
                    raise ValueError("لا يمكن جعل إجمالي القيد أقل من مجموع الدفعات المسجلة")
                if currency_code != existing.get('currency_original') and float(summary['paid_amount_original']) > 0:
                    raise ValueError("لا يمكن تغيير عملة قيد عليه دفعات. احذف الدفعات أولاً")
        data = {
            'company_name': company_name, 'amount': amount, 'type': type_val, 'date': date, 'notes': notes,
            'currency': currency_code, 'updated_by': user_id, 'updated_at': now,
            'payment_due_date': payment_due_date, 'payment_reminder_note': payment_note,
            'person_name': person_name, 'service_type': service_type, 'operation_type': operation_type,
            'is_locked': existing.get('is_locked', 0) if existing else 0,
            'source_type': existing.get('source_type') if existing else None,
            'source_ref': existing.get('source_ref') if existing else None,
            'reversal_of': existing.get('reversal_of') if existing else None,
            'reversed_by': existing.get('reversed_by') if existing else None,
            'print_description': existing.get('print_description') if existing else None,
            'internal_note': existing.get('internal_note') if existing else None,
            'service_case_role': existing.get('service_case_role') if existing else None,
            'linked_company_name': existing.get('linked_company_name') if existing else None,
        }
        data = normalize_expense_metadata(self.ledger.normalize_expense_payload(data, existing=existing))
        if self.data.is_remote():
            self.data.update_expense(expense_id, data)
            return
        user = UserSession.get_current() or {}
        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                '''UPDATE expenses SET company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?, person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?, print_description=?, internal_note=?, service_case_role=?, linked_company_name=? WHERE id=?''',
                (
                    data['company_name'], data['amount'], data['amount_base'], data['type'], data['date'], data['notes'], data['currency'], data['updated_by'], data['updated_at'],
                    data['amount_original'], data['currency_original'], data['exchange_rate_to_usd'], data['status'], data['payment_due_date'], data['payment_reminder_note'],
                    data.get('person_name'), data.get('person_name_search'), data.get('service_type'), data.get('operation_type'), data.get('is_locked', 0),
                    data.get('reversal_of'), data.get('reversed_by'), data.get('print_description'), data.get('internal_note'), data.get('service_case_role'),
                    data.get('linked_company_name'), expense_id,
                ),
            )
            if cur.rowcount != 1:
                raise ValueError(f"لم يتم العثور على القيد المطلوب تعديله id={expense_id}")
            sync_payment_state(conn, expense_id, now=now)
            if amount <= 0.005 and payment_due_date:
                conn.execute("UPDATE expenses SET status='waiting_payment', payment_status='not_applicable' WHERE id=?", (expense_id,))
                conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (expense_id,))
                conn.execute(
                    "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                    (expense_id, str(payment_due_date)[:10], payment_note or "بانتظار تحديد المبلغ / الدفع", 0, now),
                )
            elif amount > 0.005:
                conn.execute("UPDATE expenses SET status='approved' WHERE id=?", (expense_id,))
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, user.get('username', ''), "تعديل قيد", 'expenses', expense_id, f"الشركة: {company_name}, الإجمالي: {amount} {currency_code}", '127.0.0.1', now),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def delete(self, expense_id: int, user_id: int = None):
        if expense_id is None:
            raise ValueError("لا يمكن حذف قيد دون معرّف id")
        expense_id = int(expense_id)
        user = UserSession.get_current() or {}
        user_id = user_id or user.get('id')
        if self.data.is_remote():
            self.data.delete_expense(expense_id)
            return
        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
            if row and (is_generated_source(row['source_type']) or int(row['is_locked'] or 0)):
                raise ValueError('هذا القيد مرتبط بعملية محاسبية ولا يُحذف منفرداً. احذف العملية الأصلية كاملة من إجراءات القيد.')
            if not row:
                raise ValueError(f"لم يتم العثور على القيد المطلوب حذفه id={expense_id}")
            payment_counts = delete_payments_for_targets(conn, [expense_id])
            conn.execute('DELETE FROM payment_reminders WHERE expense_id=?', (expense_id,))
            conn.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
            details = f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}, الدفعات المحذوفة: {payment_counts['payments']}"
            conn.execute(
                "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, user.get('username', ''), "حذف قيد", 'expenses', expense_id, details, '127.0.0.1', datetime.datetime.now().isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def get_pending_payment_reminders(self) -> List[Dict]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_pending_payment_reminders()
        conn = self.db.get_connection()
        rows = conn.execute(
            """SELECT r.*, e.company_name, e.amount_original, e.currency_original, e.type, e.person_name,
                      COALESCE(SUM(p.amount_original),0) AS paid_amount_original,
                      MAX(e.amount_original - COALESCE(SUM(p.amount_original),0),0) AS remaining_amount_original
               FROM payment_reminders r
               JOIN expenses e ON e.id = r.expense_id
               LEFT JOIN payments p ON p.target_expense_id=e.id AND p.status='posted'
               WHERE r.is_done=0 AND (e.is_settleable=1 OR e.status='waiting_payment')
               GROUP BY r.id
               HAVING remaining_amount_original > 0.005 OR e.status='waiting_payment'
               ORDER BY r.reminder_date ASC, r.id DESC"""
        ).fetchall()
        return [dict(row) for row in rows]

    def count_waiting_payment(self) -> int:
        if self.data.is_remote():
            return self.db.get_rest_client().count_waiting_payment()
        row = self.db.get_connection().execute(
            """SELECT COUNT(*) AS c FROM expenses e
               WHERE (e.is_settleable=1 AND e.amount_original >
               COALESCE((SELECT SUM(p.amount_original) FROM payments p WHERE p.target_expense_id=e.id AND p.status='posted'),0) + 0.005)
               OR e.status='waiting_payment'"""
        ).fetchone()
        return int(row['c'] if row else 0)

    def summarize_persons_by_company(self, company_name: str) -> List[Dict]:
        rows = self.get_by_company(company_name, convert_to_display=False)
        buckets = {}
        for row in rows:
            person = (row.get('person_name') or '').strip()
            if not person:
                continue
            item = buckets.setdefault(person, {'person_name': person, 'incoming': 0.0, 'outgoing': 0.0, 'count': 0, 'last_date': '', 'remaining': 0.0})
            item['count'] += 1
            amount = float(row.get('amount_base', row.get('amount', 0)) or 0)
            if row.get('type') == 'incoming':
                item['incoming'] += amount
            else:
                item['outgoing'] += amount
            item['remaining'] += float(row.get('remaining_amount_original') or 0)
            date = str(row.get('date') or '')
            if date > item['last_date']:
                item['last_date'] = date
        return sorted(buckets.values(), key=lambda x: (x['last_date'], x['person_name']), reverse=True)

    def get_summary(self, convert_to_display: bool = True) -> Dict:
        expenses = self.get_all(convert_to_display=False)
        approved = [e for e in expenses if e.get('status', 'approved') != 'waiting_payment']
        total_in = sum(self._base_amount(e) for e in approved if e['type'] == 'incoming')
        total_out = sum(self._base_amount(e) for e in approved if e['type'] == 'outgoing')
        companies_count = len(set(e['company_name'] for e in expenses))
        outstanding = sum(float(e.get('remaining_amount_original') or 0) for e in expenses if int(e.get('is_settleable') or 0))
        return {'total_incoming': total_in, 'total_outgoing': total_out, 'net': total_in - total_out, 'companies_count': companies_count, 'outstanding_original_mixed': outstanding}
