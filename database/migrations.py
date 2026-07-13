# -*- coding: utf-8 -*-
"""SQLite schema creation and lossless migration for Android local databases."""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path

from auth.password import hash_password
from database.connection import DatabaseConnection, get_local_db_path

CURRENT_SCHEMA_VERSION = 23

_DEFAULT_RATES = (
    ("USD", 1.0),
    ("SAR", 3.75),
    ("SYP", 14000.0),
    ("EUR", 0.92),
    ("GBP", 0.79),
    ("AED", 3.67),
    ("QAR", 3.64),
    ("KWD", 0.31),
    ("OMR", 0.38),
)

_SETTINGS_DEFAULTS = {
    "currency_decimals": "2",
    "number_format": "western",
    "language": "ar",
    "theme": "light",
    "base_currency": "USD",
    "display_currency": "USD",
    "schema_version": str(CURRENT_SCHEMA_VERSION),
    "abbreviate_numbers": "false",
    "network/mode": "local",
    "network/server_url": "",
    "network/allow_insecure_http": "false",
    "company_name": "هوى الشام للسياحة والسفر",
    "company_address": "الجمهورية العربية السورية - محافظة درعا - نوى",
    "company_phone": "+963 968 155 010",
    "company_email": "hawa.alsham990@gmail.com",
    "company_tax_number": "",
    "company_logo_path": "",
}

_TABLE_SQL = (
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT,
        role TEXT DEFAULT 'user',
        created_at TEXT,
        last_login TEXT,
        force_password_change INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        table_name TEXT,
        record_id INTEGER,
        details TEXT,
        ip_address TEXT,
        timestamp TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        amount REAL NOT NULL,
        amount_base REAL NOT NULL DEFAULT 0,
        type TEXT NOT NULL CHECK(type IN ('incoming','outgoing')),
        date TEXT NOT NULL,
        notes TEXT,
        currency TEXT DEFAULT 'USD',
        created_by INTEGER,
        created_at TEXT,
        updated_by INTEGER,
        updated_at TEXT,
        amount_original REAL NOT NULL DEFAULT 0,
        currency_original TEXT NOT NULL DEFAULT 'USD',
        exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0,
        status TEXT NOT NULL DEFAULT 'approved',
        payment_due_date TEXT,
        payment_reminder_note TEXT,
        source_type TEXT,
        source_ref TEXT,
        counterparty_company_name TEXT,
        person_name TEXT,
        person_name_search TEXT,
        service_type TEXT NOT NULL DEFAULT 'غير محدد',
        operation_type TEXT NOT NULL DEFAULT 'normal',
        is_locked INTEGER NOT NULL DEFAULT 0,
        reversal_of INTEGER,
        reversed_by INTEGER,
        print_description TEXT,
        internal_note TEXT,
        service_case_role TEXT,
        linked_company_name TEXT
    )""",
    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
    """CREATE TABLE IF NOT EXISTS exchange_rates (
        currency_code TEXT PRIMARY KEY,
        rate_to_usd REAL NOT NULL,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS exchange_rate_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        currency_code TEXT NOT NULL,
        rate_to_usd REAL NOT NULL,
        previous_rate_to_usd REAL,
        changed_by INTEGER,
        changed_at TEXT NOT NULL
    )""",
    "CREATE TABLE IF NOT EXISTS token_blacklist (jti TEXT PRIMARY KEY, created_at TEXT)",
    """CREATE TABLE IF NOT EXISTS payment_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_id INTEGER NOT NULL,
        reminder_date TEXT NOT NULL,
        note TEXT,
        is_done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(expense_id) REFERENCES expenses(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS third_party_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE NOT NULL,
        payer_company_name TEXT NOT NULL,
        paid_to_company_name TEXT NOT NULL,
        amount_original REAL NOT NULL,
        currency_original TEXT NOT NULL,
        exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0,
        amount_base REAL NOT NULL DEFAULT 0,
        date TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'approved',
        payer_expense_id INTEGER,
        paid_to_expense_id INTEGER,
        created_by INTEGER,
        created_at TEXT,
        reversed_at TEXT,
        reversal_ref TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS service_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE NOT NULL,
        client_company_name TEXT NOT NULL,
        supplier_company_name TEXT NOT NULL,
        person_name TEXT NOT NULL,
        service_type TEXT NOT NULL DEFAULT 'تأشيرة سياحية',
        sale_amount_original REAL NOT NULL DEFAULT 0,
        cost_amount_original REAL NOT NULL DEFAULT 0,
        currency_original TEXT NOT NULL DEFAULT 'USD',
        exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0,
        sale_amount_base REAL NOT NULL DEFAULT 0,
        cost_amount_base REAL NOT NULL DEFAULT 0,
        date TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        client_expense_id INTEGER,
        supplier_expense_id INTEGER,
        created_by INTEGER,
        created_at TEXT,
        reversed_at TEXT,
        reversal_ref TEXT,
        print_description_client TEXT,
        print_description_supplier TEXT,
        internal_note TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS service_case_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_case_ref TEXT NOT NULL,
        component_index INTEGER NOT NULL DEFAULT 1,
        service_type TEXT NOT NULL,
        supplier_company_name TEXT,
        sale_amount_original REAL NOT NULL DEFAULT 0,
        cost_amount_original REAL NOT NULL DEFAULT 0,
        currency_original TEXT NOT NULL DEFAULT 'USD',
        exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0,
        sale_amount_base REAL NOT NULL DEFAULT 0,
        cost_amount_base REAL NOT NULL DEFAULT 0,
        supplier_expense_id INTEGER,
        print_description_client TEXT,
        print_description_supplier TEXT,
        notes TEXT
    )""",
)

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_expenses_company ON expenses(company_name)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_source_ref ON expenses(source_ref)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_person_name_search ON expenses(person_name_search)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_operation_type ON expenses(operation_type)",
    "CREATE INDEX IF NOT EXISTS idx_third_party_payments_ref ON third_party_payments(reference)",
    "CREATE INDEX IF NOT EXISTS idx_service_cases_ref ON service_cases(reference)",
    "CREATE INDEX IF NOT EXISTS idx_service_cases_client ON service_cases(client_company_name)",
    "CREATE INDEX IF NOT EXISTS idx_service_cases_supplier ON service_cases(supplier_company_name)",
    "CREATE INDEX IF NOT EXISTS idx_service_case_components_ref ON service_case_components(service_case_ref)",
    "CREATE INDEX IF NOT EXISTS idx_service_case_components_supplier ON service_case_components(supplier_company_name)",
    "CREATE INDEX IF NOT EXISTS idx_payment_reminders_date ON payment_reminders(reminder_date)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
)

_EXPENSE_COLUMNS = {
    "amount_base": "REAL NOT NULL DEFAULT 0",
    "notes": "TEXT",
    "currency": "TEXT DEFAULT 'USD'",
    "created_by": "INTEGER",
    "created_at": "TEXT",
    "updated_by": "INTEGER",
    "updated_at": "TEXT",
    "amount_original": "REAL NOT NULL DEFAULT 0",
    "currency_original": "TEXT NOT NULL DEFAULT 'USD'",
    "exchange_rate_to_usd": "REAL NOT NULL DEFAULT 1.0",
    "status": "TEXT NOT NULL DEFAULT 'approved'",
    "payment_due_date": "TEXT",
    "payment_reminder_note": "TEXT",
    "source_type": "TEXT",
    "source_ref": "TEXT",
    "counterparty_company_name": "TEXT",
    "person_name": "TEXT",
    "person_name_search": "TEXT",
    "service_type": "TEXT NOT NULL DEFAULT 'غير محدد'",
    "operation_type": "TEXT NOT NULL DEFAULT 'normal'",
    "is_locked": "INTEGER NOT NULL DEFAULT 0",
    "reversal_of": "INTEGER",
    "reversed_by": "INTEGER",
    "print_description": "TEXT",
    "internal_note": "TEXT",
    "service_case_role": "TEXT",
    "linked_company_name": "TEXT",
}

_USER_COLUMNS = {
    "full_name": "TEXT",
    "role": "TEXT DEFAULT 'user'",
    "created_at": "TEXT",
    "last_login": "TEXT",
    "force_password_change": "INTEGER DEFAULT 0",
}

_AUDIT_COLUMNS = {
    "user_id": "INTEGER",
    "username": "TEXT",
    "action": "TEXT",
    "table_name": "TEXT",
    "record_id": "INTEGER",
    "details": "TEXT",
    "ip_address": "TEXT",
    "timestamp": "TEXT",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _add_columns(
    conn: sqlite3.Connection, table: str, definitions: dict[str, str]
) -> set[str]:
    existing = _column_names(conn, table)
    added: set[str] = set()
    for name, definition in definitions.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')
            added.add(name)
    return added


def _validate_legacy_core(conn: sqlite3.Connection) -> None:
    tables = {name for name in _table_names(conn) if not name.startswith("sqlite_")}
    if not tables or tables.issubset({"settings"}):
        # DatabaseConnection may create a bootstrap settings table before the
        # first full schema initialization; treat that file as a new database.
        return
    if "expenses" not in tables:
        raise ValueError("قاعدة البيانات القديمة لا تحتوي جدول القيود expenses")
    expense_cols = _column_names(conn, "expenses")
    required = {"company_name", "amount", "type", "date"}
    missing = sorted(required - expense_cols)
    if missing:
        raise ValueError("جدول القيود القديم يفتقد أعمدة أساسية: " + ", ".join(missing))
    if "users" in tables:
        user_cols = _column_names(conn, "users")
        if "password_hash" not in user_cols or "salt" not in user_cols:
            if "password" not in user_cols:
                raise ValueError(
                    "جدول المستخدمين القديم لا يحتوي صيغة كلمة مرور قابلة للترحيل"
                )


def _migrate_plaintext_passwords(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn, "users")
    if "password" not in cols or {"password_hash", "salt"}.issubset(cols):
        return
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "salt" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN salt TEXT")
    rows = conn.execute("SELECT id, password FROM users").fetchall()
    for user_id, password in rows:
        pwd_hash, salt = hash_password(str(password or ""))
        conn.execute(
            "UPDATE users SET password_hash=?, salt=? WHERE id=?",
            (pwd_hash, salt, user_id),
        )


def _normalize_expense_rows(conn: sqlite3.Connection, added: set[str]) -> None:
    if "currency" in added:
        conn.execute(
            "UPDATE expenses SET currency='USD' WHERE currency IS NULL OR TRIM(currency)='' "
        )
    if "amount_base" in added:
        conn.execute("UPDATE expenses SET amount_base=amount")
    else:
        conn.execute("UPDATE expenses SET amount_base=amount WHERE amount_base IS NULL")
    if "amount_original" in added:
        conn.execute("UPDATE expenses SET amount_original=amount")
    else:
        conn.execute(
            "UPDATE expenses SET amount_original=amount WHERE amount_original IS NULL"
        )
    if "currency_original" in added:
        conn.execute(
            "UPDATE expenses SET currency_original=COALESCE(NULLIF(currency,''),'USD')"
        )
    else:
        conn.execute(
            "UPDATE expenses SET currency_original=COALESCE(NULLIF(currency_original,''), NULLIF(currency,''), 'USD')"
        )
    conn.execute(
        "UPDATE expenses SET exchange_rate_to_usd=1.0 WHERE exchange_rate_to_usd IS NULL OR exchange_rate_to_usd<=0"
    )
    conn.execute(
        "UPDATE expenses SET status='approved' WHERE status IS NULL OR TRIM(status)='' "
    )
    conn.execute(
        "UPDATE expenses SET service_type='غير محدد' WHERE service_type IS NULL OR TRIM(service_type)='' "
    )
    conn.execute(
        "UPDATE expenses SET operation_type='normal' WHERE operation_type IS NULL OR TRIM(operation_type)='' "
    )
    if "is_locked" in added:
        conn.execute(
            "UPDATE expenses SET is_locked=1 WHERE source_type IS NOT NULL AND TRIM(source_type)<>''"
        )
    try:
        from services.company_search_service import normalize_search_text

        rows = conn.execute(
            "SELECT id, person_name FROM expenses "
            "WHERE person_name IS NOT NULL AND TRIM(person_name)<>'' "
            "AND (person_name_search IS NULL OR TRIM(person_name_search)='')"
        ).fetchall()
        for expense_id, person_name in rows:
            conn.execute(
                "UPDATE expenses SET person_name_search=? WHERE id=?",
                (normalize_search_text(person_name), expense_id),
            )
    except Exception:
        pass


def migrate_database_file(db_path: str, *, create_admin_if_empty: bool = True) -> dict:
    """Migrate a database in place, preserving all existing rows.

    This function is also used on a temporary copy during backup restore. Any
    failure raises and leaves the active application database untouched.
    """
    path = str(Path(db_path))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if str(integrity).lower() != "ok":
            raise ValueError(f"فحص سلامة SQLite فشل قبل الترحيل: {integrity}")
        if not is_new:
            _validate_legacy_core(conn)
        conn.execute("BEGIN IMMEDIATE")
        for statement in _TABLE_SQL:
            conn.execute(statement)

        _migrate_plaintext_passwords(conn)
        expense_added = _add_columns(conn, "expenses", _EXPENSE_COLUMNS)
        _add_columns(conn, "users", _USER_COLUMNS)
        _add_columns(conn, "audit_log", _AUDIT_COLUMNS)
        _normalize_expense_rows(conn, expense_added)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for key, value in _SETTINGS_DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (key, value)
            )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
            (str(CURRENT_SCHEMA_VERSION),),
        )
        # Credentials persisted by old APK versions must not survive migration.
        conn.execute("DELETE FROM settings WHERE key='auth/network_token'")

        for code, rate in _DEFAULT_RATES:
            conn.execute(
                "INSERT OR IGNORE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
                (code, rate, now),
            )

        user_count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        if create_admin_if_empty and user_count == 0:
            pwd_hash, salt = hash_password("admin123")
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, full_name, role, created_at, force_password_change) "
                "VALUES (?,?,?,?,?,?,1)",
                ("admin", pwd_hash, salt, "المدير العام", "admin", now),
            )

        for statement in _INDEX_SQL:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
        conn.commit()

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if str(integrity).lower() != "ok":
            raise ValueError(f"فحص سلامة SQLite فشل بعد الترحيل: {integrity}")
        count_queries = {
            "users": "SELECT COUNT(*) FROM users",
            "expenses": "SELECT COUNT(*) FROM expenses",
            "settings": "SELECT COUNT(*) FROM settings",
            "exchange_rates": "SELECT COUNT(*) FROM exchange_rates",
            "audit_log": "SELECT COUNT(*) FROM audit_log",
        }
        counts = {
            table: int(conn.execute(query).fetchone()[0])
            for table, query in count_queries.items()
        }
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "is_new": is_new,
            "counts": counts,
            "path": path,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_legacy_settings_json(db_path: str) -> None:
    old_settings_file = os.path.join(os.path.dirname(db_path), "settings.json")
    if not os.path.exists(old_settings_file):
        return
    try:
        with open(old_settings_file, "r", encoding="utf-8") as file_obj:
            old_settings = json.load(file_obj)
        conn = sqlite3.connect(db_path)
        try:
            for key, value in dict(old_settings or {}).items():
                if str(key) == "auth/network_token":
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                    (str(key), str(value)),
                )
            conn.commit()
        finally:
            conn.close()
        migrated_name = old_settings_file + ".migrated"
        os.replace(old_settings_file, migrated_name)
    except Exception as exc:
        raise RuntimeError(f"فشل ترحيل settings.json القديم: {exc}") from exc


def init_database() -> dict:
    db = DatabaseConnection()
    db.close()
    db_path = get_local_db_path()
    result = migrate_database_file(db_path, create_admin_if_empty=True)
    _migrate_legacy_settings_json(db_path)
    DatabaseConnection.reset_after_restore()
    return result


def ensure_db() -> dict:
    """Create or migrate the active database; never hide migration failures."""
    db = DatabaseConnection()
    db.close()
    result = migrate_database_file(get_local_db_path(), create_admin_if_empty=True)
    _migrate_legacy_settings_json(get_local_db_path())
    DatabaseConnection.reset_after_restore()
    return result
