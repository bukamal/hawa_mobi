# المرحلة 110.1 — إصلاح Backend تغليف إضافة الإشعارات

## المشكلة

فشل `tools/flet_notifications_extension_packaging_smoke_test.py` في GitHub Actions قبل بناء الـwheel برسالة:

```text
BackendUnavailable: Cannot import 'setuptools.build_meta'
```

السبب أن بيئة `actions/setup-python` لا تضمن وجود `setuptools` داخل مفسر Python، بينما الاختبار يستخدم `pip wheel --no-build-isolation` عمدًا. تثبيت المشروع بصيغة editable قد يستخدم بيئة بناء مؤقتة، ولا يجعل `setuptools.build_meta` متاحًا بالضرورة داخل مفسر الاختبار.

## الإصلاح

- تثبيت `setuptools>=65` و`wheel` صراحةً قبل تثبيت المشروع.
- التحقق المبكر من إمكانية استيراد `setuptools.build_meta`.
- الإبقاء على اختبار بناء الـwheel الفعلي داخل CI.
- جعل الاختبار المحلي على بيئة Python مصغرة يكتفي بعقد التغليف الساكن بدل طباعة traceback داخلي مبهم، مع رسالة Skip واضحة.

## الأثر

لا يوجد تغيير في قاعدة البيانات أو الواجهات أو منطق الإشعارات. التعديل يخص موثوقية بوابة الجودة ومسار CI فقط.

## تصحيحات اتساق اكتُشفت أثناء إعادة البوابة

- تحديث اختبار المرحلة 100 ليتحقق من حد أدنى للإصدار بدل فرض `1.0.50` حرفيًا.
- توحيد GitHub Actions مع `pyproject.toml`: الإصدار `1.0.55` ورقم البناء `1100`.
