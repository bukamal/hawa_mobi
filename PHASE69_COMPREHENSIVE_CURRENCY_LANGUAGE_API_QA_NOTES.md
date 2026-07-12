# Phase 69 — Comprehensive Currency / Language / API QA

Added `tools/comprehensive_currency_language_api_test.py` and included it in the Android quality gate.

Coverage:

- Original stored amount and currency: `amount_original`, `currency_original`.
- Accounting base value: immutable USD `amount_base` / legacy `amount` mirror.
- Historical exchange-rate snapshot: `exchange_rate_to_usd` remains frozen after current-rate changes.
- Display currency: reports and running balances convert from base USD using the current display rate.
- Exchange-rate history: updates create `exchange_rate_history` rows.
- Service-case workflow: client/supplier rows, locked entries, profit base, reconciliation output and internal profit report.
- Company search: person/service matching across client and supplier entries.
- Languages: Arabic/English/French dictionary parity, RTL/LTR switching and label mappings.
- API contract: capabilities, routes, RestClient methods and historical-currency/service-case support.

Environment note:

- In this container, Flask is not installed, so the live Flask `test_client` branch is skipped by the comprehensive test. The static API contract branch passes. On the Windows server environment where Flask is installed, the same test executes live authenticated API calls.
