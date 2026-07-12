# Phase 67 — Service Case + Reconciliation Statement

## Core accounting model

This phase adds a professional intermediary service workflow for travel agency operations.

Example:
- Client company: بلو ستار
- Supplier company: سيف الشام
- Passenger/customer: أحمد محمد
- Service: تأشيرة سياحية
- Sale price to client: 150 USD
- Supplier cost: 120 USD

The app now creates one service-case reference, for example `SVC-20260712-145317-ABC123`, and automatically posts two locked ledger entries:

1. Client side: incoming / لنا على الشركة العميلة.
2. Supplier side: outgoing / له للشركة المورّدة.

Profit remains internal and is not exposed in the external reconciliation statement.

## Database additions

Backward-compatible columns were added to `expenses`:

- `print_description`
- `internal_note`
- `service_case_role`
- `linked_company_name`

A new `service_cases` table ties the two ledger entries together and records sale/cost/profit metadata.

Old data remains valid. Existing balances are not changed.

## Android UI

The Accounts screen now includes:

- `خدمة لعميل عبر مورد`
- `تقرير أرباح الخدمات`

Company details now include:

- `كشف مطابقة`
- WhatsApp uses the reconciliation statement layout by default.

## Print/reporting

New outputs:

- External reconciliation statement: hides internal profit and uses `print_description`.
- Internal service profit report: shows client, supplier, sale, cost, and profit.

## Protection

Service-case generated ledger entries are locked and cannot be edited or deleted individually. Use reversal workflow instead.
