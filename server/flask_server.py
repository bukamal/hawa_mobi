#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone REST server for Hawaa Accounting network mode.

This module is intentionally isolated under server/ and must not be imported by
main.py or by the Android/APK client. It uses the local SQLite database on the
machine where the server runs.
"""
from __future__ import annotations

import datetime
import json
import os
import secrets
import sqlite3
from functools import wraps
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Must be set before importing database.connection so the server never switches
# itself into REST client mode because of persisted client settings.
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from flask import Flask, jsonify, request

from auth.password import hash_password, verify_password
from database.connection import get_local_db_path
from database.migrations import ensure_db
from server.config import load_server_config
from services.currency_ledger_service import CurrencyLedgerService

_SERVER_CONFIG = load_server_config()
app = Flask(__name__)
_TOKENS: Dict[str, Dict[str, Any]] = {}
_PAIRING_TOKENS: Dict[str, Dict[str, Any]] = {}

API_CONTRACT_VERSION = "2026.07.mobile-v1"
CURRENCY_CONTRACT_VERSION = "historic-currency-snapshot-v1"
REQUIRED_MOBILE_ENDPOINTS = [
    "/api/health",
    "/api/capabilities",
    "/api/login",
    "/api/logout",
    "/api/server_info",
    "/api/expenses",
    "/api/expenses/{id}",
    "/api/expenses/summary",
    "/api/payment_reminders",
    "/api/payment_reminders/count_waiting",
    "/api/users",
    "/api/users/{id}",
    "/api/users/change_password",
    "/api/audit_log",
    "/api/audit_log/old",
    "/api/settings",
    "/api/settings/{key}",
    "/api/exchange_rates",
    "/api/exchange_rate_history",
    "/api/exchange_rates/{currency_code}",
    "/api/mobile/pairing-token",
    "/api/mobile/pair",
]


def _capabilities_payload() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "hawaa-server",
        "api_contract_version": API_CONTRACT_VERSION,
        "currency_contract": CURRENCY_CONTRACT_VERSION,
        "base_currency": "USD",
        "supports_historic_currency_snapshot": True,
        "supports_amount_base": True,
        "supports_exchange_rate_history": True,
        "auth_required": True,
        "token_type": "Bearer",
        "endpoints": REQUIRED_MOBILE_ENDPOINTS,
    }


PAIRING_CONTRACT_VERSION = "hawaa-mobile-pairing-v1"
PAIRING_TOKEN_TTL_SECONDS = 300


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso_utc(dt: datetime.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _public_server_url() -> str:
    data = request.get_json(silent=True) or {}
    explicit = str(data.get("server_url") or data.get("public_url") or "").strip().rstrip("/")
    if explicit:
        return explicit
    # request.host_url may be http://127.0.0.1:8000/ on local browsers; the
    # Windows UI should pass its LAN URL when generating QR.  This fallback keeps
    # tests/dev server usable and the Android client still rejects localhost.
    return request.host_url.rstrip("/")


def _purge_pairing_tokens() -> None:
    now = _utc_now()
    expired = [token for token, payload in _PAIRING_TOKENS.items() if payload.get("expires_at") <= now or payload.get("used")]
    for token in expired:
        _PAIRING_TOKENS.pop(token, None)


def _pairing_payload(token: str, server_url: str, expires_at: datetime.datetime) -> Dict[str, Any]:
    payload = _capabilities_payload()
    payload.update({
        "app": "hawaa-sham",
        "kind": "mobile_pairing",
        "pairing_contract": PAIRING_CONTRACT_VERSION,
        "pairing_token": token,
        "server_url": server_url,
        "server_name": "هوى الشام - خادم ويندوز",
        "expires_at": _iso_utc(expires_at),
        "ttl_seconds": max(0, int((expires_at - _utc_now()).total_seconds())),
    })
    return payload


def _parse_iso_utc(value: str) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _validate_lan_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and host not in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    except Exception:
        return False


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _connect() -> sqlite3.Connection:
    ensure_db()
    conn = sqlite3.connect(get_local_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _rowdict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def _json_error(message: Any, status: int = 400):
    return jsonify({"ok": False, "error": str(message)}), status


def _purge_expired_tokens() -> None:
    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=_SERVER_CONFIG.token_ttl_minutes)
    expired = [token for token, payload in _TOKENS.items() if payload.get("issued_at") < cutoff]
    for token in expired:
        _TOKENS.pop(token, None)


def _current_user() -> Optional[Dict[str, Any]]:
    _purge_expired_tokens()
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = _TOKENS.get(auth[7:])
        return payload.get("user") if payload else None
    return None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _current_user():
            return _json_error("تسجيل الدخول مطلوب", 401)
        return fn(*args, **kwargs)
    return wrapper


def require_roles(*roles: str):
    allowed = {r.lower() for r in roles}
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return _json_error("تسجيل الدخول مطلوب", 401)
            if (user.get("role") or "").lower() not in allowed:
                return _json_error("ليست لديك صلاحية لتنفيذ هذه العملية", 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _role_allows_write() -> tuple[str, ...]:
    return ("admin", "manager", "accountant", "user")


def _get_rate_to_usd(conn: sqlite3.Connection, currency_code: str) -> float:
    code = (currency_code or "USD").upper()
    if code == "USD":
        return 1.0
    row = conn.execute("SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?", (code,)).fetchone()
    try:
        rate = float(row["rate_to_usd"] if row else 1.0)
    except Exception:
        rate = 1.0
    return rate if rate > 0 else 1.0


def _ledger_for(conn: sqlite3.Connection) -> CurrencyLedgerService:
    return CurrencyLedgerService(rate_getter=lambda code: _get_rate_to_usd(conn, code))


def _insert_rate_history(conn: sqlite3.Connection, currency_code: str, new_rate: float, previous_rate: Optional[float]) -> None:
    conn.execute(
        "INSERT INTO exchange_rate_history (currency_code, rate_to_usd, previous_rate_to_usd, changed_by, changed_at) VALUES (?,?,?,?,?)",
        ((currency_code or "USD").upper(), float(new_rate), previous_rate, (_current_user() or {}).get("id"), _now()),
    )


def _audit(conn: sqlite3.Connection, action: str, table_name: str, record_id: Optional[int], details: str):
    user = _current_user() or {}
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (user.get("id"), user.get("username", ""), action, table_name, record_id, details, request.remote_addr or "", _now()),
    )


def _expense_payload(conn: sqlite3.Connection, data: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    required = ["company_name", "amount", "type", "date", "currency"]
    missing = [k for k in required if k not in data or data.get(k) in (None, "")]
    if missing:
        raise ValueError(f"حقول ناقصة: {', '.join(missing)}")
    type_val = str(data.get("type") or "").strip()
    if type_val not in {"incoming", "outgoing"}:
        raise ValueError("نوع القيد يجب أن يكون incoming أو outgoing")
    try:
        original_amount = float(data.get("amount_original", data.get("amount") or 0))
    except Exception:
        raise ValueError("المبلغ غير صالح")
    if original_amount < 0:
        raise ValueError("المبلغ لا يمكن أن يكون سالباً")
    currency_code = str(data.get("currency_original") or data.get("currency") or "USD").upper()
    normalized = _ledger_for(conn).normalize_expense_payload(
        {
            "company_name": str(data["company_name"]).strip(),
            "amount": original_amount,
            "type": type_val,
            "date": data["date"],
            "notes": data.get("notes", ""),
            "currency": currency_code,
            "created_by": data.get("created_by", (_current_user() or {}).get("id", 1)),
            "created_at": data.get("created_at") or _now(),
            "updated_by": data.get("updated_by", (_current_user() or {}).get("id", data.get("created_by", 1))),
            "updated_at": data.get("updated_at") or _now(),
            "payment_due_date": data.get("payment_due_date"),
            "payment_reminder_note": data.get("payment_reminder_note"),
        },
        existing=existing,
    )
    normalized["status"] = data.get("status") or ("waiting_payment" if normalized["amount_original"] == 0 else "approved")
    return normalized

@app.get("/api/health")
@app.get("/health")
def health():
    ensure_db()
    payload = {
        "ok": True,
        "service": "hawaa-server",
        "server_time": _now(),
        "auth_required": True,
    }
    payload.update({
        "api_contract_version": API_CONTRACT_VERSION,
        "currency_contract": CURRENCY_CONTRACT_VERSION,
        "supports_historic_currency_snapshot": True,
    })
    if _SERVER_CONFIG.expose_database_path:
        payload["database"] = get_local_db_path()
    return jsonify(payload)


@app.get("/api/capabilities")
def capabilities():
    ensure_db()
    payload = _capabilities_payload()
    payload["server_time"] = _now()
    return jsonify(payload)


@app.post("/api/mobile/pairing-token")
@require_roles("admin", "manager")
def create_mobile_pairing_token():
    """Create a short-lived, one-time token encoded into a QR payload.

    The token only pairs the phone with this server URL; it does not log in the
    user and does not grant data access. Android must still authenticate via
    /api/login after pairing.
    """
    _purge_pairing_tokens()
    server_url = _public_server_url()
    if not _validate_lan_url(server_url):
        return _json_error("استخدم عنوان IP الشبكة المحلي للخادم، وليس localhost، قبل إنشاء QR للربط", 400)
    token = secrets.token_urlsafe(24)
    expires_at = _utc_now() + datetime.timedelta(seconds=PAIRING_TOKEN_TTL_SECONDS)
    _PAIRING_TOKENS[token] = {
        "expires_at": expires_at,
        "server_url": server_url,
        "created_by": (_current_user() or {}).get("id"),
        "created_at": _utc_now(),
        "used": False,
    }
    try:
        conn = _connect()
        try:
            _audit(conn, "create_mobile_pairing_token", "mobile_pairing", None, f"QR pairing token generated for {server_url}")
        finally:
            conn.close()
    except Exception:
        pass
    payload = _pairing_payload(token, server_url, expires_at)
    # qr_text is what the Windows UI should render as QR Code.  It is included
    # directly so the desktop UI can use any QR library without rebuilding it.
    return jsonify({"ok": True, "qr_text": json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "payload": payload})


@app.post("/api/mobile/pair")
def pair_mobile_client():
    """Validate a QR pairing token from Android.

    This endpoint is intentionally public: possession of the short-lived token
    proves that the user saw the QR in the Windows app.  It still does not return
    an auth token and does not bypass username/password login.
    """
    _purge_pairing_tokens()
    data = request.get_json(silent=True) or {}
    token = str(data.get("pairing_token") or "").strip()
    if not token:
        return _json_error("رمز الربط مطلوب", 400)
    record = _PAIRING_TOKENS.get(token)
    if not record:
        return _json_error("رمز الربط غير صالح أو انتهت صلاحيته", 401)
    if record.get("used"):
        return _json_error("تم استخدام رمز الربط مسبقاً", 401)
    if record.get("expires_at") <= _utc_now():
        _PAIRING_TOKENS.pop(token, None)
        return _json_error("انتهت صلاحية رمز الربط", 401)
    record["used"] = True
    payload = _capabilities_payload()
    payload.update({
        "ok": True,
        "paired": True,
        "server_url": record.get("server_url") or _public_server_url(),
        "server_name": "هوى الشام - خادم ويندوز",
        "pairing_contract": PAIRING_CONTRACT_VERSION,
        "message": "تم ربط الهاتف بالخادم. سجّل الدخول بحسابك للمتابعة.",
    })
    try:
        conn = _connect()
        try:
            _audit(conn, "pair_mobile_client", "mobile_pairing", None, f"Android client paired from {request.remote_addr or ''}")
        finally:
            conn.close()
    except Exception:
        pass
    return jsonify(payload)


@app.get("/api/server_info")
@require_auth
def server_info():
    ensure_db()
    payload = _capabilities_payload()
    payload.update({
        "server_time": _now(),
        "token_ttl_minutes": _SERVER_CONFIG.token_ttl_minutes,
        "authenticated": True,
    })
    return jsonify(payload)


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
        _TOKENS[token] = {"user": user, "issued_at": datetime.datetime.now()}
        conn.execute("UPDATE users SET last_login=? WHERE id=?", (_now(), row["id"]))
        return jsonify({"ok": True, "token": token, "user": user})
    finally:
        conn.close()


@app.post("/api/logout")
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _TOKENS.pop(auth[7:], None)
    return jsonify({"ok": True})


@app.get("/api/expenses")
@require_auth
def get_expenses():
    company = request.args.get("company")
    conn = _connect()
    try:
        if company:
            rows = conn.execute("SELECT * FROM expenses WHERE company_name=? ORDER BY id DESC", (company,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/api/expenses/<int:expense_id>")
@require_auth
def get_expense(expense_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        return jsonify(dict(row))
    finally:
        conn.close()


@app.post("/api/expenses")
@require_roles(*_role_allows_write())
def add_expense():
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        try:
            p = _expense_payload(conn, data)
        except ValueError as e:
            return _json_error(e, 400)
        cur = conn.execute(
            """INSERT INTO expenses
            (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
             updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
             status, payment_due_date, payment_reminder_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["company_name"], p["amount"], p["amount_base"], p["type"], p["date"], p["notes"], p["currency"], p["created_by"], p["created_at"],
             p["updated_by"], p["updated_at"], p["amount_original"], p["currency_original"], p["exchange_rate_to_usd"],
             p["status"], p["payment_due_date"], p["payment_reminder_note"]),
        )
        eid = cur.lastrowid
        if p["status"] == "waiting_payment" and p["payment_due_date"]:
            conn.execute(
                "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                (eid, p["payment_due_date"], p["payment_reminder_note"] or "بانتظار إدخال الدفعة الأولى", 0, _now()),
            )
        _audit(conn, "إضافة قيد", "expenses", eid, f"الشركة: {p['company_name']}, المبلغ: {p['amount_original']} {p['currency_original']}")
        return jsonify({"ok": True, "id": eid})
    finally:
        conn.close()


@app.put("/api/expenses/<int:expense_id>")
@require_roles(*_role_allows_write())
def update_expense(expense_id: int):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        existing_row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not existing_row:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        try:
            p = _expense_payload(conn, data, existing=dict(existing_row))
        except ValueError as e:
            return _json_error(e, 400)
        cur = conn.execute(
            """UPDATE expenses SET
            company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?,
            amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?
            WHERE id=?""",
            (p["company_name"], p["amount"], p["amount_base"], p["type"], p["date"], p["notes"], p["currency"], p["updated_by"], p["updated_at"],
             p["amount_original"], p["currency_original"], p["exchange_rate_to_usd"], p["status"], p["payment_due_date"], p["payment_reminder_note"], expense_id),
        )
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        if p["status"] == "waiting_payment" and p["payment_due_date"]:
            conn.execute("DELETE FROM payment_reminders WHERE expense_id=? AND is_done=0", (expense_id,))
            conn.execute(
                "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                (expense_id, p["payment_due_date"], p["payment_reminder_note"] or "بانتظار إدخال الدفعة الأولى", 0, _now()),
            )
        else:
            conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (expense_id,))
        _audit(conn, "تعديل قيد", "expenses", expense_id, f"الشركة: {p['company_name']}, المبلغ: {p['amount_original']} {p['currency_original']}")
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.delete("/api/expenses/<int:expense_id>")
@require_roles("admin", "manager", "accountant")
def delete_expense(expense_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT company_name, amount_original, currency_original FROM expenses WHERE id=?", (expense_id,)).fetchone()
        cur = conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        conn.execute("DELETE FROM payment_reminders WHERE expense_id=?", (expense_id,))
        details = f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}" if row else ""
        _audit(conn, "حذف قيد", "expenses", expense_id, details)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/expenses/summary")
@require_auth
def expense_summary():
    conn = _connect()
    try:
        rows = conn.execute("SELECT company_name, amount, amount_base, type, status FROM expenses").fetchall()
        approved = [r for r in rows if r["status"] != "waiting_payment"]
        total_in = sum(float((r["amount_base"] if "amount_base" in r.keys() else r["amount"]) or 0) for r in approved if r["type"] == "incoming")
        total_out = sum(float((r["amount_base"] if "amount_base" in r.keys() else r["amount"]) or 0) for r in approved if r["type"] == "outgoing")
        return jsonify({"total_incoming": total_in, "total_outgoing": total_out, "net": total_in - total_out, "companies_count": len({r['company_name'] for r in rows})})
    finally:
        conn.close()


@app.get("/api/payment_reminders")
@require_auth
def payment_reminders():
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT r.*, e.company_name, e.amount_original, e.currency_original, e.type
               FROM payment_reminders r JOIN expenses e ON e.id = r.expense_id
               WHERE r.is_done=0 ORDER BY r.reminder_date ASC, r.id DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/api/payment_reminders/count_waiting")
@require_auth
def count_waiting_payment():
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM expenses WHERE status='waiting_payment'").fetchone()
        return jsonify({"count": int(row["c"] if row else 0)})
    finally:
        conn.close()


@app.get("/api/users")
@require_auth
def get_users():
    conn = _connect()
    try:
        rows = conn.execute("SELECT id, username, full_name, role, created_at, last_login, force_password_change FROM users ORDER BY id").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/users")
@require_roles("admin")
def add_user():
    data = request.get_json(silent=True) or {}
    if not data.get("username") or not data.get("password"):
        return _json_error("اسم المستخدم وكلمة المرور مطلوبان", 400)
    pwd_hash, salt = hash_password(data["password"])
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role, created_at, force_password_change) VALUES (?,?,?,?,?,?,?)",
            (data["username"], pwd_hash, salt, data.get("full_name", ""), data.get("role", "user"), _now(), int(data.get("force_password_change", 1))),
        )
        _audit(conn, "إضافة مستخدم", "users", cur.lastrowid, f"المستخدم: {data['username']}")
        return jsonify({"ok": True, "id": cur.lastrowid})
    except sqlite3.IntegrityError as e:
        return _json_error(e, 409)
    finally:
        conn.close()


@app.put("/api/users/<int:user_id>")
@require_roles("admin")
def update_user(user_id: int):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        existing = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            return _json_error(f"لم يتم العثور على المستخدم id={user_id}", 404)
        username = data.get("username") or existing["username"]
        full_name = data.get("full_name", existing["full_name"] or "")
        role = data.get("role", existing["role"] or "user")
        force = int(data.get("force_password_change", existing["force_password_change"] or 0))
        if data.get("password"):
            pwd_hash, salt = hash_password(data["password"])
            cur = conn.execute("UPDATE users SET username=?, password_hash=?, salt=?, full_name=?, role=?, force_password_change=? WHERE id=?", (username, pwd_hash, salt, full_name, role, force, user_id))
        else:
            cur = conn.execute("UPDATE users SET username=?, full_name=?, role=?, force_password_change=? WHERE id=?", (username, full_name, role, force, user_id))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على المستخدم id={user_id}", 404)
        _audit(conn, "تعديل مستخدم", "users", user_id, f"المستخدم: {username}")
        return jsonify({"ok": True})
    except sqlite3.IntegrityError as e:
        return _json_error(e, 409)
    finally:
        conn.close()


@app.delete("/api/users/<int:user_id>")
@require_roles("admin")
def delete_user(user_id: int):
    if user_id == 1:
        return _json_error("لا يمكن حذف المستخدم الرئيسي", 400)
    conn = _connect()
    try:
        row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على المستخدم id={user_id}", 404)
        _audit(conn, "حذف مستخدم", "users", user_id, f"المستخدم: {row['username'] if row else user_id}")
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.post("/api/users/change_password")
@require_auth
def change_password():
    user = _current_user() or {}
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user.get("id"),)).fetchone()
        if not row or not verify_password(data.get("old_password", ""), row["password_hash"], row["salt"]):
            return _json_error("كلمة المرور القديمة غير صحيحة", 400)
        if not data.get("new_password"):
            return _json_error("كلمة المرور الجديدة مطلوبة", 400)
        pwd_hash, salt = hash_password(data["new_password"])
        conn.execute("UPDATE users SET password_hash=?, salt=?, force_password_change=0 WHERE id=?", (pwd_hash, salt, user.get("id")))
        _audit(conn, "تغيير كلمة المرور", "users", user.get("id"), "")
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/audit_log")
@require_auth
def get_audit_log():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/audit_log")
@require_auth
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
@require_roles("admin")
def delete_old_audit_logs():
    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 90))
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
        return jsonify({"ok": True, "deleted": cur.rowcount})
    finally:
        conn.close()


@app.get("/api/settings")
@require_auth
def get_settings_all():
    conn = _connect()
    try:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        return jsonify({r["key"]: r["value"] for r in rows})
    finally:
        conn.close()


@app.get("/api/settings/<path:key>")
@require_auth
def get_setting(key: str):
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return jsonify({"value": row["value"] if row else None})
    finally:
        conn.close()


@app.post("/api/settings/<path:key>")
@require_roles("admin")
def set_setting(key: str):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(data.get("value", ""))))
        _audit(conn, "تعديل إعداد", "settings", None, key)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/exchange_rates")
@require_auth
def get_exchange_rates():
    conn = _connect()
    try:
        rows = conn.execute("SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/api/exchange_rate_history")
@require_auth
def get_exchange_rate_history():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM exchange_rate_history ORDER BY id DESC LIMIT 200").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.put("/api/exchange_rates/<currency_code>")
@require_roles("admin", "manager")
def update_exchange_rate(currency_code: str):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        code = currency_code.upper()
        new_rate = float(data.get("rate_to_usd", 1.0) or 1.0)
        old_row = conn.execute("SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?", (code,)).fetchone()
        previous = float(old_row["rate_to_usd"]) if old_row else None
        conn.execute("INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)",
                     (code, new_rate, _now()))
        _insert_rate_history(conn, code, new_rate, previous)
        _audit(conn, "تعديل سعر صرف", "exchange_rates", None, code)
        return jsonify({"ok": True})
    finally:
        conn.close()
