# -*- coding: utf-8 -*-
import sqlite3
import os
import datetime
import json
from database.connection import DatabaseConnection, get_local_db_path
from auth.password import hash_password

def init_database():
    db = DatabaseConnection()
    db.close()
    db_path = get_local_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, full_name TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_login TEXT, force_password_change INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, table_name TEXT, record_id INTEGER, details TEXT, ip_address TEXT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, amount REAL NOT NULL, amount_base REAL NOT NULL DEFAULT 0, type TEXT NOT NULL CHECK(type IN ('incoming','outgoing')), date TEXT NOT NULL, notes TEXT, currency TEXT DEFAULT 'USD', created_by INTEGER, created_at TEXT, updated_by INTEGER, updated_at TEXT, amount_original REAL NOT NULL DEFAULT 0, currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, status TEXT NOT NULL DEFAULT 'approved', payment_due_date TEXT, payment_reminder_note TEXT, source_type TEXT, source_ref TEXT, counterparty_company_name TEXT, person_name TEXT, person_name_search TEXT, service_type TEXT NOT NULL DEFAULT 'غير محدد', operation_type TEXT NOT NULL DEFAULT 'normal', is_locked INTEGER NOT NULL DEFAULT 0, reversal_of INTEGER, reversed_by INTEGER, print_description TEXT, internal_note TEXT, service_case_role TEXT, linked_company_name TEXT);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS exchange_rates (currency_code TEXT PRIMARY KEY, rate_to_usd REAL NOT NULL, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS exchange_rate_history (id INTEGER PRIMARY KEY AUTOINCREMENT, currency_code TEXT NOT NULL, rate_to_usd REAL NOT NULL, previous_rate_to_usd REAL, changed_by INTEGER, changed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS token_blacklist (jti TEXT PRIMARY KEY, created_at TEXT);
        CREATE TABLE IF NOT EXISTS payment_reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, expense_id INTEGER NOT NULL, reminder_date TEXT NOT NULL, note TEXT, is_done INTEGER NOT NULL DEFAULT 0, created_at TEXT, FOREIGN KEY(expense_id) REFERENCES expenses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS third_party_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL, payer_company_name TEXT NOT NULL, paid_to_company_name TEXT NOT NULL, amount_original REAL NOT NULL, currency_original TEXT NOT NULL, exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, amount_base REAL NOT NULL DEFAULT 0, date TEXT NOT NULL, notes TEXT, status TEXT NOT NULL DEFAULT 'approved', payer_expense_id INTEGER, paid_to_expense_id INTEGER, created_by INTEGER, created_at TEXT, reversed_at TEXT, reversal_ref TEXT, updated_by INTEGER, updated_at TEXT, edit_reason TEXT);
        CREATE TABLE IF NOT EXISTS service_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL, client_company_name TEXT NOT NULL, supplier_company_name TEXT NOT NULL, person_name TEXT NOT NULL, service_type TEXT NOT NULL DEFAULT 'تأشيرة سياحية', sale_amount_original REAL NOT NULL DEFAULT 0, cost_amount_original REAL NOT NULL DEFAULT 0, currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, sale_amount_base REAL NOT NULL DEFAULT 0, cost_amount_base REAL NOT NULL DEFAULT 0, date TEXT NOT NULL, notes TEXT, status TEXT NOT NULL DEFAULT 'open', client_expense_id INTEGER, supplier_expense_id INTEGER, created_by INTEGER, created_at TEXT, reversed_at TEXT, reversal_ref TEXT, print_description_client TEXT, print_description_supplier TEXT, internal_note TEXT);
        CREATE TABLE IF NOT EXISTS service_case_components (id INTEGER PRIMARY KEY AUTOINCREMENT, service_case_ref TEXT NOT NULL, component_index INTEGER NOT NULL DEFAULT 1, service_type TEXT NOT NULL, supplier_company_name TEXT, sale_amount_original REAL NOT NULL DEFAULT 0, cost_amount_original REAL NOT NULL DEFAULT 0, currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, sale_amount_base REAL NOT NULL DEFAULT 0, cost_amount_base REAL NOT NULL DEFAULT 0, supplier_expense_id INTEGER, print_description_client TEXT, print_description_supplier TEXT, notes TEXT);
    ''')
    cursor.executescript('''
        CREATE INDEX IF NOT EXISTS idx_expenses_company ON expenses(company_name);
        CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
        CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status);
        CREATE INDEX IF NOT EXISTS idx_expenses_source_ref ON expenses(source_ref);
        CREATE INDEX IF NOT EXISTS idx_expenses_person_name_search ON expenses(person_name_search);
        CREATE INDEX IF NOT EXISTS idx_expenses_operation_type ON expenses(operation_type);
        CREATE INDEX IF NOT EXISTS idx_third_party_payments_ref ON third_party_payments(reference);
        CREATE INDEX IF NOT EXISTS idx_service_cases_ref ON service_cases(reference);
        CREATE INDEX IF NOT EXISTS idx_service_cases_client ON service_cases(client_company_name);
        CREATE INDEX IF NOT EXISTS idx_service_cases_supplier ON service_cases(supplier_company_name);
        CREATE INDEX IF NOT EXISTS idx_service_case_components_ref ON service_case_components(service_case_ref);
        CREATE INDEX IF NOT EXISTS idx_service_case_components_supplier ON service_case_components(supplier_company_name);
        CREATE INDEX IF NOT EXISTS idx_payment_reminders_date ON payment_reminders(reminder_date);
        CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
    ''')
    cursor.executescript('''
        INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('currency_decimals','2'),
            ('number_format','western'),
            ('language','ar'),
            ('theme','light'),
            ('base_currency','USD'),
            ('display_currency','USD'),
            ('schema_version','22'),
            ('abbreviate_numbers','false'),
            ('network/mode','local'),
            ('network/server_url','');
        INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('company_name','هوى الشام للسياحة والسفر'),
            ('company_address','المملكة العربية السعودية - الرياض'),
            ('company_phone','+966 12 3456789'),
            ('company_email','info@hawaa.com'),
            ('company_tax_number',''),
            ('company_logo_path','');
    ''')
    now = datetime.datetime.now().isoformat()
    default_rates = [('USD',1.0),('SAR',3.75),('SYP',14000.0),('EUR',0.92),('GBP',0.79),('AED',3.67),('QAR',3.64),('KWD',0.31),('OMR',0.38)]
    for code, rate in default_rates:
        cursor.execute("INSERT OR IGNORE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)", (code, rate, now))
    cursor.execute("SELECT id FROM users WHERE username='admin'")
    if not cursor.fetchone():
        pwd_hash, salt = hash_password('admin123')
        cursor.execute("INSERT INTO users (username, password_hash, salt, full_name, role, created_at, force_password_change) VALUES (?,?,?,?,?,?,?)",
                       ('admin', pwd_hash, salt, 'المدير العام', 'admin', now, 1))
    
    # ترحيل الإعدادات من settings.json القديم إن وجد
    old_settings_file = os.path.join(os.path.dirname(db_path), 'settings.json')
    if os.path.exists(old_settings_file):
        try:
            with open(old_settings_file, 'r', encoding='utf-8') as f:
                old_settings = json.load(f)
            for key, value in old_settings.items():
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
            os.remove(old_settings_file)
            print("تم ترحيل الإعدادات القديمة وحذف settings.json")
        except Exception as e:
            print(f"تحذير: فشل ترحيل settings.json: {e}")
    
    conn.commit()
    conn.close()
    print(f"✅ تم تهيئة قاعدة البيانات: {db_path}")

def ensure_db():
    db_path = get_local_db_path()
    if not os.path.exists(db_path):
        init_database()
    else:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
            if not cursor.fetchone():
                conn.close()
                init_database()
                return
            cursor.execute("PRAGMA table_info(expenses)")
            cols = [c[1] for c in cursor.fetchall()]
            if 'amount_original' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN amount_original REAL NOT NULL DEFAULT 0")
                cursor.execute("ALTER TABLE expenses ADD COLUMN currency_original TEXT NOT NULL DEFAULT 'USD'")
                cursor.execute("ALTER TABLE expenses ADD COLUMN exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0")
                cursor.execute("UPDATE expenses SET amount_original = amount, currency_original = currency, exchange_rate_to_usd = 1.0")
            if 'amount_base' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN amount_base REAL NOT NULL DEFAULT 0")
                cursor.execute("UPDATE expenses SET amount_base = amount WHERE amount_base = 0 OR amount_base IS NULL")
            # keep legacy amount column as base USD mirror for old views.
            cursor.execute("UPDATE expenses SET amount_base = amount WHERE amount_base IS NULL")
            if 'status' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'")
            if 'payment_due_date' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN payment_due_date TEXT")
            if 'payment_reminder_note' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN payment_reminder_note TEXT")
            if 'source_type' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN source_type TEXT")
            if 'source_ref' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN source_ref TEXT")
            if 'counterparty_company_name' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN counterparty_company_name TEXT")
            if 'person_name' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN person_name TEXT")
            if 'person_name_search' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN person_name_search TEXT")
            if 'service_type' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN service_type TEXT NOT NULL DEFAULT 'غير محدد'")
            if 'operation_type' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN operation_type TEXT NOT NULL DEFAULT 'normal'")
            if 'is_locked' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0")
                cursor.execute("UPDATE expenses SET is_locked=1 WHERE source_type IS NOT NULL AND source_type <> ''")
            if 'reversal_of' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN reversal_of INTEGER")
            if 'reversed_by' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN reversed_by INTEGER")
            if 'print_description' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN print_description TEXT")
            if 'internal_note' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN internal_note TEXT")
            if 'service_case_role' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN service_case_role TEXT")
            if 'linked_company_name' not in cols:
                cursor.execute("ALTER TABLE expenses ADD COLUMN linked_company_name TEXT")
            try:
                from services.company_search_service import normalize_search_text
                rows_to_index = cursor.execute("SELECT id, person_name FROM expenses WHERE person_name IS NOT NULL AND person_name <> '' AND (person_name_search IS NULL OR person_name_search='')").fetchall()
                for r in rows_to_index:
                    cursor.execute("UPDATE expenses SET person_name_search=? WHERE id=?", (normalize_search_text(r[1]), r[0]))
            except Exception:
                pass
            cursor.execute("CREATE TABLE IF NOT EXISTS exchange_rate_history (id INTEGER PRIMARY KEY AUTOINCREMENT, currency_code TEXT NOT NULL, rate_to_usd REAL NOT NULL, previous_rate_to_usd REAL, changed_by INTEGER, changed_at TEXT NOT NULL)")
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ('schema_version','22'))
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_blacklist'")
            if not cursor.fetchone():
                cursor.execute("CREATE TABLE token_blacklist (jti TEXT PRIMARY KEY, created_at TEXT)")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payment_reminders'")
            if not cursor.fetchone():
                cursor.execute("CREATE TABLE payment_reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, expense_id INTEGER NOT NULL, reminder_date TEXT NOT NULL, note TEXT, is_done INTEGER NOT NULL DEFAULT 0, created_at TEXT, FOREIGN KEY(expense_id) REFERENCES expenses(id) ON DELETE CASCADE)")
            cursor.execute("CREATE TABLE IF NOT EXISTS third_party_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL, payer_company_name TEXT NOT NULL, paid_to_company_name TEXT NOT NULL, amount_original REAL NOT NULL, currency_original TEXT NOT NULL, exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, amount_base REAL NOT NULL DEFAULT 0, date TEXT NOT NULL, notes TEXT, status TEXT NOT NULL DEFAULT 'approved', payer_expense_id INTEGER, paid_to_expense_id INTEGER, created_by INTEGER, created_at TEXT, reversed_at TEXT, reversal_ref TEXT, updated_by INTEGER, updated_at TEXT, edit_reason TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS service_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL, client_company_name TEXT NOT NULL, supplier_company_name TEXT NOT NULL, person_name TEXT NOT NULL, service_type TEXT NOT NULL DEFAULT 'تأشيرة سياحية', sale_amount_original REAL NOT NULL DEFAULT 0, cost_amount_original REAL NOT NULL DEFAULT 0, currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, sale_amount_base REAL NOT NULL DEFAULT 0, cost_amount_base REAL NOT NULL DEFAULT 0, date TEXT NOT NULL, notes TEXT, status TEXT NOT NULL DEFAULT 'open', client_expense_id INTEGER, supplier_expense_id INTEGER, created_by INTEGER, created_at TEXT, reversed_at TEXT, reversal_ref TEXT, print_description_client TEXT, print_description_supplier TEXT, internal_note TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS service_case_components (id INTEGER PRIMARY KEY AUTOINCREMENT, service_case_ref TEXT NOT NULL, component_index INTEGER NOT NULL DEFAULT 1, service_type TEXT NOT NULL, supplier_company_name TEXT, sale_amount_original REAL NOT NULL DEFAULT 0, cost_amount_original REAL NOT NULL DEFAULT 0, currency_original TEXT NOT NULL DEFAULT 'USD', exchange_rate_to_usd REAL NOT NULL DEFAULT 1.0, sale_amount_base REAL NOT NULL DEFAULT 0, cost_amount_base REAL NOT NULL DEFAULT 0, supplier_expense_id INTEGER, print_description_client TEXT, print_description_supplier TEXT, notes TEXT)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_reminders_date ON payment_reminders(reminder_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_source_ref ON expenses(source_ref)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_person_name_search ON expenses(person_name_search)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_operation_type ON expenses(operation_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_third_party_payments_ref ON third_party_payments(reference)")
            cursor.execute("PRAGMA table_info(third_party_payments)")
            tpp_cols = [c[1] for c in cursor.fetchall()]
            if 'updated_by' not in tpp_cols:
                cursor.execute("ALTER TABLE third_party_payments ADD COLUMN updated_by INTEGER")
            if 'updated_at' not in tpp_cols:
                cursor.execute("ALTER TABLE third_party_payments ADD COLUMN updated_at TEXT")
            if 'edit_reason' not in tpp_cols:
                cursor.execute("ALTER TABLE third_party_payments ADD COLUMN edit_reason TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_cases_ref ON service_cases(reference)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_cases_client ON service_cases(client_company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_cases_supplier ON service_cases(supplier_company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_case_components_ref ON service_case_components(service_case_ref)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_case_components_supplier ON service_case_components(supplier_company_name)")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"تحذير: تعذر تحديث قاعدة البيانات: {e}")
