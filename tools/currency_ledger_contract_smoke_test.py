import os
# -*- coding: utf-8 -*-
"""Currency historical snapshot compatibility contract for Windows/APK."""
from services.currency_ledger_service import CurrencyLedgerService


def main():
    rates = {"USD": 1.0, "SYP": 14000.0, "EUR": 0.92}
    svc = CurrencyLedgerService(rate_getter=lambda code: rates[code])

    snap = svc.snapshot(14000, "SYP")
    assert snap["amount_original"] == 14000
    assert snap["currency_original"] == "SYP"
    assert snap["exchange_rate_to_usd"] == 14000.0
    assert snap["amount_base"] == 1.0
    assert snap["amount"] == snap["amount_base"]

    rates["SYP"] = 15000.0
    edited = svc.snapshot(28000, "SYP", existing=snap)
    assert edited["exchange_rate_to_usd"] == 14000.0, "same-currency edit must preserve historical rate"
    assert edited["amount_base"] == 2.0

    changed_currency = svc.snapshot(2, "EUR", existing=edited)
    assert changed_currency["exchange_rate_to_usd"] == 0.92, "currency change must capture a fresh snapshot"
    assert round(changed_currency["amount_base"], 6) == round(2 / 0.92, 6)

    print("currency_ledger_contract_smoke_test OK")


if __name__ == "__main__":
    main()
