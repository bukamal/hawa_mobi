# Phase 72 — Historical Currency Detailed Statement QA Fix

Quality Gate failed because Phase 71 folded optional table columns into compact statement metadata, but the comprehensive QA test still requires the detailed account statement to print the historical currency snapshot label.

Fix:
- `reports/account_statement.py`
  - Detailed statement metadata now includes `القيمة التاريخية للعملة` when `historical_currency_value` is present.
  - The value remains folded into the البيان cell to preserve the mobile-first five-column layout.
  - Currency/amount text remains LTR-isolated and non-wrapping.

This preserves:
- compact reconciliation statement for WhatsApp/share,
- detailed statement for printing,
- historical exchange-rate audit trail.
