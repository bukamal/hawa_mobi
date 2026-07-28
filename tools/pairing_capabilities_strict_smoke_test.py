#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensure Android refuses partially-compatible servers during QR pairing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / 'services' / 'pairing_service.py').read_text(encoding='utf-8')
    for required in [
        'supports_amount_base',
        'supports_exchange_rate_history',
        'supports_expense_summary',
        'supports_payment_reminders',
        'supports_batch_payments',
        'supports_payment_payer_tracking',
        'supports_audit_post',
        '/api/expenses/summary',
        '/api/payment_reminders',
        '/api/payment_reminders/count_waiting',
        '/api/payment-batches',
        '/api/payment-batches/outstanding',
    ]:
        if required not in source:
            print(f'❌ Missing strict pairing capability check: {required}')
            return 1
    print('✅ pairing_capabilities_strict_smoke_test passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
