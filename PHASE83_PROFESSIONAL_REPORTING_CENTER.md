# Phase 83 — Professional Reporting Center

- Added a unified reporting engine under `reports/reporting_center.py`.
- Added a mobile reporting center screen under `views/reports_center_mobile_view.py`.
- Added bottom navigation entry: `التقارير`.
- Added core reports:
  - تقرير أرصدة الشركات
  - تقرير أعمار الذمم
  - تقرير أرباح الفترة
  - تقرير الخدمات حسب الفترة
  - تقرير سدد عني
  - تقرير نشاط المستخدمين
- Added common filters: period, custom date range, company, currency, display mode.
- Added HTML and CSV export through the same report result object.
- Added `tools/reporting_center_core_smoke_test.py` and included it in `quality_gate.py`.

The report calculations reuse the same ledger/service/audit repositories used by the rest of the app, so balances and service profit reports remain tied to the accounting source of truth.
