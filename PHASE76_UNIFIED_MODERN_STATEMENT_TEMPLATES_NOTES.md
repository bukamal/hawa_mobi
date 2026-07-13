# Phase 76 — Unified Modern Statement Templates

- Replaced the overly-short mobile-only reconciliation output with a unified responsive statement renderer.
- Added three layout modes:
  - `full_table`: all visible columns as a complete accounting table.
  - `compact_table`: core money/date columns plus details under the statement line.
  - `cards`: mobile-friendly movement cards.
- Restored important reconciliation data by default:
  - reference
  - person/passenger
  - service/component
  - debit/credit/balance
- Added print settings for reconciliation, WhatsApp/share, and printable statement layout modes.
- Added report settings for logo/contact/summary/note/colors/reference shortening.
- Preserved RTL/LTR isolation for phone, email, money, and references.
- Updated the professional statement smoke test to protect against hidden columns.
