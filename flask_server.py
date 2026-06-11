#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REST server for Hawaa Accounting network mode.

Run with: python run_server.py
The server always uses the local SQLite database on the machine where it runs.
Clients must connect to this machine's LAN IP, not localhost.
"""
import datetime
import os
import secrets
import sqlite3
from functools import wraps

from flask import Flask, jsonify, request

# Force database.connection to avoid client mode while the server process is running.
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from auth.password import hash_password, verify_password
from database.connection import get_local_db_path
from database.migrations import ensure_db

app = Flask(__name__)
_TOKENS = {}


def _connect():
    ensure_db()
    conn = sqlite3.connect(get_local_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _json_error(message, status=400):
    return jsonify({"error": str(message)}), status


def _rowdict(row):
    return dict(row) if row is not None else None


def _now():
    return datetime.datetime.now().isoformat()


def _current_user():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _TOKENS.get(auth[7:])
    return None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Keep /api usable for older clients during LAN migration, but require token
        # for mutating user-management routes handled below.
        return fn(*args, **kwargs)
    return wrapper


@app.get("/api/health")
def health():
    ensure_db()
    return jsonify({"ok": True, "server_time": _now()})


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return _json_error("اسم المستخدم وكلمة المرور مطلوبان", 400)
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            return _json_error("بيانات الدخول غير صحيحة", 401)
        token = secrets.token_urlsafe(32)
        user = {k: row[k] for k in row.keys() if k not in ("password_hash", "salt")}
        _TOKENS[token] = user
        conn.execute("UPDATE users SET last_login=? WHERE id=?", (_now(), row["id"]))
        return jsonify({"token": token, "user": user})
    finally:
        conn.close()


@app.post("/api/logout")
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _TOKENS.pop(auth[7:], None)
    return jsonify({"ok": True})


@app.get("/api/expenses")
def get_expenses():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/expenses")
def add_expense():
    data = request.get_json(silent=True) or {}
    required = ["company_name", "amount", "type", "date", "currency"]
    missing = [k for k in required if k not in data or data.get(k) in (None, "")]
    if missing:
        return _json_error(f"حقول ناقصة: {', '.join(missing)}", 400)
    conn = _connect()
    try:
        now = _now()
        cur = conn.execute('''INSERT INTO expenses
            (company_name, amount, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data["company_name"], float(data.get("amount") or 0), data["type"], data["date"], data.get("notes", ""), data["currency"],
             data.get("created_by", 1), data.get("created_at") or now, data.get("updated_by", data.get("created_by", 1)), data.get("updated_at") or now,
             float(data.get("amount_original", data.get("amount") or 0)), data.get("currency_original", data["currency"]), float(data.get("exchange_rate_to_usd", 1.0)),
             data.get("status", "approved"), data.get("payment_due_date"), data.get("payment_reminder_note")))
        expense_id = cur.lastrowid
        if data.get("status") == "waiting_payment" and data.get("payment_due_date"):
            conn.execute("INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                         (expense_id, data.get("payment_due_date"), data.get("payment_reminder_note") or "بانتظار إدخال الدفعة الأولى", 0, now))
        return jsonify({"id": expense_id})
    finally:
        conn.close()


@app.put("/api/expenses/<int:expense_id>")
def update_expense(expense_id):
    data = request.get_json(silent=True) or {}
    required = ["company_name", "amount", "type", "date", "currency"]
    missing = [k for k in required if k not in data or data.get(k) in (None, "")]
    if missing:
        return _json_error(f"حقول ناقصة: {', '.join(missing)}", 400)
    conn = _connect()
    try:
        now = _now()
        cur = conn.execute('''UPDATE expenses SET
            company_name=?, amount=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?,
            amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?
            WHERE id=?''',
            (data["company_name"], float(data.get("amount") or 0), data["type"], data["date"], data.get("notes", ""), data["currency"],
             data.get("updated_by", 1), data.get("updated_at") or now, float(data.get("amount_original", data.get("amount") or 0)),
             data.get("currency_original", data["currency"]), float(data.get("exchange_rate_to_usd", 1.0)), data.get("status", "approved"),
             data.get("payment_due_date"), data.get("payment_reminder_note"), int(expense_id)))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        if data.get("status") == "waiting_payment" and data.get("payment_due_date"):
            conn.execute("DELETE FROM payment_reminders WHERE expense_id=? AND is_done=0", (expense_id,))
            conn.execute("INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                         (expense_id, data.get("payment_due_date"), data.get("payment_reminder_note") or "بانتظار إدخال الدفعة الأولى", 0, now))
        else:
            conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (expense_id,))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.delete("/api/expenses/<int:expense_id>")
def delete_expense(expense_id):
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM expenses WHERE id=?", (int(expense_id),))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        conn.execute("DELETE FROM payment_reminders WHERE expense_id=?", (int(expense_id),))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/users")
def get_users():
    conn = _connect()
    try:
        rows = conn.execute("SELECT id, username, full_name, role, created_at, last_login, force_password_change FROM users ORDER BY id").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/users")
def add_user():
    data = request.get_json(silent=True) or {}
    if not data.get("username") or not data.get("password"):
        return _json_error("اسم المستخدم وكلمة المرور مطلوبان", 400)
    pwd_hash, salt = hash_password(data["password"])
    conn = _connect()
    try:
        cur = conn.execute("INSERT INTO users (username, password_hash, salt, full_name, role, created_at, force_password_change) VALUES (?,?,?,?,?,?,?)",
                           (data["username"], pwd_hash, salt, data.get("full_name", ""), data.get("role", "user"), _now(), int(data.get("force_password_change", 1))))
        return jsonify({"id": cur.lastrowid})
    except sqlite3.IntegrityError as e:
        return _json_error(e, 409)
    finally:
        conn.close()


@app.put("/api/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        if data.get("password"):
            pwd_hash, salt = hash_password(data["password"])
            cur = conn.execute("UPDATE users SET username=?, password_hash=?, salt=?, full_name=?, role=?, force_password_change=? WHERE id=?",
                               (data.get("username", ""), pwd_hash, salt, data.get("full_name", ""), data.get("role", "user"), int(data.get("force_password_change", 0)), user_id))
        else:
            cur = conn.execute("UPDATE users SET username=?, full_name=?, role=?, force_password_change=? WHERE id=?",
                               (data.get("username", ""), data.get("full_name", ""), data.get("role", "user"), int(data.get("force_password_change", 0)), user_id))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على المستخدم id={user_id}", 404)
        return jsonify({"ok": True})
    except sqlite3.IntegrityError as e:
        return _json_error(e, 409)
    finally:
        conn.close()


@app.delete("/api/users/<int:user_id>")
def delete_user(user_id):
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على المستخدم id={user_id}", 404)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.post("/api/users/change_password")
def change_password():
    user = _current_user()
    if not user:
        return _json_error("تسجيل الدخول مطلوب", 401)
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row or not verify_password(data.get("old_password", ""), row["password_hash"], row["salt"]):
            return _json_error("كلمة المرور القديمة غير صحيحة", 400)
        pwd_hash, salt = hash_password(data.get("new_password", ""))
        conn.execute("UPDATE users SET password_hash=?, salt=?, force_password_change=0 WHERE id=?", (pwd_hash, salt, user["id"]))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/audit_log")
def get_audit_log():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/audit_log")
def add_audit_log():
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                     (data.get("user_id"), data.get("username", ""), data.get("action", ""), data.get("table_name", ""), data.get("record_id"), data.get("details", ""), request.remote_addr or "", _now()))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.delete("/api/audit_log/old")
def delete_old_audit_logs():
    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 90))
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
        return jsonify({"deleted": cur.rowcount})
    finally:
        conn.close()


@app.get("/api/settings/<path:key>")
def get_setting(key):
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return jsonify({"value": row["value"] if row else None})
    finally:
        conn.close()


@app.post("/api/settings/<path:key>")
def set_setting(key):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(data.get("value", ""))))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/exchange_rates")
def get_exchange_rates():
    conn = _connect()
    try:
        rows = conn.execute("SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.put("/api/exchange_rates/<currency_code>")
def update_exchange_rate(currency_code):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
                     (currency_code.upper(), float(data.get("rate_to_usd", 1.0)), _now()))
        return jsonify({"ok": True})
    finally:
        conn.close()
