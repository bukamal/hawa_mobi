# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Dict, List, Any
from services.ledger_operation_service import normalize_expense_metadata


class LocalDataSource:
    """SQLite-backed data source.

    It deliberately receives the existing DatabaseConnection instance so this
    phase can introduce a clean boundary without changing migrations, storage
    paths, or the already-tested singleton lifecycle.
    """

    def __init__(self, db):
        self.db = db

    def is_remote(self) -> bool:
        return False

    def execute(self, sql: str, params=(), audit_data=None):
        return self.db.execute(sql, params, audit_data)

    def executemany(self, sql: str, params_list, audit_data=None):
        return self.db.executemany(sql, params_list, audit_data)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def begin(self) -> None:
        self.db.begin()

    def get_connection(self):
        return self.db.get_connection()

    def get_expenses(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def add_expense(self, data: Dict[str, Any]) -> int:
        conn = self.get_connection()
        now = datetime.datetime.now().isoformat()
        data = normalize_expense_metadata(data)
        cur = conn.execute(
            """INSERT INTO expenses
            (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note, source_type, source_ref, counterparty_company_name,
             person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by, print_description, internal_note, service_case_role, linked_company_name)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["company_name"],
                data["amount"],
                data.get("amount_base", data["amount"]),
                data["type"],
                data["date"],
                data.get("notes", ""),
                data["currency"],
                data.get("created_by", 1),
                data.get("created_at", now),
                data.get("updated_by", 1),
                data.get("updated_at", now),
                data.get("amount_original", data["amount"]),
                data.get("currency_original", data["currency"]),
                data.get("exchange_rate_to_usd", 1.0),
                data.get("status", "approved"),
                data.get("payment_due_date"),
                data.get("payment_reminder_note"),
                data.get("source_type"),
                data.get("source_ref"),
                data.get("counterparty_company_name"),
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
        return int(cur.lastrowid)

    def update_expense(self, expense_id: int, data: Dict[str, Any]) -> None:
        conn = self.get_connection()
        now = datetime.datetime.now().isoformat()
        data = normalize_expense_metadata(data)
        cur = conn.execute(
            """UPDATE expenses SET
            company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?,
            amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?,
            person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?, print_description=?, internal_note=?, service_case_role=?, linked_company_name=?
            WHERE id=?""",
            (
                data["company_name"],
                data["amount"],
                data.get("amount_base", data["amount"]),
                data["type"],
                data["date"],
                data.get("notes", ""),
                data["currency"],
                data.get("updated_by", 1),
                data.get("updated_at", now),
                data.get("amount_original", data["amount"]),
                data.get("currency_original", data["currency"]),
                data.get("exchange_rate_to_usd", 1.0),
                data.get("status", "approved"),
                data.get("payment_due_date"),
                data.get("payment_reminder_note"),
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
                int(expense_id),
            ),
        )
        if cur.rowcount != 1:
            conn.rollback()
            raise ValueError(f"Expense not found: {expense_id}")
        conn.commit()

    def delete_expense(self, expense_id: int) -> None:
        conn = self.get_connection()
        cur = conn.execute("DELETE FROM expenses WHERE id=?", (int(expense_id),))
        if cur.rowcount != 1:
            conn.rollback()
            raise ValueError(f"Expense not found: {expense_id}")
        conn.execute(
            "DELETE FROM payment_reminders WHERE expense_id=?", (int(expense_id),)
        )
        conn.commit()

    def search_company_ledger(
        self, query: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        from services.company_search_service import search_expense_rows

        conn = self.get_connection()
        rows = conn.execute("""
            SELECT
                e.*,
                u.username AS created_username,
                u.full_name AS created_full_name
            FROM expenses e
            LEFT JOIN users u ON u.id = e.created_by
            ORDER BY e.date DESC, e.id DESC
        """).fetchall()
        return search_expense_rows([dict(row) for row in rows], query, limit=limit)

    def get_users(self) -> List[Dict[str, Any]]:
        rows = (
            self.get_connection()
            .execute(
                "SELECT id, username, full_name, role, created_at, last_login, force_password_change FROM users ORDER BY id"
            )
            .fetchall()
        )
        return [dict(row) for row in rows]

    def add_user(self, data: Dict[str, Any]) -> int:
        from auth.password import hash_password

        pwd_hash, salt = hash_password(data["password"])
        now = datetime.datetime.now().isoformat()
        cur = self.get_connection().execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            (
                data["username"],
                pwd_hash,
                salt,
                data.get("full_name", ""),
                data.get("role", "user"),
                now,
            ),
        )
        self.get_connection().commit()
        return int(cur.lastrowid)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        rows = (
            self.get_connection()
            .execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000")
            .fetchall()
        )
        return [dict(row) for row in rows]

    def get_setting(self, key: str, default=None):
        conn = self.get_connection()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str) -> None:
        conn = self.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
            (key, str(value)),
        )
        conn.commit()

    def get_all_currencies(self) -> List[Dict[str, Any]]:
        rows = (
            self.get_connection()
            .execute(
                "SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code"
            )
            .fetchall()
        )
        return [dict(row) for row in rows]

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float) -> None:
        now = datetime.datetime.now().isoformat()
        conn = self.get_connection()
        code = (currency_code or "USD").upper()
        old_row = conn.execute(
            "SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?", (code,)
        ).fetchone()
        previous = float(old_row["rate_to_usd"]) if old_row else None
        conn.execute(
            "INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
            (code, float(rate_to_usd), now),
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS exchange_rate_history (id INTEGER PRIMARY KEY AUTOINCREMENT, currency_code TEXT NOT NULL, rate_to_usd REAL NOT NULL, previous_rate_to_usd REAL, changed_by INTEGER, changed_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO exchange_rate_history (currency_code, rate_to_usd, previous_rate_to_usd, changed_by, changed_at) VALUES (?,?,?,?,?)",
            (code, float(rate_to_usd), previous, None, now),
        )
        conn.commit()

    def get_exchange_rate_history(self) -> List[Dict[str, Any]]:
        rows = (
            self.get_connection()
            .execute("SELECT * FROM exchange_rate_history ORDER BY id DESC LIMIT 200")
            .fetchall()
        )
        return [dict(row) for row in rows]
