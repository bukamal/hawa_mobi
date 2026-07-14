# Phase 87 — Reconciliation Note Restored

استرجاع ملاحظة كشف المطابقة التي أزيلت في Phase 86:

> لنا = مبالغ مستحقة لنا على الحساب. له = مبالغ مستحقة للحساب علينا أو مدفوعة منه. هذا الكشف مخصص للمطابقة ولا يُعد مخالصة نهائية إلا بعد التأكيد.

## التغييرات

- إعادة إظهار الملاحظة داخل كشف المطابقة.
- إعادة خيار: إظهار ملاحظة المطابقة داخل إعدادات التقارير والطباعة.
- جعل الخيار مفعلاً افتراضيًا.
- تحديث اختبارات التقارير حتى تتحقق من وجود الملاحظة بدل غيابها.

## فحوص مرحلة الإصلاح

- compileall
- reconciliation_statement_note_restored_smoke_test
- professional_statement_layout_smoke_test
- report_action_share_print_whatsapp_smoke_test
- reporting_center_core_smoke_test
- reporting_center_advanced_smoke_test
- local_crud_smoke_test
- sqlite_closed_connection_recovery_smoke_test
- hawa_visual_identity_smoke_test
- apk_release_preflight
