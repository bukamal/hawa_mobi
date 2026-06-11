# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
from typing import Dict, List, Any


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
        cur = conn.execute(
            """INSERT INTO expenses
            (company_name, amount, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["company_name"], data["amount"], data["type"], data["date"], data.get("notes", ""), data["currency"],
                data.get("created_by", 1), data.get("created_at", now), data.get("updated_by", 1), data.get("updated_at", now),
                data.get("amount_original", data["amount"]), data.get("currency_original", data["currency"]),
                data.get("exchange_rate_to_usd", 1.0), data.get("status", "approved"), data.get("payment_due_date"),
                data.get("payment_reminder_note"),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

    def update_expense(self, expense_id: int, data: Dict[str, Any]) -> None:
        conn = self.get_connection()
        now = datetime.datetime.now().isoformat()
        cur = conn.execute(
            """UPDATE expenses SET
            company_name=?, amount=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?,
            amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?
            WHERE id=?""",
            (
                data["company_name"], data["amount"], data["type"], data["date"], data.get("notes", ""), data["currency"],
                data.get("updated_by", 1), data.get("updated_at", now), data.get("amount_original", data["amount"]),
                data.get("currency_original", data["currency"]), data.get("exchange_rate_to_usd", 1.0),
                data.get("status", "approved"), data.get("payment_due_date"), data.get("payment_reminder_note"), int(expense_id),
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
        conn.execute("DELETE FROM payment_reminders WHERE expense_id=?", (int(expense_id),))
        conn.commit()

    def get_users(self) -> List[Dict[str, Any]]:
        rows = self.get_connection().execute(
            "SELECT id, username, full_name, role, created_at, last_login, force_password_change FROM users ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_user(self, data: Dict[str, Any]) -> int:
        from auth.password import hash_password
        pwd_hash, salt = hash_password(data["password"])
        now = datetime.datetime.now().isoformat()
        cur = self.get_connection().execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            (data["username"], pwd_hash, salt, data.get("full_name", ""), data.get("role", "user"), now),
        )
        self.get_connection().commit()
        return int(cur.lastrowid)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        rows = self.get_connection().execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000").fetchall()
        return [dict(row) for row in rows]

    def get_setting(self, key: str, default=None):
        conn = self.get_connection()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str) -> None:
        conn = self.get_connection()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        conn.commit()

    def get_all_currencies(self) -> List[Dict[str, Any]]:
        rows = self.get_connection().execute(
            "SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code"
        ).fetchall()
        return [dict(row) for row in rows]

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float) -> None:
        now = datetime.datetime.now().isoformat()
        conn = self.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
            (currency_code, float(rate_to_usd), now),
        )
        conn.commit()
