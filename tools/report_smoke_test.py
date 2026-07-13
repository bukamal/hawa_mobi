# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from reports.account_statement import build_rows, export_account_statement_csv, export_account_statement_html
from reports.config import get_report_settings


def main() -> int:
    settings = get_report_settings()
    cols = [c for c in settings['account_statement_columns'] if c.get('visible')]
    expected = ['date', 'notes', 'debit', 'credit', 'running_balance']
    assert [c['key'] for c in cols[:5]] == expected, [c['key'] for c in cols]
    assert {'reference', 'person_name', 'service_type'} <= {c['key'] for c in cols}, [c['key'] for c in cols]
    records = [
        {'id': 1, 'company_name': 'شركة اختبار', 'date': '2026-01-01', 'notes': 'قيد لنا', 'type': 'incoming', 'amount': 100.0, 'amount_original': 100.0, 'currency_original': 'USD', 'currency': 'USD', 'exchange_rate_to_usd': 1.0, 'status': 'approved'},
        {'id': 2, 'company_name': 'شركة اختبار', 'date': '2026-01-02', 'notes': 'قيد له', 'type': 'outgoing', 'amount': 25.0, 'amount_original': 25.0, 'currency_original': 'USD', 'currency': 'USD', 'exchange_rate_to_usd': 1.0, 'status': 'approved'},
    ]
    rows, totals = build_rows(records, 'USD')
    assert rows[0]['debit'] and not rows[0]['credit']
    assert rows[1]['credit'] and not rows[1]['debit']
    assert totals['net_usd'] == 75.0
    out_dir = tempfile.mkdtemp(prefix='hawaa_report_test_')
    html_path = export_account_statement_html('شركة اختبار', records, os.path.join(out_dir, 'statement.html'))
    csv_path = export_account_statement_csv('شركة اختبار', records, os.path.join(out_dir, 'statement.csv'))
    html = Path(html_path).read_text(encoding='utf-8')
    assert 'التاريخ' in html and 'البيان' in html and 'الرصيد' in html
    assert 'القيمة التاريخية للعملة' not in html  # optional column is disabled by default
    assert Path(csv_path).exists()
    print('✅ report_smoke_test passed')
    return 0


if __name__ == '__main__':
    code = main()
    sys.stdout.flush() if 'sys' in globals() else None
    sys.stderr.flush() if 'sys' in globals() else None
    os._exit(code)
