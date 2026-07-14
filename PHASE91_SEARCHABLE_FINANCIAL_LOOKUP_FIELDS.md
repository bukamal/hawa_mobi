# Phase 91 — Searchable Financial Lookup Fields

- Added a reusable `SearchableLookupField` for financial dialogs.
- Company/supplier fields now search existing ledger/service company names and allow an explicit new-account text path.
- Passenger/person fields now search historical passenger/person names without creating financial accounts.
- Service type fields now search the controlled service list plus historical values.
- Applied to:
  - normal entry dialog
  - service case dialog
  - third-party payment dialog
- Added `services.lookup_service` with Arabic-normalized lookup behavior.
- Added `tools/searchable_lookup_fields_smoke_test.py` and included it in the quality gate.
