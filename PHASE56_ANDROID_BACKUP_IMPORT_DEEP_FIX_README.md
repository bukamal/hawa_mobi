# Phase 56 — Android backup import deep fix

## السبب العملي
فتح نافذة اختيار الملف لا يعني أن Python داخل Flet/Android يستطيع قراءة الملف المختار. على Android قد يرجع FilePicker إحدى الحالات التالية:

- مسار حقيقي قابل للقراءة: يعمل مباشرة.
- `file://...`: يحتاج تحويل إلى path عادي.
- `content://...`: يظهر في Android picker لكن لا يُقرأ عبر `open()` العادي.
- اسم ملف فقط: مثل `hawaa_backup_....zip` بدون المسار.

في Phase 55 كان التطبيق يرفض `content://` أو الاسم فقط ويفتح fallback، لذلك كان يبدو للمستخدم أن الاستيراد بدأ بينما لم تُستبدل قاعدة البيانات فعليًا.

## التصحيح
تم تعديل `services/file_export_service.py`:

- `resolve_picker_file_path()` صار يحاول:
  1. قراءة المسار المباشر.
  2. تحويل `file://` إلى path.
  3. نسخ `content://` إلى cache داخلي عبر Android ContentResolver عند توفر bridge داخل APK.
  4. البحث بالاسم في:
     - `Download/Hawaa`
     - `Download`
     - تخزين التطبيق الداخلي `backups`
     - cache backups
- إضافة `describe_picker_file()` لإظهار تشخيص حقيقي عند فشل قراءة الملف.
- منع الصمت: إذا لم يكن الملف مقروءًا، تظهر نافذة بسبب واضح وتشخيص للنتيجة التي أعادها Android.

تم تعديل `views/settings_mobile_view.py`:

- إضافة زر جديد:
  `استيراد آخر نسخة محفوظة داخليًا`
- هذا الزر يستورد من النسخ التي أنشأها التطبيق وحفظها داخليًا بدون الاعتماد على Android FilePicker.
- عند اختيار ملف غير قابل للقراءة، تظهر رسالة توضح أن المشكلة من `content://` أو الاسم فقط، وتقترح استخدام الزر الداخلي أو وضع الملف داخل `Download/Hawaa`.

## لماذا هذا مهم؟
لأن Android scoped storage يمنع أحيانًا قراءة ZIP من Downloads كمسار عادي، حتى لو ظهر الملف في نافذة الاختيار. هذا ليس فشل قاعدة البيانات، بل فشل في تحويل نتيجة FilePicker إلى ملف يمكن لـ SQLite/ZIP قراءته.

## فحوص منفذة

```bash
python -m compileall -q .
PYTHONPATH=. python tools/backup_picker_resolution_smoke_test.py
PYTHONPATH=. python tools/backup_restore_smoke_test.py
PYTHONPATH=. python tools/backup_import_runtime_refresh_smoke_test.py
PYTHONPATH=. python tools/filepicker_permission_compat_smoke_test.py
PYTHONPATH=. python tools/apk_release_preflight.py
PYTHONPATH=. python tools/share_export_fallback_smoke_test.py
PYTHONPATH=. python tools/report_action_share_print_whatsapp_smoke_test.py
PYTHONPATH=. python tools/local_crud_smoke_test.py
PYTHONPATH=. python tools/third_party_payment_smoke_test.py
PYTHONPATH=. python tools/flet_dialog_route_cleanup_smoke_test.py
PYTHONPATH=. python tools/flet_snackbar_no_overlay_route_smoke_test.py
```

`quality_gate.py` الكامل وصل إلى `apk_release_preflight` في هذه البيئة ثم علق بسبب stdout/subprocess inheritance، بينما `apk_release_preflight.py` نفسه نجح منفردًا.

## اختبار APK المطلوب

1. ابنِ APK من Phase 56.
2. احذف التطبيق القديم من الهاتف.
3. ثبّت APK الجديد.
4. أنشئ قيدًا تجريبيًا.
5. أنشئ نسخة احتياطية.
6. غيّر/احذف القيد.
7. جرّب أولًا: `استيراد آخر نسخة محفوظة داخليًا`.
8. بعدها جرّب اختيار ملف ZIP من Download/Hawaa.
9. يجب أن تظهر نافذة نجاح فيها أعداد الجداول، ثم تظهر البيانات داخل حسابات الشركات.
