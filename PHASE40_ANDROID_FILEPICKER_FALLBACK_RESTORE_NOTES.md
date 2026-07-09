# Phase 40 — Android FilePicker Fallback Restore

## الهدف
بعض نسخ Flet/Android لا تدعم تسجيل `FilePicker` كخدمة داخل APK، فتظهر رسالة أن منتقي الملفات غير مدعوم. هذه المرحلة تمنع توقف مسار الاستيراد عند هذه النقطة.

## التعديلات
- إضافة fallback لاستيراد النسخة الاحتياطية بدون FilePicker:
  - عرض آخر نسخ احتياطية أنشأها التطبيق داخل تخزينه.
  - السماح بإدخال مسار ZIP/DB يدويًا.
  - فحص النسخة قبل الاستعادة ثم عرض تأكيد الاستيراد.
- إضافة fallback لاختيار شعار الشركة بدون FilePicker:
  - إدخال مسار صورة قابل للقراءة يدويًا.
  - نسخ الصورة إلى تخزين التطبيق ثم عرض المعاينة.
- إضافة `FileExportService.find_recent_backup_archives()` و `describe_backup_file()`.

## ملاحظات
هذا لا يجبر Flet Runtime غير داعم على فتح منتقي الملفات. لكنه يوفر مسارًا عمليًا داخل التطبيق بدل الاكتفاء برسالة خطأ. عند توفر نسخة Flet تدعم FilePicker، سيبقى المسار الأصلي يعمل طبيعيًا.

## الفحص
- `python3 -m compileall -q .`
- `PYTHONPATH=. python3 tools/quality_gate.py`

النتيجة: `quality_gate passed`.
