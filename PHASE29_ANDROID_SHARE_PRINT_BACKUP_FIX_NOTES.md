# Phase 29 — Android Share / Print / Backup Export Fix

## المشكلة
من لقطات Android كانت الأزرار تعرض رسائل نجاح مثل:

- تم إنشاء النسخة الاحتياطية وفتح المشاركة
- تم إنشاء كشف الطباعة وفتحه
- تم فتح المشاركة/واتساب
- تم إنشاء CSV وفتح المشاركة

لكن نافذة المشاركة أو الطباعة لا تظهر فعليًا. السبب أن المسار القديم كان يعتمد على `file://` و/أو محاولة Android Intent عبر `pyjnius`/Kivy. هذا غير موثوق داخل Flet Android، وقد يعطي رسالة نجاح رغم أن النظام لم يفتح Share Sheet.

## الإصلاح
- تم تحويل المشاركة إلى Flet Share service الرسمي: `ft.Share` + `ft.ShareFile`.
- تم استخدام `ShareFile.from_bytes()` للملفات الصغيرة والمتوسطة لتفادي مشاكل Android scoped storage مع مسارات التطبيق الخاصة.
- لم يعد `page.launch_url(file://...)` يعتبر نجاحًا في Android.
- تم تحويل أزرار كشف الحساب/المشاركة/واتساب/CSV إلى async handlers تنتظر نتيجة المشاركة قبل إظهار رسالة الحالة.
- زر واتساب يفتح Share Sheet للملف مع تعليمات اختيار واتساب، بدل افتراض إمكانية إرفاق الملف مباشرة بمحادثة واتساب.
- تم تعديل النسخ الاحتياطي ليستخدم SQLite backup API قبل ضغط الملف، لأن قاعدة Android تعمل بـ WAL ونسخ `hawaa_data.db` وحده قد ينتج نسخة ناقصة.

## ملاحظات تشغيل Android
- الطباعة في Android لا تعني طباعة مباشرة من التطبيق. يتم إنشاء HTML ثم فتح Share Sheet؛ يختار المستخدم Chrome / Files / Print provider / Drive ثم يطبع من التطبيق المناسب.
- النسخ الاحتياطي في وضع العميل المتصل بـ Windows Server ليس بديلًا عن نسخة الخادم. النسخة الأساسية يجب أن تؤخذ من Windows Server. في الوضع المحلي، يتم إنشاء ZIP ومشاركته عبر النظام.
- WhatsApp لا يُضمن معه إرفاق مباشر لملف محدد من Flet في كل الأجهزة. المسار الآمن هو Share Sheet واختيار WhatsApp يدويًا.

## فحوصات
تم تحديث:

- `reports/share.py`
- `services/file_export_service.py`
- `views/company_details_mobile_view.py`
- `views/settings_mobile_view.py`
- `tools/apk_release_preflight.py`
- `tools/report_share_smoke_test.py`
- `tools/quality_gate.py`

والنتيجة:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/apk_release_preflight.py
PYTHONPATH=. python3 tools/report_share_smoke_test.py
PYTHONPATH=. python3 tools/apk_file_export_smoke_test.py
PYTHONPATH=. python3 tools/quality_gate.py
```

كلها نجحت.
