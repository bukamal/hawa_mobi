# Phase 70 — Service Components, Embassy Fees, Ground Transport

Clean professional workflow for travel services.

## What changed
- Added service types:
  - سفارة / رسوم سفارة
  - نقل بري
  - متعدد الخدمات
- Service case can now contain multiple components:
  - main visa/service supplier
  - embassy/consular fees supplier
  - ground transport company
- Accounting output:
  - one locked client ledger row with total sale
  - one locked supplier ledger row per component cost
  - one unified service reference `SVC-*`
  - component details stored in `service_case_components`
- Client reconciliation statement stays clean and does not expose suppliers/profit.
- Internal service-profit report shows suppliers/components.
- API capabilities now advertise service-case components.

## Example
Client: بلو ستار
Passenger: أحمد محمد
Components:
- تأشيرة سياحية / supplier: سيف الشام / sale 150 / cost 120
- سفارة / رسوم سفارة / supplier: رسوم سفارات / sale 45 / cost 40
- نقل بري / supplier: شركة نقل الشام / sale 25 / cost 20

Client statement:
- بلو ستار: one line, total 220

Supplier ledgers:
- سيف الشام: 120
- رسوم سفارات: 40
- شركة نقل الشام: 20

Internal profit:
- sale 220
- cost 180
- profit 40
