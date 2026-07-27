#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify an existing phase-107 style database upgrades without data loss."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase108-migration-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from database.connection import get_local_db_path
from database.migrations import ensure_db


def main():
    # Minimal schema equivalent to the payment tables before phase 108.
    db_path = get_local_db_path()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, amount REAL NOT NULL,
          amount_base REAL NOT NULL DEFAULT 0, type TEXT NOT NULL, date TEXT NOT NULL, notes TEXT, currency TEXT DEFAULT 'USD',
          created_by INTEGER, created_at TEXT, updated_by INTEGER, updated_at TEXT, amount_original REAL NOT NULL DEFAULT 0,
          currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, status TEXT NOT NULL DEFAULT 'approved',
          payment_due_date TEXT, payment_reminder_note TEXT, source_type TEXT, source_ref TEXT, counterparty_company_name TEXT,
          person_name TEXT, person_name_search TEXT, service_type TEXT NOT NULL DEFAULT 'غير محدد', operation_type TEXT NOT NULL DEFAULT 'normal',
          is_locked INTEGER NOT NULL DEFAULT 0, reversal_of INTEGER, reversed_by INTEGER, print_description TEXT, internal_note TEXT,
          service_case_role TEXT, linked_company_name TEXT, is_settleable INTEGER NOT NULL DEFAULT 1, payment_status TEXT NOT NULL DEFAULT 'unpaid');
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE exchange_rates (currency_code TEXT PRIMARY KEY, rate_to_usd REAL NOT NULL, updated_at TEXT);
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, salt TEXT, full_name TEXT, role TEXT, created_at TEXT, last_login TEXT, force_password_change INTEGER DEFAULT 0);
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, table_name TEXT, record_id INTEGER, details TEXT, ip_address TEXT, timestamp TEXT);
        CREATE TABLE payments (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL, target_expense_id INTEGER NOT NULL,
          company_name TEXT NOT NULL, person_name TEXT, source_type TEXT, source_ref TEXT, party_role TEXT, amount_original REAL NOT NULL,
          currency_original TEXT NOT NULL, exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, amount_base REAL NOT NULL DEFAULT 0,
          direction TEXT NOT NULL, payment_method TEXT NOT NULL DEFAULT 'cash', date TEXT NOT NULL, reference_number TEXT, notes TEXT,
          ledger_expense_id INTEGER, status TEXT NOT NULL DEFAULT 'posted', created_by INTEGER, created_at TEXT, updated_by INTEGER, updated_at TEXT);
        INSERT INTO settings(key,value) VALUES ('schema_version','24');
        INSERT INTO exchange_rates(currency_code,rate_to_usd,updated_at) VALUES ('USD',1.0,'2026-07-27');
        INSERT INTO expenses(company_name,amount,amount_base,type,date,amount_original,currency_original,exchange_rate_to_usd)
          VALUES ('شركة قديمة',100,100,'incoming','2026-07-01',100,'USD',1.0);
        """
    )
    conn.commit()
    conn.close()

    ensure_db()
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "payment_batches" in tables
        assert "payment_allocations" in tables
        payment_cols = {row[1] for row in conn.execute("PRAGMA table_info(payments)")}
        assert "batch_id" in payment_cols
        version = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
        assert version == "25", version
        assert conn.execute("SELECT COUNT(*) FROM expenses WHERE company_name='شركة قديمة'").fetchone()[0] == 1
    finally:
        conn.close()
    print("PHASE108_BATCH_PAYMENTS_MIGRATION_OK")


if __name__ == "__main__":
    main()
