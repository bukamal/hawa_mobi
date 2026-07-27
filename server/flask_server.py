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
from services.payment_service import (
    delete_payments_for_targets,
    enrich_expenses_with_payments,
    get_payment_summary,
    insert_payment_in_transaction,
    sync_payment_state,
)
from services.batch_payment_service import (
    create_payment_batch_in_transaction,
    delete_payment_batch_in_transaction,
    get_payment_batch,
    list_outstanding_claims,
)

_SERVER_CONFIG = load_server_config()
app = Flask(__name__)
_TOKENS: Dict[str, Dict[str, Any]] = {}
_PAIRING_TOKENS: Dict[str, Dict[str, Any]] = {}

API_CONTRACT_VERSION = "2026.07.mobile-v1"
PARTIAL_PAYMENTS_CONTRACT_VERSION = "partial-payments-v1"
BATCH_PAYMENTS_CONTRACT_VERSION = "batch-payments-v1"
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
    "/api/expenses/{id}/payment-summary",
    "/api/expenses/{id}/payments",
    "/api/payments/{id}",
    "/api/payment-batches",
    "/api/payment-batches/outstanding",
    "/api/payment-batches/{id}",
    "/api/search/company-ledger",
    "/api/third_party_payments",
    "/api/third_party_payments/{reference}",
    "/api/third_party_payments/{reference}/reverse",
    "/api/service_cases",
    "/api/service_cases/{reference}",
    "/api/service_cases/{reference}/reverse",
    "/api/direct_services",
    "/api/direct_services/{reference}",
    "/api/direct_services/{reference}/reverse",
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
        "supports_mobile_pairing": True,
        "supports_payment_reminders": True,
        "supports_partial_payments": True,
        "partial_payments_contract": PARTIAL_PAYMENTS_CONTRACT_VERSION,
        "supports_dynamic_payment_balances": True,
        "supports_batch_payments": True,
        "batch_payments_contract": BATCH_PAYMENTS_CONTRACT_VERSION,
        "supports_third_party_payments": True,
        "supports_linked_intercompany_entry_editing": True,
        "supports_audit_post": True,
        "supports_expense_summary": True,
        "supports_company_deep_search": True,
        "supports_ledger_operation_core": True,
        "supports_service_cases": True,
        "supports_service_case_editing": True,
        "supports_service_case_components": True,
        "supports_direct_services": True,
        "supports_direct_service_correction": True,
        "supports_embassy_and_ground_transport_components": True,
        "supports_reconciliation_statement": True,
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
            "source_type": data.get("source_type") or ((existing or {}).get("source_type") if existing else None),
            "source_ref": data.get("source_ref") or ((existing or {}).get("source_ref") if existing else None),
            "counterparty_company_name": data.get("counterparty_company_name") or ((existing or {}).get("counterparty_company_name") if existing else None),
            "person_name": data.get("person_name") or "",
            "service_type": data.get("service_type") or "غير محدد",
            "operation_type": data.get("operation_type") or "normal",
            "is_locked": data.get("is_locked", (existing or {}).get("is_locked", 0) if existing else 0),
            "reversal_of": data.get("reversal_of") or ((existing or {}).get("reversal_of") if existing else None),
            "reversed_by": data.get("reversed_by") or ((existing or {}).get("reversed_by") if existing else None),
            "print_description": data.get("print_description") or ((existing or {}).get("print_description") if existing else None),
            "internal_note": data.get("internal_note") or ((existing or {}).get("internal_note") if existing else None),
            "service_case_role": data.get("service_case_role") or ((existing or {}).get("service_case_role") if existing else None),
            "linked_company_name": data.get("linked_company_name") or ((existing or {}).get("linked_company_name") if existing else None),
        },
        existing=existing,
    )
    from services.ledger_operation_service import normalize_expense_metadata
    normalized = normalize_expense_metadata(normalized)
    normalized["status"] = data.get("status") or ("waiting_payment" if normalized["amount_original"] == 0 else "approved")
    return normalized


def _insert_expense_with_source(conn: sqlite3.Connection, p: Dict[str, Any]) -> int:
    from services.ledger_operation_service import normalize_expense_metadata
    p = normalize_expense_metadata(p)
    cur = conn.execute(
        """INSERT INTO expenses
        (company_name, amount, amount_base, type, date, notes, currency, created_by, created_at,
         updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd,
         status, payment_due_date, payment_reminder_note, source_type, source_ref, counterparty_company_name,
         person_name, person_name_search, service_type, operation_type, is_locked, reversal_of, reversed_by, print_description, internal_note, service_case_role, linked_company_name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (p["company_name"], p["amount"], p["amount_base"], p["type"], p["date"], p.get("notes", ""), p["currency"], p.get("created_by"), p.get("created_at"),
         p.get("updated_by"), p.get("updated_at"), p["amount_original"], p["currency_original"], p["exchange_rate_to_usd"],
         p.get("status", "approved"), p.get("payment_due_date"), p.get("payment_reminder_note"), p.get("source_type"), p.get("source_ref"), p.get("counterparty_company_name"),
         p.get("person_name"), p.get("person_name_search"), p.get("service_type"), p.get("operation_type"), p.get("is_locked", 0), p.get("reversal_of"), p.get("reversed_by"), p.get("print_description"), p.get("internal_note"), p.get("service_case_role"), p.get("linked_company_name")),
    )
    return int(cur.lastrowid)



def _update_expense_with_source(conn: sqlite3.Connection, expense_id: int, p: Dict[str, Any]) -> None:
    from services.ledger_operation_service import normalize_expense_metadata
    p = normalize_expense_metadata(p)
    cur = conn.execute(
        """UPDATE expenses SET
        company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?,
        updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=?,
        status=?, payment_due_date=?, payment_reminder_note=?, source_type=?, source_ref=?, counterparty_company_name=?,
        person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?,
        print_description=?, internal_note=?, service_case_role=?, linked_company_name=?
        WHERE id=?""",
        (p["company_name"], p["amount"], p["amount_base"], p["type"], p["date"], p.get("notes", ""), p["currency"],
         p.get("updated_by"), p.get("updated_at"), p["amount_original"], p["currency_original"], p["exchange_rate_to_usd"],
         p.get("status", "approved"), p.get("payment_due_date"), p.get("payment_reminder_note"), p.get("source_type"), p.get("source_ref"), p.get("counterparty_company_name"),
         p.get("person_name"), p.get("person_name_search"), p.get("service_type"), p.get("operation_type"), p.get("is_locked", 1), p.get("reversal_of"), p.get("reversed_by"),
         p.get("print_description"), p.get("internal_note"), p.get("service_case_role"), p.get("linked_company_name"), int(expense_id)),
    )
    if cur.rowcount != 1:
        raise ValueError(f"تعذر تحديث القيد المرتبط id={expense_id}")

def _new_third_party_reference() -> str:
    return "TPP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3).upper()


def _validate_third_party_payload(data: Dict[str, Any]) -> tuple[str, str, float, str, str, str]:
    payer = str(data.get("payer_company_name") or "").strip()
    paid_to = str(data.get("paid_to_company_name") or "").strip()
    if not payer:
        raise ValueError("الشركة التي سدّدت عني مطلوبة")
    if not paid_to:
        raise ValueError("الشركة التي تم السداد لها مطلوبة")
    if payer == paid_to:
        raise ValueError("لا يمكن اختيار نفس الشركة للطرفين")
    try:
        amount = float(data.get("amount_original", data.get("amount") or 0))
    except Exception:
        raise ValueError("المبلغ غير صالح")
    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    currency_code = str(data.get("currency_original") or data.get("currency") or "USD").upper().strip()
    date = str(data.get("date") or _now()).strip()[:10]
    notes = str(data.get("notes") or "").strip()
    return payer, paid_to, amount, currency_code, date, notes

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
        return jsonify(enrich_expenses_with_payments(conn, [dict(r) for r in rows]))
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
        return jsonify(enrich_expenses_with_payments(conn, [dict(row)])[0])
    finally:
        conn.close()

@app.post("/api/expenses")
@require_roles(*_role_allows_write())
def add_expense():
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        p = _expense_payload(conn, data)
        p["is_settleable"] = int(data.get("is_settleable", 1) or 0)
        user = _current_user() or {}
        conn.execute("BEGIN IMMEDIATE")
        eid = _insert_expense_with_source(conn, p)
        conn.execute("UPDATE expenses SET is_settleable=? WHERE id=?", (p["is_settleable"], eid))
        target = dict(conn.execute("SELECT * FROM expenses WHERE id=?", (eid,)).fetchone())
        initial_paid = float(data.get("initial_paid_amount") or data.get("paid_amount") or 0)
        if initial_paid > 0:
            insert_payment_in_transaction(
                conn, target, initial_paid, date=data.get("payment_date") or p["date"],
                payment_method=data.get("payment_method") or "cash",
                reference_number=data.get("payment_reference") or "",
                notes=data.get("payment_notes") or "دفعة أولى عند إنشاء القيد",
                user_id=user.get("id") or p.get("created_by") or 1,
                username=user.get("username", ""),
            )
        else:
            sync_payment_state(conn, eid)
        if float(p.get("amount_original") or 0) <= 0.005 and p.get("payment_due_date"):
            conn.execute("UPDATE expenses SET status='waiting_payment', payment_status='not_applicable' WHERE id=?", (eid,))
            conn.execute(
                "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                (eid, str(p["payment_due_date"])[:10], p.get("payment_reminder_note") or "بانتظار تحديد المبلغ / الدفع", 0, _now()),
            )
        _audit(conn, "إضافة قيد", "expenses", eid, f"الشركة: {p['company_name']}, الإجمالي: {p['amount_original']} {p['currency_original']}, المدفوع: {initial_paid}")
        conn.commit()
        return jsonify({"ok": True, "id": eid, **get_payment_summary(conn, eid)})
    except ValueError as e:
        try: conn.rollback()
        except Exception: pass
        return _json_error(e, 400)
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return _json_error(e, 400)
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
        if ("source_type" in existing_row.keys() and existing_row["source_type"] in {"third_party_payment", "third_party_payment_reversal"}) or ("is_locked" in existing_row.keys() and int(existing_row["is_locked"] or 0)):
            return _json_error("هذا القيد مرتبط بعملية محاسبية ولا يُعدّل منفرداً. عدّل العملية الأصلية من إجراءات القيد.", 409)
        try:
            existing = dict(existing_row)
            summary_before = get_payment_summary(conn, existing)
            requested_total = float(data.get("amount_original", data.get("amount") or 0))
            if requested_total + 0.005 < float(summary_before.get("paid_amount_original") or 0):
                return _json_error("لا يمكن جعل إجمالي القيد أقل من مجموع الدفعات المسجلة", 409)
            requested_currency = str(data.get("currency_original") or data.get("currency") or existing.get("currency_original") or "USD").upper()
            if requested_currency != existing.get("currency_original") and float(summary_before.get("paid_amount_original") or 0) > 0.005:
                return _json_error("لا يمكن تغيير عملة قيد عليه دفعات. احذف الدفعات أولاً", 409)
            p = _expense_payload(conn, data, existing=existing)
        except ValueError as e:
            return _json_error(e, 400)
        cur = conn.execute(
            """UPDATE expenses SET
            company_name=?, amount=?, amount_base=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?,
            amount_original=?, currency_original=?, exchange_rate_to_usd=?, status=?, payment_due_date=?, payment_reminder_note=?,
            person_name=?, person_name_search=?, service_type=?, operation_type=?, is_locked=?, reversal_of=?, reversed_by=?, print_description=?, internal_note=?, service_case_role=?, linked_company_name=?
            WHERE id=?""",
            (p["company_name"], p["amount"], p["amount_base"], p["type"], p["date"], p["notes"], p["currency"], p["updated_by"], p["updated_at"],
             p["amount_original"], p["currency_original"], p["exchange_rate_to_usd"], p["status"], p["payment_due_date"], p["payment_reminder_note"],
             p.get("person_name"), p.get("person_name_search"), p.get("service_type"), p.get("operation_type"), p.get("is_locked", 0), p.get("reversal_of"), p.get("reversed_by"), p.get("print_description"), p.get("internal_note"), p.get("service_case_role"), p.get("linked_company_name"), expense_id),
        )
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        sync_payment_state(conn, expense_id)
        if float(p.get("amount_original") or 0) <= 0.005 and p.get("payment_due_date"):
            conn.execute("UPDATE expenses SET status='waiting_payment', payment_status='not_applicable' WHERE id=?", (expense_id,))
            conn.execute("UPDATE payment_reminders SET is_done=1 WHERE expense_id=? AND is_done=0", (expense_id,))
            conn.execute(
                "INSERT INTO payment_reminders (expense_id, reminder_date, note, is_done, created_at) VALUES (?,?,?,?,?)",
                (expense_id, str(p["payment_due_date"])[:10], p.get("payment_reminder_note") or "بانتظار تحديد المبلغ / الدفع", 0, _now()),
            )
        elif float(p.get("amount_original") or 0) > 0.005:
            conn.execute("UPDATE expenses SET status='approved' WHERE id=?", (expense_id,))
        _audit(conn, "تعديل قيد", "expenses", expense_id, f"الشركة: {p['company_name']}, المبلغ: {p['amount_original']} {p['currency_original']}")
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.delete("/api/expenses/<int:expense_id>")
@require_roles("admin", "manager", "accountant")
def delete_expense(expense_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT company_name, amount_original, currency_original, source_type, source_ref, is_locked, operation_type FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if row and (("source_type" in row.keys() and row["source_type"] in {"third_party_payment", "third_party_payment_reversal"}) or ("is_locked" in row.keys() and int(row["is_locked"] or 0))):
            return _json_error("هذا القيد مرتبط بعملية محاسبية ولا يُحذف منفرداً. احذف العملية الأصلية كاملة من إجراءات القيد.", 409)
        payment_counts = delete_payments_for_targets(conn, [expense_id])
        cur = conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        if cur.rowcount != 1:
            return _json_error(f"لم يتم العثور على القيد id={expense_id}", 404)
        conn.execute("DELETE FROM payment_reminders WHERE expense_id=?", (expense_id,))
        details = f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}, الدفعات المحذوفة: {payment_counts['payments']}" if row else ""
        _audit(conn, "حذف قيد", "expenses", expense_id, details)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.get("/api/expenses/<int:expense_id>/payment-summary")
@require_auth
def expense_payment_summary(expense_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row:
            return _json_error("لم يتم العثور على القيد", 404)
        return jsonify(get_payment_summary(conn, expense_id))
    finally:
        conn.close()


@app.get("/api/expenses/<int:expense_id>/payments")
@require_auth
def expense_payments(expense_id: int):
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM payments WHERE target_expense_id=? AND status='posted' ORDER BY date DESC, id DESC", (expense_id,)).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/api/expenses/<int:expense_id>/payments")
@require_roles(*_role_allows_write())
def add_expense_payment(expense_id: int):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row:
            conn.rollback()
            return _json_error("لم يتم العثور على القيد", 404)
        user = _current_user() or {}
        result = insert_payment_in_transaction(
            conn, dict(row), data.get("amount"), date=data.get("date") or _now()[:10],
            payment_method=data.get("payment_method") or "cash",
            reference_number=data.get("reference_number") or "", notes=data.get("notes") or "",
            user_id=user.get("id") or 1, username=user.get("username", ""),
        )
        conn.commit()
        return jsonify({"ok": True, **result})
    except ValueError as e:
        try: conn.rollback()
        except Exception: pass
        return _json_error(e, 400)
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return _json_error(e, 400)
    finally:
        conn.close()


@app.delete("/api/payments/<int:payment_id>")
@require_roles("admin", "manager", "accountant")
def delete_expense_payment(payment_id: int):
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    if not reason:
        return _json_error("سبب حذف الدفعة مطلوب", 400)
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
        if not row:
            conn.rollback()
            return _json_error("لم يتم العثور على الدفعة", 404)
        payment = dict(row)
        if payment.get("batch_id"):
            conn.rollback()
            return _json_error("هذه الدفعة جزء من دفعة مجمعة؛ احذف الدفعة المجمعة كاملةً", 409)
        if payment.get("ledger_expense_id"):
            conn.execute("DELETE FROM expenses WHERE id=?", (payment["ledger_expense_id"],))
        conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
        summary = sync_payment_state(conn, payment["target_expense_id"])
        _audit(conn, "حذف دفعة", "payments", payment_id, f"{payment.get('reference')} | السبب: {reason}")
        conn.commit()
        return jsonify({"ok": True, **summary})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return _json_error(e, 400)
    finally:
        conn.close()


@app.get("/api/payment-batches/outstanding")
@require_auth
def payment_batch_outstanding():
    conn = _connect()
    try:
        person_arg = request.args.get("person_name")
        rows = list_outstanding_claims(
            conn,
            company_name=(request.args.get("company_name") or "").strip() or None,
            person_name=(person_arg.strip() if person_arg is not None else None),
            direction=(request.args.get("direction") or "").strip() or None,
            currency_code=(request.args.get("currency_code") or "").strip() or None,
        )
        return jsonify(rows)
    finally:
        conn.close()


@app.get("/api/payment-batches")
@require_auth
def payment_batches_list():
    try:
        limit = max(1, min(int(request.args.get("limit") or 50), 200))
    except Exception:
        limit = 50
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM payment_batches WHERE status='posted' ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return jsonify([dict(row) for row in rows])
    finally:
        conn.close()


@app.get("/api/payment-batches/<batch_key>")
@require_auth
def payment_batch_get(batch_key: str):
    conn = _connect()
    try:
        try:
            value = int(batch_key) if str(batch_key).isdigit() else batch_key
            return jsonify(get_payment_batch(conn, value))
        except ValueError as exc:
            return _json_error(exc, 404)
    finally:
        conn.close()


@app.post("/api/payment-batches")
@require_roles(*_role_allows_write())
def payment_batch_add():
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        user = _current_user() or {}
        result = create_payment_batch_in_transaction(
            conn,
            company_name=data.get("company_name"),
            person_name=data.get("person_name") or "",
            direction=data.get("direction"),
            amount=data.get("amount"),
            currency_code=data.get("currency_original") or data.get("currency") or "USD",
            date=data.get("date") or _now()[:10],
            payment_method=data.get("payment_method") or "cash",
            reference_number=data.get("reference_number") or "",
            notes=data.get("notes") or "",
            allocation_mode=data.get("allocation_mode") or "oldest",
            allocations=data.get("allocations") or [],
            user_id=user.get("id") or 1,
            username=user.get("username", ""),
        )
        conn.commit()
        return jsonify(result)
    except ValueError as exc:
        try: conn.rollback()
        except Exception: pass
        return _json_error(exc, 400)
    except Exception as exc:
        try: conn.rollback()
        except Exception: pass
        return _json_error(exc, 400)
    finally:
        conn.close()


@app.delete("/api/payment-batches/<int:batch_id>")
@require_roles("admin", "manager", "accountant")
def payment_batch_delete(batch_id: int):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        user = _current_user() or {}
        result = delete_payment_batch_in_transaction(
            conn,
            batch_id,
            reason=data.get("reason") or "",
            user_id=user.get("id") or 1,
            username=user.get("username", ""),
        )
        conn.commit()
        return jsonify(result)
    except ValueError as exc:
        try: conn.rollback()
        except Exception: pass
        return _json_error(exc, 409)
    except Exception as exc:
        try: conn.rollback()
        except Exception: pass
        return _json_error(exc, 400)
    finally:
        conn.close()


@app.get("/api/expenses/summary")
@require_auth
def expense_summary():
    conn = _connect()
    try:
        raw_rows = [dict(r) for r in conn.execute("SELECT * FROM expenses").fetchall()]
        from services.ledger_operation_service import filter_operational_expenses
        rows = filter_operational_expenses(raw_rows)
        approved = [r for r in rows if r.get("status") != "waiting_payment"]
        total_in = sum(float(r.get("amount_base", r.get("amount", 0)) or 0) for r in approved if r.get("type") == "incoming")
        total_out = sum(float(r.get("amount_base", r.get("amount", 0)) or 0) for r in approved if r.get("type") == "outgoing")
        return jsonify({"total_incoming": total_in, "total_outgoing": total_out, "net": total_in - total_out, "companies_count": len({r.get('company_name') for r in rows if r.get('company_name')})})
    finally:
        conn.close()






@app.get("/api/search/company-ledger")
@require_auth
def search_company_ledger():
    query = (request.args.get("q") or "").strip()
    try:
        limit = min(max(int(request.args.get("limit") or 100), 1), 300)
    except Exception:
        limit = 100
    if not query:
        return jsonify([])
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT
                e.*,
                u.username AS created_username,
                u.full_name AS created_full_name
            FROM expenses e
            LEFT JOIN users u ON u.id = e.created_by
            ORDER BY e.date DESC, e.id DESC
        """).fetchall()
        from services.company_search_service import search_expense_rows
        from services.ledger_operation_service import filter_operational_expenses
        operational_rows = filter_operational_expenses([dict(r) for r in rows])
        return jsonify(search_expense_rows(operational_rows, query, limit=limit))
    finally:
        conn.close()


@app.post("/api/third_party_payments")
@require_roles(*_role_allows_write())
def add_third_party_payment():
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        try:
            payer, paid_to, amount, currency_code, date, notes = _validate_third_party_payload(data)
        except ValueError as e:
            return _json_error(e, 400)
        reference = _new_third_party_reference()
        user = _current_user() or {}
        uid = user.get("id") or data.get("created_by") or 1
        paid_to_payload = _expense_payload(conn, {
            "company_name": paid_to,
            "amount": amount,
            "type": "incoming",
            "date": date,
            "notes": f"سداد بالنيابة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {notes}".strip(),
            "currency": currency_code,
            "created_by": uid,
            "updated_by": uid,
        })
        paid_to_payload.update({"source_type": "third_party_payment", "source_ref": reference, "counterparty_company_name": payer})
        payer_payload = _expense_payload(conn, {
            "company_name": payer,
            "amount": amount,
            "type": "outgoing",
            "date": date,
            "notes": f"ذمة مستحقة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {notes}".strip(),
            "currency": currency_code,
            "created_by": uid,
            "updated_by": uid,
        })
        payer_payload.update({"source_type": "third_party_payment", "source_ref": reference, "counterparty_company_name": paid_to})
        conn.execute("BEGIN IMMEDIATE")
        paid_to_expense_id = _insert_expense_with_source(conn, paid_to_payload)
        payer_expense_id = _insert_expense_with_source(conn, payer_payload)
        conn.execute(
            """INSERT INTO third_party_payments
            (reference, payer_company_name, paid_to_company_name, amount_original, currency_original,
             exchange_rate_to_usd, amount_base, date, notes, status, payer_expense_id, paid_to_expense_id,
             created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (reference, payer, paid_to, amount, currency_code, paid_to_payload["exchange_rate_to_usd"], paid_to_payload["amount_base"], date, notes,
             "approved", payer_expense_id, paid_to_expense_id, uid, _now()),
        )
        _audit(conn, "سداد بالنيابة", "third_party_payments", None, f"{payer} سدّد عني إلى {paid_to}: {amount} {currency_code} | {reference}")
        conn.commit()
        return jsonify({"ok": True, "reference": reference, "payer_expense_id": payer_expense_id, "paid_to_expense_id": paid_to_expense_id, "amount_base": paid_to_payload["amount_base"], "exchange_rate_to_usd": paid_to_payload["exchange_rate_to_usd"]})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return _json_error(e, 400)
    finally:
        conn.close()



@app.get("/api/third_party_payments/<path:reference>")
@require_auth
def get_third_party_payment(reference: str):
    reference = str(reference or "").strip()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM third_party_payments WHERE reference=?", (reference,)).fetchone()
        if not row:
            return _json_error("لم يتم العثور على عملية السداد بالنيابة", 404)
        out = dict(row)
        rows = conn.execute("SELECT * FROM expenses WHERE source_ref=? AND source_type='third_party_payment' ORDER BY id", (reference,)).fetchall()
        out["entries"] = [dict(r) for r in rows]
        return jsonify(out)
    finally:
        conn.close()


@app.put("/api/third_party_payments/<path:reference>")
@require_roles(*_role_allows_write())
def update_third_party_payment(reference: str):
    reference = str(reference or "").strip()
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM third_party_payments WHERE reference=?", (reference,)).fetchone()
        if not row:
            return _json_error("لم يتم العثور على عملية السداد بالنيابة", 404)
        payment = dict(row)
        if payment.get("status") == "reversed":
            return _json_error("لا يمكن تعديل عملية معكوسة. أنشئ عملية جديدة بدلاً منها.", 409)
        try:
            payer, paid_to, amount, currency_code, date, notes = _validate_third_party_payload(data)
        except ValueError as e:
            return _json_error(e, 400)
        reason = str(data.get("edit_reason") or "").strip()
        if not reason:
            return _json_error("سبب تعديل العملية مطلوب", 400)
        payer_row = conn.execute("SELECT * FROM expenses WHERE id=?", (payment.get("payer_expense_id"),)).fetchone() if payment.get("payer_expense_id") else None
        paid_to_row = conn.execute("SELECT * FROM expenses WHERE id=?", (payment.get("paid_to_expense_id"),)).fetchone() if payment.get("paid_to_expense_id") else None
        if not payer_row or not paid_to_row:
            rows = conn.execute("SELECT * FROM expenses WHERE source_ref=? AND source_type='third_party_payment' ORDER BY id", (reference,)).fetchall()
            for r in rows:
                if r["type"] == "outgoing" and not payer_row:
                    payer_row = r
                elif r["type"] == "incoming" and not paid_to_row:
                    paid_to_row = r
        if not payer_row or not paid_to_row:
            return _json_error("تعذر العثور على القيدين المرتبطين بعملية سدد عني", 409)
        payer_entry = dict(payer_row)
        paid_to_entry = dict(paid_to_row)
        if payer_entry.get("source_ref") != reference or paid_to_entry.get("source_ref") != reference:
            return _json_error("ترابط القيود غير مطابق للمرجع", 409)
        if payer_entry.get("source_type") != "third_party_payment" or paid_to_entry.get("source_type") != "third_party_payment":
            return _json_error("لا يمكن تعديل عملية غير أصلية أو معكوسة", 409)
        if payer_entry.get("type") != "outgoing" or paid_to_entry.get("type") != "incoming":
            return _json_error("اتجاهات قيود سدد عني غير متوازنة", 409)
        user = _current_user() or {}
        uid = user.get("id") or data.get("updated_by") or 1
        now = _now()
        paid_to_payload = _expense_payload(conn, {
            "company_name": paid_to,
            "amount": amount,
            "type": "incoming",
            "date": date,
            "notes": f"سداد بالنيابة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {notes}".strip(),
            "currency": currency_code,
            "created_by": paid_to_entry.get("created_by"),
            "created_at": paid_to_entry.get("created_at"),
            "updated_by": uid,
            "updated_at": now,
            "source_type": "third_party_payment",
            "source_ref": reference,
            "counterparty_company_name": payer,
            "service_type": "سداد بالنيابة",
            "operation_type": "third_party_payment",
            "is_locked": 1,
        }, existing=paid_to_entry)
        payer_payload = _expense_payload(conn, {
            "company_name": payer,
            "amount": amount,
            "type": "outgoing",
            "date": date,
            "notes": f"ذمة مستحقة: {payer} سدّد عني إلى {paid_to}. المرجع {reference}. {notes}".strip(),
            "currency": currency_code,
            "created_by": payer_entry.get("created_by"),
            "created_at": payer_entry.get("created_at"),
            "updated_by": uid,
            "updated_at": now,
            "source_type": "third_party_payment",
            "source_ref": reference,
            "counterparty_company_name": paid_to,
            "service_type": "سداد بالنيابة",
            "operation_type": "third_party_payment",
            "is_locked": 1,
        }, existing=payer_entry)
        conn.execute("BEGIN IMMEDIATE")
        _update_expense_with_source(conn, int(paid_to_entry["id"]), paid_to_payload)
        _update_expense_with_source(conn, int(payer_entry["id"]), payer_payload)
        conn.execute(
            """UPDATE third_party_payments SET payer_company_name=?, paid_to_company_name=?, amount_original=?, currency_original=?,
               exchange_rate_to_usd=?, amount_base=?, date=?, notes=?, updated_by=?, updated_at=?, edit_reason=? WHERE reference=?""",
            (payer, paid_to, amount, currency_code, paid_to_payload["exchange_rate_to_usd"], paid_to_payload["amount_base"], date, notes, uid, now, reason, reference),
        )
        details = f"{reference} | السبب: {reason} | قبل: {payment.get('payer_company_name')} -> {payment.get('paid_to_company_name')} {payment.get('amount_original')} {payment.get('currency_original')} بتاريخ {payment.get('date')} | بعد: {payer} -> {paid_to} {amount} {currency_code} بتاريخ {date}"
        _audit(conn, "تعديل سداد بالنيابة", "third_party_payments", payment.get("id"), details)
        conn.commit()
        return jsonify({"ok": True, "reference": reference, "payer_expense_id": int(payer_entry["id"]), "paid_to_expense_id": int(paid_to_entry["id"]), "amount_base": paid_to_payload["amount_base"], "exchange_rate_to_usd": paid_to_payload["exchange_rate_to_usd"]})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return _json_error(e, 400)
    finally:
        conn.close()


@app.delete("/api/third_party_payments/<path:reference>")
@require_roles(*_role_allows_write())
def delete_third_party_payment(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.third_party_payment_repo import ThirdPartyPaymentRepository
        user = _current_user() or {}
        reason = str(data.get("reason") or "").strip()
        return jsonify(ThirdPartyPaymentRepository().delete_payment_on_behalf(
            reference, user_id=user.get("id") or 1, reason=reason
        ))
    except ValueError as e:
        status = 404 if "العثور" in str(e) else 400
        return _json_error(e, status)
    except Exception as e:
        return _json_error(e, 400)


@app.post("/api/third_party_payments/<path:reference>/reverse")
@require_roles(*_role_allows_write())
def reverse_third_party_payment(reference: str):
    reference = str(reference or "").strip()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM third_party_payments WHERE reference=?", (reference,)).fetchone()
        if not row:
            return _json_error("لم يتم العثور على عملية السداد بالنيابة", 404)
        if row["status"] == "reversed":
            return _json_error("هذه العملية معكوسة مسبقاً", 409)
        row = dict(row)
        user = _current_user() or {}
        uid = user.get("id") or 1
        date = _now()[:10]
        payer = row["payer_company_name"]
        paid_to = row["paid_to_company_name"]
        amount = float(row["amount_original"])
        currency_code = row["currency_original"]
        payer_payload = _expense_payload(conn, {"company_name": payer, "amount": amount, "type": "incoming", "date": date, "notes": f"عكس سداد بالنيابة: {reference}", "currency": currency_code, "created_by": uid, "updated_by": uid})
        payer_payload.update({"source_type": "third_party_payment_reversal", "source_ref": reference, "counterparty_company_name": paid_to})
        paid_to_payload = _expense_payload(conn, {"company_name": paid_to, "amount": amount, "type": "outgoing", "date": date, "notes": f"عكس سداد بالنيابة: {reference}", "currency": currency_code, "created_by": uid, "updated_by": uid})
        paid_to_payload.update({"source_type": "third_party_payment_reversal", "source_ref": reference, "counterparty_company_name": payer})
        conn.execute("BEGIN IMMEDIATE")
        _insert_expense_with_source(conn, payer_payload)
        _insert_expense_with_source(conn, paid_to_payload)
        reversal_ref = f"REV-{reference}"
        conn.execute("UPDATE third_party_payments SET status='reversed', reversed_at=?, reversal_ref=? WHERE reference=?", (_now(), reversal_ref, reference))
        _audit(conn, "عكس سداد بالنيابة", "third_party_payments", row.get("id"), reference)
        conn.commit()
        return jsonify({"ok": True, "reference": reference, "reversal_ref": reversal_ref})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return _json_error(e, 400)
    finally:
        conn.close()



@app.get("/api/direct_services")
@require_auth
def get_direct_services():
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        return jsonify(DirectServiceRepository().list_services())
    except Exception as e:
        return _json_error(e, 400)


@app.post("/api/direct_services")
@require_roles(*_role_allows_write())
def add_direct_service():
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        user = _current_user() or {}
        payload = dict(data)
        payload["created_by"] = user.get("id") or data.get("created_by") or 1
        return jsonify(DirectServiceRepository().add(payload))
    except Exception as e:
        return _json_error(e, 400)


@app.get("/api/direct_services/<path:reference>")
@require_auth
def get_direct_service(reference: str):
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        return jsonify(DirectServiceRepository().get_by_reference(reference))
    except ValueError as e:
        return _json_error(e, 404)
    except Exception as e:
        return _json_error(e, 400)


@app.put("/api/direct_services/<path:reference>")
@require_roles(*_role_allows_write())
def update_direct_service(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        user = _current_user() or {}
        reason = str(data.get("edit_reason") or "").strip()
        return jsonify(DirectServiceRepository().update(reference, data, edit_reason=reason, user_id=user.get("id") or data.get("updated_by") or 1))
    except ValueError as e:
        return _json_error(e, 400)
    except Exception as e:
        return _json_error(e, 400)


@app.delete("/api/direct_services/<path:reference>")
@require_roles(*_role_allows_write())
def delete_direct_service(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        user = _current_user() or {}
        reason = str(data.get("reason") or "").strip()
        return jsonify(DirectServiceRepository().delete(
            reference, user_id=user.get("id") or 1, reason=reason
        ))
    except ValueError as e:
        status = 404 if "العثور" in str(e) else 400
        return _json_error(e, status)
    except Exception as e:
        return _json_error(e, 400)


@app.post("/api/direct_services/<path:reference>/reverse")
@require_roles(*_role_allows_write())
def reverse_direct_service(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.direct_service_repo import DirectServiceRepository
        user = _current_user() or {}
        reason = str(data.get("reason") or data.get("edit_reason") or "").strip()
        date = data.get("date") or None
        return jsonify(DirectServiceRepository().reverse(reference, user_id=user.get("id") or 1, date=date, reason=reason))
    except ValueError as e:
        return _json_error(e, 400)
    except Exception as e:
        return _json_error(e, 400)

@app.get("/api/service_cases/<path:reference>")
@require_auth
def get_service_case(reference: str):
    try:
        from database.repositories.service_case_repo import ServiceCaseRepository
        return jsonify(ServiceCaseRepository().get_by_reference(reference))
    except ValueError as e:
        return _json_error(e, 404)
    except Exception as e:
        return _json_error(e, 400)


@app.put("/api/service_cases/<path:reference>")
@require_roles(*_role_allows_write())
def update_service_case(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.service_case_repo import ServiceCaseRepository
        user = _current_user() or {}
        reason = str(data.get("edit_reason") or "").strip()
        return jsonify(ServiceCaseRepository().update(reference, data, edit_reason=reason, user_id=user.get("id") or data.get("updated_by") or 1))
    except ValueError as e:
        return _json_error(e, 400)
    except Exception as e:
        return _json_error(e, 400)


@app.delete("/api/service_cases/<path:reference>")
@require_roles(*_role_allows_write())
def delete_service_case(reference: str):
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.service_case_repo import ServiceCaseRepository
        user = _current_user() or {}
        reason = str(data.get("reason") or "").strip()
        return jsonify(ServiceCaseRepository().delete(
            reference, reason=reason, user_id=user.get("id") or 1
        ))
    except ValueError as e:
        status = 404 if "العثور" in str(e) else 400
        return _json_error(e, status)
    except Exception as e:
        return _json_error(e, 400)


@app.get("/api/service_cases")
@require_auth
def get_service_cases():
    try:
        from database.repositories.service_case_repo import ServiceCaseRepository
        return jsonify(ServiceCaseRepository().list_cases())
    except Exception as e:
        return _json_error(e, 400)

@app.post("/api/service_cases")
@require_roles(*_role_allows_write())
def add_service_case():
    data = request.get_json(silent=True) or {}
    try:
        from database.repositories.service_case_repo import ServiceCaseRepository
        user = _current_user() or {}
        payload = dict(data)
        payload["created_by"] = user.get("id") or data.get("created_by") or 1
        return jsonify(ServiceCaseRepository().add(payload))
    except ValueError as e:
        return _json_error(e, 400)
    except Exception as e:
        return _json_error(e, 400)

@app.post("/api/service_cases/<path:reference>/reverse")
@require_roles(*_role_allows_write())
def reverse_service_case(reference: str):
    from services.service_case_service import SERVICE_CASE_REVERSAL, SERVICE_CASE_OPERATION_REVERSAL, SERVICE_CASE_STATUS_REVERSED
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or data.get("edit_reason") or "").strip()
    if not reason:
        return _json_error("سبب عكس ملف الخدمة مطلوب", 400)
    reference = str(reference or "").strip()
    conn = _connect()
    try:
        # Serialize the complete read-check-insert-update sequence.  Starting
        # the write transaction before reading prevents two devices from
        # reversing the same service case concurrently.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM service_cases WHERE reference=?", (reference,)).fetchone()
        if not row:
            return _json_error("لم يتم العثور على ملف الخدمة", 404)
        row = dict(row)
        if row.get("status") == SERVICE_CASE_STATUS_REVERSED:
            return _json_error("ملف الخدمة معكوس مسبقاً", 409)
        components = [dict(r) for r in conn.execute(
            "SELECT * FROM service_case_components WHERE service_case_ref=? ORDER BY component_index",
            (reference,),
        ).fetchall()]
        if not components:
            components = [{
                "service_type": row.get("service_type"),
                "supplier_company_name": row.get("supplier_company_name"),
                "cost_amount_original": row.get("cost_amount_original"),
                "print_description_supplier": row.get("print_description_supplier"),
            }]
        user = _current_user() or {}
        uid = user.get("id") or 1
        date = _now()[:10]
        now = _now()
        client_rev = _expense_payload(conn, {
            "company_name": row["client_company_name"], "amount": row["sale_amount_original"], "type": "outgoing", "date": date,
            "notes": f"عكس ملف خدمة {reference}. السبب: {reason}", "currency": row["currency_original"], "created_by": uid, "updated_by": uid,
            "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["supplier_company_name"],
            "person_name": row["person_name"], "service_type": row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
            "is_locked": 1, "print_description": f"عكس {row.get('print_description_client') or row.get('service_type')}",
            "service_case_role": "client_reversal", "linked_company_name": row["supplier_company_name"], "internal_note": f"عكس ملف خدمة {reference}: {reason}",
        })
        supplier_reversals = []
        for component in components:
            supplier_name = str(component.get("supplier_company_name") or "").strip()
            cost = float(component.get("cost_amount_original") or 0)
            if not supplier_name or cost <= 0:
                continue
            supplier_reversals.append(_expense_payload(conn, {
                "company_name": supplier_name, "amount": cost, "type": "incoming", "date": date,
                "notes": f"عكس ملف خدمة {reference}. السبب: {reason}", "currency": row["currency_original"], "created_by": uid, "updated_by": uid,
                "source_type": SERVICE_CASE_REVERSAL, "source_ref": reference, "counterparty_company_name": row["client_company_name"],
                "person_name": row["person_name"], "service_type": component.get("service_type") or row["service_type"], "operation_type": SERVICE_CASE_OPERATION_REVERSAL,
                "is_locked": 1, "print_description": f"عكس {component.get('print_description_supplier') or component.get('service_type') or row.get('service_type')}",
                "service_case_role": "supplier_reversal", "linked_company_name": row["client_company_name"], "internal_note": f"عكس ملف خدمة {reference}: {reason}",
            }))
        client_reversal_id = _insert_expense_with_source(conn, client_rev)
        supplier_reversal_ids = [_insert_expense_with_source(conn, payload) for payload in supplier_reversals]
        reversal_ref = f"REV-{reference}"
        changed = conn.execute(
            "UPDATE service_cases SET status=?, reversed_at=?, reversal_ref=? WHERE reference=? AND status<>?",
            (SERVICE_CASE_STATUS_REVERSED, now, reversal_ref, reference, SERVICE_CASE_STATUS_REVERSED),
        )
        if changed.rowcount != 1:
            raise ValueError("تعذر عكس ملف الخدمة؛ ربما عُكس من جهاز آخر")
        _audit(
            conn,
            "عكس ملف خدمة",
            "service_cases",
            row.get("id"),
            f"{reference} | السبب: {reason} | قيود العكس: {client_reversal_id}/" + ",".join(str(x) for x in supplier_reversal_ids),
        )
        conn.commit()
        return jsonify({
            "ok": True,
            "reference": reference,
            "reversal_ref": reversal_ref,
            "client_reversal_expense_id": client_reversal_id,
            "supplier_reversal_expense_ids": supplier_reversal_ids,
        })
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return _json_error(e, 400)
    finally:
        conn.close()

@app.get("/api/payment_reminders")
@require_auth
def payment_reminders():
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT r.*, e.company_name, e.amount_original, e.currency_original, e.type, e.person_name,
                      COALESCE(SUM(p.amount_original),0) AS paid_amount_original,
                      MAX(e.amount_original - COALESCE(SUM(p.amount_original),0),0) AS remaining_amount_original
               FROM payment_reminders r
               JOIN expenses e ON e.id = r.expense_id
               LEFT JOIN payments p ON p.target_expense_id=e.id AND p.status='posted'
               WHERE r.is_done=0 AND (e.is_settleable=1 OR e.status='waiting_payment')
               GROUP BY r.id
               HAVING remaining_amount_original > 0.005 OR e.status='waiting_payment'
               ORDER BY r.reminder_date ASC, r.id DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/api/payment_reminders/count_waiting")
@require_auth
def count_waiting_payment():
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM expenses e
               WHERE (e.is_settleable=1 AND e.amount_original >
               COALESCE((SELECT SUM(p.amount_original) FROM payments p WHERE p.target_expense_id=e.id AND p.status='posted'),0) + 0.005)
               OR e.status='waiting_payment'"""
        ).fetchone()
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
