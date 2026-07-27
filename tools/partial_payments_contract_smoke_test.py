#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

migrations = text('database/migrations.py')
assert 'CREATE TABLE IF NOT EXISTS payments' in migrations
assert 'is_settleable INTEGER NOT NULL DEFAULT 1' in migrations
assert 'payment_status TEXT NOT NULL DEFAULT' in migrations

payment_service = text('services/payment_service.py')
for token in ('insert_payment_in_transaction', 'remaining_amount_original', 'UPDATE payment_reminders SET is_done=1'):
    assert token in payment_service

company_view = text('views/company_details_mobile_view.py')
for token in ('تسجيل دفعة', 'عرض سجل الدفعات', 'paid_amount_original', 'remaining_amount_original'):
    assert token in company_view

normal_dialog = text('views/dialogs/add_edit_expense_dialog.py')
assert 'المدفوع الآن' in normal_dialog
assert 'initial_paid_amount' in normal_dialog

service_dialog = text('views/dialogs/direct_service_dialog.py')
assert 'client_paid_amount' in service_dialog
assert 'supplier_paid_amount' in service_dialog

case_dialog = text('views/dialogs/service_case_dialog.py')
assert 'المدفوع من العميل الآن' in case_dialog
assert 'client_paid_amount' in case_dialog
assert 'client_due_date' in case_dialog

reminders_view = text('views/payment_reminders_mobile_view.py')
assert 'متابعة الدفعات' in reminders_view
assert 'تسجيل دفعة' in reminders_view
assert 'remaining_amount_original' in reminders_view

server = text('server/flask_server.py')
assert '/api/expenses/<int:expense_id>/payments' in server
assert '/api/payments/<int:payment_id>' in server
assert 'supports_partial_payments' in server
assert 'enrich_expenses_with_payments' in server

rest = text('database/connection_rest.py')
for token in ('get_payment_summary', 'add_payment', 'delete_payment'):
    assert f'def {token}' in rest

print('PHASE107_PARTIAL_PAYMENTS_CONTRACT_OK')
