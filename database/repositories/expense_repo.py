from database.repositories.base_repo import BaseRepository
from auth.session import UserSession
import datetime
from typing import List, Dict, Optional
from services.currency_ledger_service import CurrencyLedgerService

class ExpenseRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.ledger = CurrencyLedgerService()

    def _base_amount(self, row: Dict) -> float:
        return float(row.get('amount_base', row.get('amount', 0)) or 0)

    def get_all(self, convert_to_display: bool = True) -> List[Dict]:
        expenses = self.data.get_expenses()
        if convert_to_display:
            for e in expenses:
                e['amount_display'] = e.get('amount_original', e['amount'])
                e['currency_display'] = e.get('currency_original', e.get('currency', 'SAR'))
        return expenses
    def get_by_company(self, company_name: str, convert_to_display: bool = True) -> List[Dict]:
        all_exp = self.get_all(convert_to_display=False)
        filtered = [e for e in all_exp if e['company_name'] == company_name]
        if convert_to_display:
            for e in filtered:
                e['amount_display'] = e.get('amount_original', e['amount'])
                e['currency_display'] = e.get('currency_original', e.get('currency', 'SAR'))
        return filtered

    def search_company_ledger(self, query: str, limit: int = 100) -> List[Dict]:
        query = (query or '').strip()
        if not query:
            return []
        if hasattr(self.data, 'search_company_ledger'):
            return self.data.search_company_ledger(query, limit=limit)
        from services.company_search_service import search_expense_rows
        return search_expense_rows(self.get_all(convert_to_display=False), query, limit=limit)

    def add(self, company_name: str, amount: float, type_val: str, date: str, notes: str, currency_code: str, user_id: int, payment_due_date: Optional[str] = None, payment_note: Optional[str] = None) -> int:
        amount = float(amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        now = datetime.datetime.now().isoformat()
        data = {'company_name': company_name, 'amount': amount, 'type': type_val, 'date': date, 'notes': notes,
                'currency': currency_code, 'created_by': user_id, 'created_at': now, 'updated_by': user_id, 'updated_at': now,
                'payment_due_date': payment_due_date, 'payment_reminder_note': payment_note}
        data = self.ledger.normalize_expense_payload(data)
        status = data['status']
        if self.data.is_remote():
            return self.data.add_expense(data)
        else:
            user = UserSession.get_current()
            audit = {'user_id': user_id, 'username': user['username'] if user else '', 'action': "إضافة قيد", 'table_name': 'expenses', 'record_id': None,
                     'details': f"الشركة: {company_name}, المبلغ: {amount} {currency_code}"}
            conn = self.db.get_connection()
            cur = conn.execute('''INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status, payment_due_date, payment_reminder_note)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (data['company_name'], data['amount'], data['amount_base'], data['type'], data['date'], data['notes'], data['currency'],
                               data['created_by'], data['created_at'], data['updated_by'], data['updated_at'],
                               data['amount_original'], data['currency_original'], data['exchange_rate_to_usd'], data['status'], data['payment_due_date'], data['payment_reminder_note']))
            conn.commit()
            new_id = cur.lastrowid
            if status == 'waiting_payment' and payment_due_date:
                conn.execute("INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                             (new_id, payment_due_date, payment_note or 'بانتظار إدخال الدفعة الأولى', 0, now))
                conn.commit()
            audit['record_id'] = new_id
            self.db._log_audit_local(audit['user_id'], audit['username'], audit['action'], audit['table_name'], audit['record_id'], audit['details'])
            return new_id
    def update(self, expense_id: int, company_name: str, amount: float, type_val: str, date: str, notes: str, currency_code: str, user_id: int, payment_due_date: Optional[str] = None, payment_note: Optional[str] = None):
        if expense_id is None:
            raise ValueError("لا يمكن تعديل قيد دون معرّف id")
        expense_id = int(expense_id)
        amount = float(amount or 0)
        if amount < 0:
            raise ValueError("المبلغ لا يمكن أن يكون سالباً")
        now = datetime.datetime.now().isoformat()
        existing = None
        if not self.data.is_remote():
            existing = self.db.get_connection().execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
            existing = dict(existing) if existing else None
            if existing and existing.get('source_type') in ('third_party_payment', 'third_party_payment_reversal'):
                raise ValueError('هذا القيد مولّد من عملية سداد بالنيابة ولا يُعدّل منفرداً')
        data = {'company_name': company_name, 'amount': amount, 'type': type_val, 'date': date, 'notes': notes,
                'currency': currency_code, 'updated_by': user_id, 'updated_at': now,
                'payment_due_date': payment_due_date, 'payment_reminder_note': payment_note}
        data = self.ledger.normalize_expense_payload(data, existing=existing)
        status = data['status']
        if self.data.is_remote():
            self.data.update_expense(expense_id, data)
        else:
            user = UserSession.get_current()
            audit = {'user_id': user_id, 'username': user['username'] if user else '', 'action': "تعديل قيد", 'table_name': 'expenses', 'record_id': expense_id,
                     'details': f"الشركة: {company_name}, المبلغ: {amount} {currency_code}"}
            conn = self.db.get_connection()
            cur = conn.execute('''UPDATE expenses SET company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=? WHERE id=?''',
                         (data['company_name'], data['amount'], data['amount_base'], data['type'], data['date'], data['notes'], data['currency'],
                          data['updated_by'], data['updated_at'], data['amount_original'], data['currency_original'], data['exchange_rate_to_usd'], data['status'], data['payment_due_date'], data['payment_reminder_note'], expense_id))
            if cur.rowcount != 1:
                conn.rollback()
                raise ValueError(f"لم يتم العثور على القيد المطلوب تعديله id={expense_id}")
            if status == 'waiting_payment' and payment_due_date:
                conn.execute("DELETE FROM payment_reminders WHERE expense_id=? AND is_done=0", (expense_id,))
                conn.execute("INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                             (expense_id, payment_due_date, payment_note or 'بانتظار إدخال الدفعة الأولى', 0, now))
            else:
                conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (expense_id,))
            conn.commit()
            self.db._log_audit_local(audit['user_id'], audit['username'], audit['action'], audit['table_name'], audit['record_id'], audit['details'])
    def delete(self, expense_id: int, user_id: int = None):
        if expense_id is None:
            raise ValueError("لا يمكن حذف قيد دون معرّف id")
        expense_id = int(expense_id)
        if user_id is None:
            u = UserSession.get_current()
            user_id = u['id'] if u else None
        if self.data.is_remote():
            self.data.delete_expense(expense_id)
        else:
            conn = self.db.get_connection()
            row = conn.execute('SELECT company_name, amount_original, currency_original, source_type, source_ref FROM expenses WHERE id=?', (expense_id,)).fetchone()
            if row and row['source_type'] in ('third_party_payment', 'third_party_payment_reversal'):
                raise ValueError('هذا القيد مولّد من عملية سداد بالنيابة. استخدم عكس العملية بدلاً من الحذف.')
            details = f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}" if row else ""
            cur = conn.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
            if cur.rowcount != 1:
                conn.rollback()
                raise ValueError(f"لم يتم العثور على القيد المطلوب حذفه id={expense_id}")
            conn.execute('DELETE FROM payment_reminders WHERE expense_id=?', (expense_id,))
            conn.commit()
            u = UserSession.get_current()
            self.db._log_audit_local(user_id, u['username'] if u else '', "حذف قيد", 'expenses', expense_id, details)
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
        row = self.db.get_connection().execute("SELECT COUNT(*) AS c FROM expenses WHERE status='waiting_payment'").fetchone()
        return int(row['c'] if row else 0)

    def get_summary(self, convert_to_display: bool = True) -> Dict:
        expenses = self.get_all(convert_to_display=False)
        approved = [e for e in expenses if e.get('status', 'approved') != 'waiting_payment']
        total_in = sum(self._base_amount(e) for e in approved if e['type'] == 'incoming')
        total_out = sum(self._base_amount(e) for e in approved if e['type'] == 'outgoing')
        companies_count = len(set(e['company_name'] for e in expenses))
        return {'total_incoming': total_in, 'total_outgoing': total_out, 'net': total_in - total_out, 'companies_count': companies_count}
