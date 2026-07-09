# Phase 42 — Android Real FilePicker Restore

## الهدف
المستخدم طلب استيرادًا حقيقيًا من Files/Drive/Downloads، وليس استعادة من مسار داخلي داخل التطبيق فقط. السبب العملي للفشل كان أن APK مبني على Flet 0.85.2، وهو خط يسبب على بعض Android builds رسالة `Unknown control: FilePicker` عند تسجيل FilePicker في الواجهة.

## التعديل
- تثبيت `flet==0.28.3` في `pyproject.toml` كخط مستقر لـ FilePicker Android.
- تعديل `views/flet_compat.py` للسماح بمسار overlay القديم عندما يكون Flet أقل من `0.80.0`.
- إبقاء الحماية من الشاشة الحمراء عند استخدام Flet 0.80+؛ في هذه الحالة لا يتم فرض FilePicker على overlay.
- إضافة `tools/flet_filepicker_runtime_pin_smoke_test.py` لمنع بناء APK بخط Flet معروف بأنه يعطل FilePicker.
- إدخال الاختبار في `tools/quality_gate.py`.

## النتيجة المتوقعة
زر **استيراد نسخة احتياطية** يجب أن يفتح منتقي ملفات Android الحقيقي، بحيث يمكن اختيار نسخة من:

- Files
- Downloads
- Drive
- WhatsApp / Telegram بعد حفظ الملف في الجهاز

كما أن زر اختيار شعار الشركة يستخدم نفس FilePicker الحقيقي.

## ملاحظات مهمة
- هذا لا يلغي fallback الداخلي، بل يتركه كخطة احتياطية إذا فشل FilePicker.
- يجب بناء APK جديد بالكامل بعد تنظيف كاش Flet/Flutter:

```bash
rm -rf ~/.flet ~/.cache/flet build/flutter build/apk
flet build apk --verbose --clear-cache
```

- إذا بقي `Unknown control: FilePicker` بعد هذا الإصلاح، فهذا يعني أن الـ APK لم يُبنَ فعليًا من التثبيت الجديد أو أن GitHub Action يستخدم كاش قديم.
