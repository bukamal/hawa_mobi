import os
# -*- coding: utf-8 -*-
from collections import defaultdict


def main():
    expenses = [
        {'type': 'incoming', 'amount_original': 100, 'currency_original': 'USD', 'amount': 100},
        {'type': 'outgoing', 'amount_original': 50, 'currency_original': 'USD', 'amount': 50},
        {'type': 'incoming', 'amount_original': 200, 'currency_original': 'EUR', 'amount': 220},
    ]
    totals = defaultdict(lambda: {'incoming': 0.0, 'outgoing': 0.0, 'net': 0.0})
    for e in expenses:
        curr = e['currency_original']
        val = float(e['amount_original'])
        if e['type'] == 'incoming':
            totals[curr]['incoming'] += val
            totals[curr]['net'] += val
        else:
            totals[curr]['outgoing'] += val
            totals[curr]['net'] -= val
    assert totals['USD']['net'] == 50
    assert totals['EUR']['net'] == 200
    assert set(totals.keys()) == {'USD', 'EUR'}
    print('dashboard_currency_totals_smoke_test OK')


if __name__ == '__main__':
    main()
