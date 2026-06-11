# -*- coding: utf-8 -*-
import sqlite3
import threading
import os
import sys
from typing import List, Dict

def get_data_dir():
    """Return a writable persistent data directory on desktop and packaged Android."""
    data_dir = (
        os.environ.get('HAWAA_DATA_DIR')
        or os.environ.get('FLET_APP_STORAGE_DATA')
        or os.path.expanduser('~/.hawaa')
    )
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_local_db_path():
    return os.path.join(get_data_dir(), 'hawaa_data.db')

class DatabaseConnection:
    _instance = None
    _local_conn = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_mode()
        return cls._instance

    def _init_mode(self):
        self.mode = "local" if os.environ.get("HAWAA_SERVER_PROCESS") == "1" else self._get_setting_from_db("network/mode", "local")
        self.server_url = self._get_setting_from_db("network/server_url", "http://localhost:8000")
        self._rest_client = None
        if self.mode == "client":
            from database.connection_rest import RestClient
            self._rest_client = RestClient(self.server_url)

    def _get_setting_from_db(self, key: str, default=None):
        try:
            conn = self.get_connection()
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row['value'] if row else default
        except:
            return default

    def _save_setting_to_db(self, key: str, value: str):
        try:
            conn = self.get_connection()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
            conn.commit()
        except:
            pass

    def is_remote(self) -> bool:
        return self.mode == "client"

    def get_rest_client(self):
        return self._rest_client

    def set_token(self, token: str):
        if self._rest_client:
            self._rest_client.set_token(token)

    def get_connection(self):
        if self.mode != "client":
            if self._local_conn is None:
                db_path = get_local_db_path()
                self._local_conn = sqlite3.connect(db_path, isolation_level=None)
                self._local_conn.row_factory = sqlite3.Row
                self._local_conn.execute('PRAGMA journal_mode=WAL')
            return self._local_conn
        return None

    def _log_audit_local(self, user_id, username, action, table_name, record_id, details):
        if self.mode == "client":
            # في وضع العميل، نرسل سجل التدقيق عبر REST
            if self._rest_client:
                self._rest_client.add_audit_log(user_id, username, action, table_name, record_id, details)
            return
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        conn.execute(
            "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, username, action, table_name, record_id, details, '127.0.0.1', now)
        )
        conn.commit()

    def execute(self, sql: str, params=(), audit_data=None):
        if self.mode != "client":
            conn = self.get_connection()
            cursor = conn.execute(sql, params)
            if audit_data and any(sql.strip().upper().startswith(cmd) for cmd in ('INSERT', 'UPDATE', 'DELETE')):
                self._log_audit_local(
                    audit_data.get('user_id'), audit_data.get('username'),
                    audit_data.get('action'), audit_data.get('table_name'),
                    audit_data.get('record_id'), audit_data.get('details')
                )
            return cursor
        # وضع العميل: العمليات عبر REST (لا يوجد execute مباشر)
        raise NotImplementedError("Use REST client methods for write operations in client mode")

    def executemany(self, sql: str, params_list, audit_data=None):
        if self.mode != "client":
            conn = self.get_connection()
            cursor = conn.executemany(sql, params_list)
            if audit_data and sql.strip().upper().startswith('INSERT'):
                self._log_audit_local(
                    audit_data.get('user_id'), audit_data.get('username'),
                    audit_data.get('action'), audit_data.get('table_name'),
                    audit_data.get('record_id'), audit_data.get('details')
                )
            return cursor
        raise NotImplementedError

    def commit(self):
        if self.mode != "client":
            self.get_connection().commit()

    def rollback(self):
        if self.mode != "client":
            self.get_connection().rollback()

    def begin(self):
        if self.mode != "client":
            self.execute("BEGIN TRANSACTION")

    def close(self):
        if self._local_conn:
            self._local_conn.close()
            self._local_conn = None

    # ========== CRUD helpers (تدعم local و client) ==========
    def get_expenses(self) -> List[Dict]:
        if self.mode == "client":
            return self._rest_client.get_expenses()
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def add_expense(self, data: Dict) -> int:
        if self.mode == "client":
            return self._rest_client.add_expense(data)
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        cursor = conn.execute('''INSERT INTO expenses (company_name, amount, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status, payment_due_date, payment_reminder_note)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                             (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
                              data.get('created_by',1), now, data.get('updated_by',1), now,
                              data.get('amount_original', data['amount']), data.get('currency_original', data['currency']), data.get('exchange_rate_to_usd',1.0), data.get('status','approved'), data.get('payment_due_date'), data.get('payment_reminder_note')))
        conn.commit()
        return cursor.lastrowid

    def update_expense(self, expense_id: int, data: Dict):
        if self.mode == "client":
            self._rest_client.update_expense(expense_id, data)
            return
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        cur = conn.execute('''UPDATE expenses SET company_name=?, amount=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=? WHERE id=?''',
                     (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
                      data.get('updated_by',1), now, data.get('amount_original', data['amount']), data.get('currency_original', data['currency']),
                      data.get('exchange_rate_to_usd',1.0), data.get('status','approved'), data.get('payment_due_date'), data.get('payment_reminder_note'), int(expense_id)))
        if cur.rowcount != 1:
            conn.rollback()
            raise ValueError(f"Expense not found: {expense_id}")
        conn.commit()

    def delete_expense(self, expense_id: int):
        if self.mode == "client":
            self._rest_client.delete_expense(expense_id)
            return
        conn = self.get_connection()
        cur = conn.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
        if cur.rowcount != 1:
            conn.rollback()
            raise ValueError(f"Expense not found: {expense_id}")
        conn.execute("DELETE FROM payment_reminders WHERE expense_id = ?", (int(expense_id),))
        conn.commit()

    def get_users(self) -> List[Dict]:
        if self.mode == "client":
            return self._rest_client.get_users()
        conn = self.get_connection()
        rows = conn.execute("SELECT id, username, full_name, role, created_at, last_login FROM users").fetchall()
        return [dict(row) for row in rows]

    def add_user(self, data: Dict) -> int:
        if self.mode == "client":
            return self._rest_client.add_user(data)
        from auth.password import hash_password
        pwd_hash, salt = hash_password(data['password'])
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        cursor = conn.execute("INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
                             (data['username'], pwd_hash, salt, data.get('full_name',''), data.get('role','user'), now))
        conn.commit()
        return cursor.lastrowid

    def get_audit_log(self) -> List[Dict]:
        if self.mode == "client":
            return self._rest_client.get_audit_log()
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000").fetchall()
        return [dict(row) for row in rows]

    def get_setting(self, key: str, default=None):
        if self.mode == "client" and self._rest_client and self._rest_client.token:
            val = self._rest_client.get_setting(key)
            if val is not None:
                return val
        conn = self.get_connection()
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        if self.mode == "client":
            self._rest_client.set_setting(key, value)
            return
        conn = self.get_connection()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()

    def get_all_currencies(self):
        if self.mode == "client" and self._rest_client and self._rest_client.token:
            return self._rest_client.get_all_currencies()
        conn = self.get_connection()
        rows = conn.execute("SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code").fetchall()
        return [dict(row) for row in rows]

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float):
        if self.mode == "client":
            self._rest_client.update_exchange_rate(currency_code, rate_to_usd)
            return
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        conn.execute("INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
                     (currency_code, rate_to_usd, now))
        conn.commit()

    def vacuum(self):
        if self.mode != "client" and self._local_conn:
            self._local_conn.execute("VACUUM")

    def refresh_mode(self):
        """إعادة تحميل وضع التشغيل من قاعدة البيانات (بعد تغيير الإعدادات)"""
        self.mode = "local" if os.environ.get("HAWAA_SERVER_PROCESS") == "1" else self._get_setting_from_db("network/mode", "local")
        self.server_url = self._get_setting_from_db("network/server_url", "http://localhost:8000")
        if self.mode == "client":
            from database.connection_rest import RestClient
            self._rest_client = RestClient(self.server_url)
        else:
            self._rest_client = None

# ---- Module-level compatibility helpers ----
# Some views import set_setting/get_setting directly from database.connection.
# Keep these wrappers so old and new code paths both work.
def _get_local_setting_direct(key: str, default=None):
    conn = sqlite3.connect(get_local_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default
    finally:
        conn.close()


def _set_local_setting_direct(key: str, value: str):
    conn = sqlite3.connect(get_local_db_path(), isolation_level=None)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default=None):
    if str(key).startswith('network/'):
        return _get_local_setting_direct(key, default)
    return DatabaseConnection().get_setting(key, default)


def set_setting(key: str, value: str):
    # network/mode and network/server_url are bootstrap settings. They must be
    # written locally even while the app is currently in client mode, otherwise
    # switching back/forth can try to call a remote server before the mode exists.
    if str(key).startswith('network/'):
        _set_local_setting_direct(key, value)
        return
    return DatabaseConnection().set_setting(key, value)
