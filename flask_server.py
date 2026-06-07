#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, os, datetime
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import threading

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'hawaa-secret-key-change-me')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=8)
app.config['JWT_BLACKLIST_ENABLED'] = True
app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access']
jwt = JWTManager(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["500 per minute", "30 per second"], storage_uri="memory://")

def get_local_db_path():
    from database.connection import get_local_db_path as get_path
    return get_path()

DB_PATH = get_local_db_path()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db: db.close()

def verify_password(stored_hash, salt, password):
    from auth.password import verify_password as verify
    return verify(password, stored_hash, salt)

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    conn = get_db()
    row = conn.execute('SELECT 1 FROM token_blacklist WHERE jti = ?', (jti,)).fetchone()
    return row is not None

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        conn = get_db()
        user = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
        return fn(*args, **kwargs)
    return wrapper

def log_audit(action, table_name, record_id, details, request_obj):
    user_id = get_jwt_identity() if request_obj.headers.get('Authorization') else None
    username = None
    if user_id:
        conn = get_db()
        user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        username = user['username'] if user else None
    ip = request_obj.remote_addr
    now = datetime.datetime.now().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                 (user_id, username, action, table_name, record_id, details, ip, now))
    conn.commit()

# ====================== Routes ======================

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not user or not verify_password(user['password_hash'], user['salt'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    token = create_access_token(identity=str(user['id']))
    log_audit('تسجيل دخول', 'users', user['id'], f'المستخدم {username}', request)
    return jsonify({'token': token, 'user': {'id': user['id'], 'username': user['username'], 'full_name': user['full_name'], 'role': user['role']}})

@app.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    conn.execute('INSERT INTO token_blacklist (jti, created_at) VALUES (?, ?)', (jti, now))
    conn.commit()
    log_audit('تسجيل خروج', 'auth', 0, '', request)
    return jsonify({'status': 'logged out'}), 200

@app.route('/api/expenses', methods=['GET'])
@jwt_required()
def get_expenses():
    conn = get_db()
    rows = conn.execute('SELECT * FROM expenses ORDER BY id DESC').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/expenses', methods=['POST'])
@jwt_required()
def add_expense():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    cursor = conn.execute('''INSERT INTO expenses (company_name, amount, type, date, notes, currency, created_by, created_at, updated_by, updated_at, amount_original, currency_original, exchange_rate_to_usd)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                         (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
                          user_id, now, user_id, now, data.get('amount_original', data['amount']), data.get('currency_original', data['currency']), data.get('exchange_rate_to_usd',1.0)))
    conn.commit()
    new_id = cursor.lastrowid
    log_audit('إضافة قيد', 'expenses', new_id, f"الشركة: {data['company_name']}, المبلغ: {data['amount']} {data['currency']}", request)
    return jsonify({'id': new_id}), 201

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    user_id = int(get_jwt_identity())
    data = request.get_json()
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    conn.execute('''UPDATE expenses SET company_name=?, amount=?, type=?, date=?, notes=?, currency=?, updated_by=?, updated_at=?, amount_original=?, currency_original=?, exchange_rate_to_usd=? WHERE id=?''',
                 (data['company_name'], data['amount'], data['type'], data['date'], data.get('notes',''), data['currency'],
                  user_id, now, data.get('amount_original', data['amount']), data.get('currency_original', data['currency']), data.get('exchange_rate_to_usd',1.0), expense_id))
    conn.commit()
    log_audit('تعديل قيد', 'expenses', expense_id, f"الشركة: {data['company_name']}, المبلغ: {data['amount']} {data['currency']}", request)
    return jsonify({'status': 'ok'})

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    conn = get_db()
    row = conn.execute('SELECT company_name, amount_original, currency_original FROM expenses WHERE id=?', (expense_id,)).fetchone()
    details = f"الشركة: {row['company_name']}, المبلغ: {row['amount_original']} {row['currency_original']}" if row else ''
    conn.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
    conn.commit()
    log_audit('حذف قيد', 'expenses', expense_id, details, request)
    return jsonify({'status': 'ok'})

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    conn = get_db()
    rows = conn.execute('SELECT id, username, full_name, role, created_at, last_login FROM users').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/users', methods=['POST'])
@admin_required
def add_user():
    data = request.get_json()
    from auth.password import hash_password
    pwd_hash, salt = hash_password(data['password'])
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    cursor = conn.execute('INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)',
                         (data['username'], pwd_hash, salt, data.get('full_name',''), data.get('role','user'), now))
    conn.commit()
    new_id = cursor.lastrowid
    log_audit('إضافة مستخدم', 'users', new_id, f"المستخدم: {data['username']}", request)
    return jsonify({'id': new_id}), 201

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE users SET full_name=?, role=? WHERE id=?', (data.get('full_name',''), data.get('role','user'), user_id))
    conn.commit()
    log_audit('تعديل مستخدم', 'users', user_id, f"الاسم: {data.get('full_name')}, صلاحية: {data.get('role')}", request)
    return jsonify({'status': 'ok'})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == 1:
        return jsonify({'error': 'Cannot delete admin'}), 400
    conn = get_db()
    user = conn.execute('SELECT username FROM users WHERE id=?', (user_id,)).fetchone()
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    log_audit('حذف مستخدم', 'users', user_id, f"المستخدم: {user['username'] if user else ''}", request)
    return jsonify({'status': 'ok'})

@app.route('/api/users/change_password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    conn = get_db()
    user = conn.execute('SELECT password_hash, salt FROM users WHERE id=?', (user_id,)).fetchone()
    if not user or not verify_password(user['password_hash'], user['salt'], data['old_password']):
        return jsonify({'error': 'Invalid old password'}), 401
    from auth.password import hash_password
    new_hash, new_salt = hash_password(data['new_password'])
    conn.execute('UPDATE users SET password_hash=?, salt=?, force_password_change=0 WHERE id=?', (new_hash, new_salt, user_id))
    conn.commit()
    log_audit('تغيير كلمة مرور', 'users', user_id, '', request)
    return jsonify({'status': 'ok'})

@app.route('/api/audit_log', methods=['GET'])
@admin_required
def get_audit_log():
    conn = get_db()
    rows = conn.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 2000').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/audit_log/old', methods=['DELETE'])
@admin_required
def delete_old_audit_logs():
    data = request.get_json()
    days = data.get('days', 90)
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    conn = get_db()
    conn.execute('DELETE FROM audit_log WHERE timestamp < ?', (cutoff,))
    conn.commit()
    log_audit('حذف سجلات تدقيق قديمة', 'audit_log', 0, f'أقدم من {days} يوماً', request)
    return jsonify({'status': 'ok'})

@app.route('/api/settings/<key>', methods=['GET'])
@jwt_required()
def get_setting(key):
    conn = get_db()
    row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return jsonify({'value': row['value'] if row else None})

@app.route('/api/settings/<key>', methods=['POST'])
@admin_required
def set_setting(key):
    data = request.get_json()
    value = data.get('value')
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)', (key, value))
    conn.commit()
    log_audit('تعديل إعداد', 'settings', 0, f'{key} = {value}', request)
    return jsonify({'status': 'ok'})

@app.route('/api/exchange_rates', methods=['GET'])
@jwt_required()
def get_exchange_rates():
    conn = get_db()
    rows = conn.execute('SELECT currency_code, rate_to_usd, updated_at FROM exchange_rates ORDER BY currency_code').fetchall()
    return jsonify([dict(row) for row in rows])

@app.route('/api/exchange_rates/<currency_code>', methods=['PUT'])
@admin_required
def update_exchange_rate(currency_code):
    data = request.get_json()
    rate_to_usd = data.get('rate_to_usd')
    if rate_to_usd is None:
        return jsonify({'error': 'rate_to_usd required'}), 400
    now = datetime.datetime.now().isoformat()
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO exchange_rates (currency_code, rate_to_usd, updated_at) VALUES (?,?,?)',
                 (currency_code, rate_to_usd, now))
    conn.commit()
    log_audit('تحديث سعر صرف', 'exchange_rates', 0, f'{currency_code} = {rate_to_usd}', request)
    return jsonify({'status': 'ok'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'alive'})

# ====================== إدارة الخادم ======================
_server = None
_server_thread = None

def start_flask_server(port=8001):
    global _server, _server_thread
    if _server is not None:
        return False
    from werkzeug.serving import make_server
    _server = make_server('0.0.0.0', port, app, threaded=True)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    return True

def stop_flask_server():
    global _server
    if _server:
        _server.shutdown()
        _server = None
        return True
    return False

if __name__ == '__main__':
    # تشغيل مباشر كخادم مستقل
    start_flask_server(8001)
