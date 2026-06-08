# -*- coding: utf-8 -*-
import sqlite3
import threading
import os
import json
import sys
from typing import List, Dict

# ========== تحديد مسار البيانات حسب المنصة ==========

def _get_app_data_dir():
    """يُرجع مساراً صالحاً للكتابة على جميع المنصات (Android, Termux, Windows, Linux/macOS)"""
    
    # المحاولة 1: متغير بيئة من main.py
    env_dir = os.environ.get('HAWAA_DATA_DIR')
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir
    
    # المحاولة 2: مسار الملف الحالي (يعمل في APK)
    try:
        current_file = os.path.abspath(__file__)
        # __file__ = /data/user/0/.../files/flet/app/database/connection.py
        app_dir = os.path.dirname(os.path.dirname(current_file))  # .../files/flet/app/
        if os.path.exists(app_dir) and os.access(app_dir, os.W_OK):
            data_dir = os.path.join(os.path.dirname(app_dir), 'app_data')  # .../files/app_data/
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
    except Exception:
        pass
    
    # المحاولة 3: os.getcwd() (لبيئة التطوير العادية)
    try:
        cwd = os.getcwd()
        if 'files' in cwd and os.access(cwd, os.W_OK):
            data_dir = os.path.join(cwd, 'app_data')
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
    except Exception:
        pass
    
    # المحاولة 4: Termux Android
    if os.path.exists("/data/data/com.termux"):
        termux_dir = os.path.expanduser("~/storage/shared/.hawaa")
        os.makedirs(termux_dir, exist_ok=True)
        return termux_dir
    
    # المحاولة 5: Windows
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming'))
        data_dir = os.path.join(appdata, 'Hawaa')
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    # المحاولة 6: Linux/macOS عادي
    home_dir = os.path.expanduser("~/.hawaa")
    os.makedirs(home_dir, exist_ok=True)
    return home_dir


def get_local_db_path():
    """يُرجع مسار قاعدة البيانات المحلية"""
    data_dir = _get_app_data_dir()
    return os.path.join(data_dir, 'hawaa_data.db')


# ========== إعدادات JSON ==========

def _get_settings_file():
    return os.path.join(os.path.dirname(get_local_db_path()), 'settings.json')


def _load_settings():
    settings_file = _get_settings_file()
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(settings):
    settings_file = _get_settings_file()
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_setting(key: str, default=None):
    return _load_settings().get(key, default)


def set_setting(key: str, value):
    s = _load_settings()
    s[key] = value
    _save_settings(s)


# ========== Database Connection ==========

LOCAL_DB_PATH = get_local_db_path()


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
        self.mode = get_setting("network/mode", "local")
        self.server_url = get_setting("network/server_url", "http://localhost:8000")
        self._rest_client = None
        if self.mode == "client":
            from database.connection_rest import RestClient
            self._rest_client = RestClient(self.server_url)
    
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
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                self._local_conn = sqlite3.connect(db_path, isolation_level=None)
                self._local_conn.row_factory = sqlite3.Row
                self._local_conn.execute('PRAGMA journal_mode=WAL')
            return self._local_conn
        return None
    
    def _log_audit_local(self, user_id, username, action, table_name, record_id, details):
        if self.mode == "client":
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
            if audit_data and any(sql.strip().upper().startswith(cmd) for cmd in ('INSERT','UPDATE','DELETE')):
                self._log_audit_local(
                    audit_data.get('user_id'), audit_data.get('username'),
                    audit_data.get('action'), audit_data.get('table_name'),
                    audit_data.get('record_id'), audit_data.get('details')
                )
            return cursor
        raise NotImplementedError("Use REST client methods in client mode")
    
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
    
    # ========== CRUD helpers ==========
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
        cursor = conn.execute(
            "INSERT INTO expenses (company_name, amount, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
             data.get('created_by',1), now, data.get('updated_by',1), now,
             data.get('amount_original', data['amount']), data.get('currency_original', data['currency']),
             data.get('exchange_rate_to_usd', 1.0))
        )
        conn.commit()
        return cursor.lastrowid
    
    def update_expense(self, expense_id: int, data: Dict):
        if self.mode == "client":
            self._rest_client.update_expense(expense_id, data)
            return
        conn = self.get_connection()
        now = __import__('datetime').datetime.now().isoformat()
        conn.execute(
            "UPDATE expenses SET company_name=?, amount=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=? WHERE id=?",
            (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
             data.get('updated_by',1), now, data.get('amount_original', data['amount']),
             data.get('currency_original', data['currency']), data.get('exchange_rate_to_usd',1.0), expense_id)
        )
        conn.commit()
    
    def delete_expense(self, expense_id: int):
        if self.mode == "client":
            self._rest_client.delete_expense(expense_id)
            return
        conn = self.get_connection()
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
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
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            (data['username'], pwd_hash, salt, data.get('full_name',''), data.get('role','user'), now)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_audit_log(self) -> List[Dict]:
        if self.mode == "client":
            return self._rest_client.get_audit_log()
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000").fetchall()
        return [dict(row) for row in rows]
    
    def get_setting(self, key: str, default=None):
        if self.mode == "client":
            if self._rest_client is None or self._rest_client.token is None:
                return default
            val = self._rest_client.get_setting(key)
            return val if val is not None else default
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
        if self.mode == "client":
            if self._rest_client is None or self._rest_client.token is None:
                return []
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
        conn.execute(
            "INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
            (currency_code, rate_to_usd, now)
        )
        conn.commit()
    
    def vacuum(self):
        if self.mode != "client" and self._local_conn:
            self._local_conn.execute("VACUUM")
