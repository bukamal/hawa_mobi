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
DATA_DIR = Path(tempfile.mkdtemp(prefix="hawaa-phase107-rest-"))
os.environ["HAWAA_DATA_DIR"] = str(DATA_DIR)
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from database.migrations import ensure_db
ensure_db()
from server.flask_server import app


def json_ok(response, status=200):
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True))
    return response.get_json()


def main():
    client = app.test_client()
    login = json_ok(client.post('/api/login', json={'username': 'admin', 'password': 'admin123'}))
    headers = {'Authorization': f"Bearer {login['token']}"}

    caps = json_ok(client.get('/api/capabilities'))
    assert caps['supports_partial_payments'] is True

    added = json_ok(client.post('/api/expenses', headers=headers, json={
        'company_name': 'REST عميل', 'amount': 1000, 'type': 'incoming', 'date': '2026-07-27',
        'notes': 'REST partial', 'currency': 'USD', 'person_name': 'مسافر REST',
        'service_type': 'قيد عادي', 'initial_paid_amount': 250, 'payment_method': 'cash',
        'payment_due_date': '2026-08-10', 'payment_reminder_note': 'تذكير REST',
    }))
    eid = added['id']
    assert added['payment_status'] == 'partial'
    assert abs(added['remaining_amount_original'] - 750) < 0.01

    one = json_ok(client.get(f'/api/expenses/{eid}', headers=headers))
    assert abs(one['paid_amount_original'] - 250) < 0.01
    assert abs(one['remaining_amount_original'] - 750) < 0.01

    pay = json_ok(client.post(f'/api/expenses/{eid}/payments', headers=headers, json={
        'amount': 500, 'date': '2026-08-01', 'payment_method': 'bank_transfer', 'reference_number': 'REST-500'
    }))
    assert abs(pay['remaining_amount_original'] - 250) < 0.01
    payments = json_ok(client.get(f'/api/expenses/{eid}/payments', headers=headers))
    assert len(payments) == 2

    reminders = json_ok(client.get('/api/payment_reminders', headers=headers))
    item = next(x for x in reminders if x['expense_id'] == eid)
    assert abs(item['paid_amount_original'] - 750) < 0.01
    assert abs(item['remaining_amount_original'] - 250) < 0.01

    # Updating below paid is rejected.
    bad = client.put(f'/api/expenses/{eid}', headers=headers, json={
        'company_name': 'REST عميل', 'amount': 700, 'type': 'incoming', 'date': '2026-07-27',
        'notes': '', 'currency': 'USD'
    })
    assert bad.status_code == 409, (bad.status_code, bad.get_data(as_text=True))

    # Complete and verify reminder disappears.
    json_ok(client.post(f'/api/expenses/{eid}/payments', headers=headers, json={
        'amount': 250, 'date': '2026-08-10', 'payment_method': 'cash'
    }))
    summary = json_ok(client.get(f'/api/expenses/{eid}/payment-summary', headers=headers))
    assert summary['payment_status'] == 'paid'
    assert summary['remaining_amount_original'] == 0
    reminders = json_ok(client.get('/api/payment_reminders', headers=headers))
    assert not any(x['expense_id'] == eid for x in reminders)

    # Service case REST endpoint delegates to the same transactional model.
    case = json_ok(client.post('/api/service_cases', headers=headers, json={
        'client_company_name': 'REST شركة عميلة', 'person_name': 'REST مسافر',
        'service_type': 'فندق', 'currency_original': 'USD', 'date': '2026-07-27',
        'client_paid_amount': 1200, 'client_due_date': '2026-08-20', 'payment_method': 'card',
        'components': [
            {'service_type': 'فندق', 'supplier_company_name': 'REST مورد 1', 'sale_amount_original': 2000, 'cost_amount_original': 1400},
            {'service_type': 'نقل بري', 'supplier_company_name': 'REST مورد 2', 'sale_amount_original': 1000, 'cost_amount_original': 600},
        ]
    }))
    case_one = json_ok(client.get(f"/api/service_cases/{case['reference']}", headers=headers))
    assert abs(case_one['client_entry']['paid_amount_original'] - 1200) < 0.01
    assert abs(case_one['client_entry']['remaining_amount_original'] - 1800) < 0.01

    print('PHASE107_PARTIAL_PAYMENTS_REST_OK')
    print(f'database={DATA_DIR / "hawaa_data.db"}')


if __name__ == '__main__':
    main()
