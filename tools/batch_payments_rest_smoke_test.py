#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase108-rest-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from database.migrations import ensure_db
ensure_db()
try:
    from server.flask_server import app
except ModuleNotFoundError as exc:
    if exc.name == "flask":
        print("PHASE108_BATCH_PAYMENTS_REST_SKIPPED: flask is not installed; static API contract passed separately")
        raise SystemExit(0)
    raise


def json_ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True))
    return response.get_json()


def main():
    client = app.test_client()
    login = json_ok(client.post('/api/login', json={'username': 'admin', 'password': 'admin123'}))
    headers = {'Authorization': f"Bearer {login['token']}"}
    caps = json_ok(client.get('/api/capabilities'))
    assert caps['supports_batch_payments'] is True
    assert '/api/payment-batches' in caps['endpoints']

    first = json_ok(client.post('/api/expenses', headers=headers, json={
        'company_name': 'REST شركة مجمعة', 'person_name': 'مسافر REST',
        'amount': 400, 'type': 'incoming', 'date': '2026-07-01', 'currency': 'USD',
        'service_type': 'قيد عادي', 'payment_due_date': '2026-07-03',
    }))
    second = json_ok(client.post('/api/expenses', headers=headers, json={
        'company_name': 'REST شركة مجمعة', 'person_name': 'مسافر REST',
        'amount': 600, 'type': 'incoming', 'date': '2026-07-02', 'currency': 'USD',
        'service_type': 'خدمة مباشرة', 'payment_due_date': '2026-07-04',
    }))

    outstanding = json_ok(client.get(
        '/api/payment-batches/outstanding?company_name=REST+شركة+مجمعة&person_name=مسافر+REST&direction=received&currency_code=USD',
        headers=headers,
    ))
    assert len(outstanding) == 2

    batch = json_ok(client.post('/api/payment-batches', headers=headers, json={
        'company_name': 'REST شركة مجمعة', 'person_name': 'مسافر REST',
        'direction': 'received', 'amount': 1200, 'currency_original': 'USD',
        'date': '2026-07-05', 'payment_method': 'bank_transfer',
        'reference_number': 'REST-BATCH-1', 'allocation_mode': 'oldest',
    }))
    assert abs(batch['allocated_amount_original'] - 1000) < 0.01
    assert abs(batch['credit_amount_original'] - 200) < 0.01
    assert len(batch['allocations']) == 2

    detail = json_ok(client.get(f"/api/payment-batches/{batch['id']}", headers=headers))
    assert detail['reference'] == batch['reference']
    assert len(detail['allocations']) == 2

    summary1 = json_ok(client.get(f"/api/expenses/{first['id']}/payment-summary", headers=headers))
    summary2 = json_ok(client.get(f"/api/expenses/{second['id']}/payment-summary", headers=headers))
    assert summary1['payment_status'] == 'paid' and summary2['payment_status'] == 'paid'

    # An allocation is deleted only through its parent batch.
    payment_id = detail['allocations'][0]['payment_id']
    blocked = client.delete(f'/api/payments/{payment_id}', headers=headers, json={'reason': 'غير مسموح'})
    assert blocked.status_code == 409, blocked.get_data(as_text=True)

    listed = json_ok(client.get('/api/payment-batches?limit=10', headers=headers))
    assert any(item['id'] == batch['id'] for item in listed)

    json_ok(client.delete(f"/api/payment-batches/{batch['id']}", headers=headers, json={'reason': 'اختبار إلغاء الحوالة'}))
    restored1 = json_ok(client.get(f"/api/expenses/{first['id']}/payment-summary", headers=headers))
    restored2 = json_ok(client.get(f"/api/expenses/{second['id']}/payment-summary", headers=headers))
    assert abs(restored1['remaining_amount_original'] - 400) < 0.01
    assert abs(restored2['remaining_amount_original'] - 600) < 0.01

    print('PHASE108_BATCH_PAYMENTS_REST_OK')
    print(f'database={DATA_DIR / "hawaa_data.db"}')


if __name__ == '__main__':
    main()
