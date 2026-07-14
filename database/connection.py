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
    # SQLite connections are thread-affine by default.  Flet Android can run
    # startup/tasks/event callbacks on different worker threads, so a singleton
    # process-wide sqlite3.Connection is unsafe and causes:
    # "SQLite objects created in a thread can only be used in that same thread".
    # Keep one connection per Python thread and expose the current thread's
    # connection through get_connection().
    _local_conn = None  # compatibility alias for the current thread connection
    _thread_local = threading.local()
    _connections = {}
    _connections_lock = threading.RLock()
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_mode()
        return cls._instance

    def _init_mode(self):
        # Bootstrap network settings without using get_connection().  During the
        # first construction self.mode is not initialized yet, and calling
        # get_connection() from here can incorrectly fall back to local mode.
        self.mode = "local" if os.environ.get("HAWAA_SERVER_PROCESS") == "1" else self._read_bootstrap_setting("network/mode", "local")
        self.server_url = self._read_bootstrap_setting("network/server_url", "")
        self._rest_client = None
        if self.mode == "client":
            from database.connection_rest import RestClient
            self._rest_client = RestClient(self.server_url)

    def _read_bootstrap_setting(self, key: str, default=None):
        try:
            conn = sqlite3.connect(get_local_db_path(), isolation_level=None)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
                row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                return row['value'] if row else default
            finally:
                conn.close()
        except Exception:
            return default

    def _get_setting_from_db(self, key: str, default=None):
        # Bootstrap settings must always be read locally even in client mode.
        if str(key).startswith('network/') or str(key).startswith('auth/'):
            return self._read_bootstrap_setting(key, default)
        try:
            if getattr(self, 'mode', 'local') == 'client':
                return default
            conn = self.get_connection()
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row['value'] if row else default
        except Exception:
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
        if self._rest_client:
            try:
                from auth.session import UserSession
                token = UserSession.get_auth_token()
                if not token:
                    token = _get_local_setting_direct('auth/network_token', '')
                if token:
                    self._rest_client.set_token(token)
            except Exception:
                pass
        return self._rest_client

    def set_token(self, token: str):
        if self._rest_client:
            self._rest_client.set_token(token)

    def _open_local_connection(self):
        db_path = get_local_db_path()
        # check_same_thread=False is intentional here: the connection registry is
        # per-thread, but some Flet callbacks can still hand repository objects
        # across task boundaries.  WAL + busy_timeout reduce lock contention, and
        # ordinary app code should still call get_connection() rather than storing
        # raw connection objects.
        conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=5000')
        except Exception:
            pass
        return conn

    @staticmethod
    def _connection_is_open(conn) -> bool:
        """Return True only for a usable sqlite3 connection.

        Android/Flet callbacks may keep a thread-local reference to a SQLite
        handle after another part of the app closed the global connection pool
        during startup, backup restore, or mode refresh.  Returning that stale
        object later causes user-visible failures such as:
        ``Cannot operate on a closed database``.  A cheap SELECT 1 makes
        get_connection() self-healing instead of trusting the cache blindly.
        """
        if conn is None:
            return False
        try:
            conn.execute("SELECT 1")
            return True
        except sqlite3.ProgrammingError:
            return False
        except Exception:
            # Other errors (for example transient locking) do not necessarily
            # mean the handle is closed.  Keep the connection so callers can
            # receive the real database error instead of silently reopening.
            return True

    def _discard_thread_connection(self, tid: int, conn=None) -> None:
        try:
            current = getattr(self._thread_local, "conn", None)
            if conn is None or current is conn:
                self._thread_local.conn = None
        except Exception:
            pass
        with self._connections_lock:
            if conn is None or self._connections.get(tid) is conn:
                self._connections.pop(tid, None)
        if self._local_conn is conn:
            self._local_conn = None

    def get_connection(self):
        if self.mode != "client":
            tid = threading.get_ident()
            conn = getattr(self._thread_local, "conn", None)
            if conn is not None:
                if self._connection_is_open(conn):
                    self._local_conn = conn
                    return conn
                self._discard_thread_connection(tid, conn)

            with self._connections_lock:
                conn = self._connections.get(tid)
                if conn is not None and not self._connection_is_open(conn):
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self._connections.pop(tid, None)
                    conn = None
                if conn is None:
                    conn = self._open_local_connection()
                    self._connections[tid] = conn
                self._thread_local.conn = conn
                self._local_conn = conn
                return conn
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
        # Close all cached per-thread SQLite handles.  This is used before
        # replacing/restoring the database and by migrations during bootstrap.
        with self._connections_lock:
            for conn in list(self._connections.values()):
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
        try:
            self._thread_local.conn = None
        except Exception:
            pass
        self._local_conn = None

    @classmethod
    def reset_after_restore(cls):
        """Force every future repository call to open the restored SQLite DB.

        Android/Flet callbacks can keep the DatabaseConnection singleton alive
        while a backup is restored.  Closing handles is not enough if the
        singleton still carries old mode/server state.  This hard reset is used
        immediately after replacing hawaa_data.db so refreshed views read the
        imported data, not the old connection/mode.
        """
        try:
            inst = cls._instance
            if inst is not None:
                inst.close()
        except Exception:
            pass
        with cls._lock:
            cls._instance = None
        try:
            cls._thread_local.conn = None
        except Exception:
            pass
        cls._local_conn = None

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
        cursor = conn.execute('''INSERT INTO expenses (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd, status, payment_due_date, payment_reminder_note)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                             (data['company_name'], data['amount'], data.get('amount_base', data['amount']), data['type'], data['date'], data.get('notes',''), data['currency'],
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
        cur = conn.execute('''UPDATE expenses SET company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=? WHERE id=?''',
                     (data['company_name'], data['amount'], data.get('amount_base', data['amount']), data['type'], data['date'], data.get('notes',''), data['currency'],
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
        code = (currency_code or 'USD').upper()
        old_row = conn.execute("SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?", (code,)).fetchone()
        previous = float(old_row['rate_to_usd']) if old_row else None
        conn.execute("INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
                     (code, float(rate_to_usd), now))
        conn.execute("CREATE TABLE IF NOT EXISTS exchange_rate_history (id INTEGER PRIMARY KEY AUTOINCREMENT, currency_code TEXT NOT NULL, rate_to_usd REAL NOT NULL, previous_rate_to_usd REAL, changed_by INTEGER, changed_at TEXT NOT NULL)")
        conn.execute("INSERT INTO exchange_rate_history (currency_code, rate_to_usd, previous_rate_to_usd, changed_by, changed_at) VALUES (?,?,?,?,?)",
                     (code, float(rate_to_usd), previous, None, now))
        conn.commit()

    def get_exchange_rate_history(self):
        if self.mode == "client":
            return self._rest_client.get_exchange_rate_history()
        conn = self.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS exchange_rate_history (id INTEGER PRIMARY KEY AUTOINCREMENT, currency_code TEXT NOT NULL, rate_to_usd REAL NOT NULL, previous_rate_to_usd REAL, changed_by INTEGER, changed_at TEXT NOT NULL)")
        rows = conn.execute("SELECT * FROM exchange_rate_history ORDER BY id DESC LIMIT 200").fetchall()
        return [dict(row) for row in rows]

    def vacuum(self):
        if self.mode != "client":
            self.get_connection().execute("VACUUM")

    def refresh_mode(self):
        """إعادة تحميل وضع التشغيل من قاعدة البيانات (بعد تغيير الإعدادات)"""
        self.mode = "local" if os.environ.get("HAWAA_SERVER_PROCESS") == "1" else self._read_bootstrap_setting("network/mode", "local")
        self.server_url = self._read_bootstrap_setting("network/server_url", "")
        if self.mode == "client":
            from database.connection_rest import RestClient
            self._rest_client = RestClient(self.server_url)
            try:
                from auth.session import UserSession
                token = UserSession.get_auth_token() or _get_local_setting_direct('auth/network_token', '')
                if token:
                    self._rest_client.set_token(token)
            except Exception:
                pass
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
    if str(key).startswith('network/') or str(key).startswith('auth/'):
        return _get_local_setting_direct(key, default)
    return DatabaseConnection().get_setting(key, default)


def set_setting(key: str, value: str):
    # network/mode and network/server_url are bootstrap settings. They must be
    # written locally even while the app is currently in client mode, otherwise
    # switching back/forth can try to call a remote server before the mode exists.
    if str(key).startswith('network/') or str(key).startswith('auth/'):
        _set_local_setting_direct(key, value)
        return
    return DatabaseConnection().set_setting(key, value)
