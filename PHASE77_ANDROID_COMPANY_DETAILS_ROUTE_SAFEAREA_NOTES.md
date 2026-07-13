# Phase 77 — Android SafeArea + Company Details Route Fix

- Company details no longer opens as a large AlertDialog.
- Details are routed as an internal AppLayout page to prevent blank white dialog shells after close.
- Added explicit Android top safe-area spacer and defensive fullscreen-off flags.
- Monetary value tiles use LTR isolation and one-line formatting to avoid `$`/decimal wrapping.
- Added `tools/company_details_route_safearea_smoke_test.py`.
