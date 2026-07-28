# المرحلة 109.5 — إصلاح Backend بناء إضافة الإشعارات في بوابة الجودة

## العطل

توقف `quality_gate.py` داخل GitHub Actions عند اختبار تغليف إضافة الإشعارات بالخطأ:

```text
BackendUnavailable: Cannot import 'setuptools.build_meta'
```

الاختبار كان يشغّل `pip wheel --no-build-isolation` مع `PIP_NO_INDEX=1`. هذا يفرض استخدام أدوات البناء المثبتة في بيئة Python الحالية، بينما خطوة CI كانت ترقي `pip` فقط ولم تثبّت `setuptools` و`wheel` صراحةً.

## الإصلاح

1. تثبيت أدوات البناء صراحةً قبل تثبيت المشروع:

```bash
python -m pip install --upgrade pip "setuptools>=65" wheel
```

2. فحص استيراد `setuptools.build_meta` و`wheel` في خطوة CI، مع طباعة الإصدارات.
3. تعديل اختبار التغليف ليستخدم `setuptools.build_meta.build_wheel()` مباشرة بدل إنشاء عملية `pip` داخلية تعتمد على إعدادات العزل والفهرس.
4. إبقاء الاختبار دون شبكة: يبني Wheel حقيقيًا ثم يفحص وجود ملفات Flutter/Dart داخله.
5. إضافة عقد ساكن يتأكد أن Workflow يثبت Backend البناء قبل تشغيل بوابة الجودة.
6. رفع نسخة التطبيق إلى `1.0.55` ورقم البناء إلى `1095` لتسهيل تثبيت APK الناتج كتحديث.

## النتيجة المتوقعة

يمر الاختبار:

```text
flet_notifications_extension_packaging_smoke_test passed
```

ثم تتابع بوابة الجودة إلى اختبارات الإشعارات والواجهات اللاحقة.

## إصلاح اختبارات الإصدار القديمة

بعد تجاوز اختبار الـWheel ظهرت حراسة قديمة في اختبارات المراحل 100–104 تشترط النص الحرفي `version = "1.0.50"`. هذا الشرط أصبح غير صحيح بعد الإصدارات اللاحقة. جرى استبداله بقراءة TOML والتحقق من أن النسخة لا تقل عن `1.0.50`، حتى لا تنكسر بوابة الجودة عند كل زيادة مشروعة للإصدار.

## التحقق المنفذ

نجح محليًا:

- `compileall`
- `flet_notifications_extension_packaging_smoke_test.py`
- `serious_python_android_rebuild_env_smoke_test.py`
- `phase109_local_notifications_smoke_test.py`
- `payment_reminder_button_target_smoke_test.py`
- `phase102_secure_admin_settings_smoke_test.py`
- `phase103_accounts_reports_performance_smoke_test.py`
- `phase104_navigation_recovery_accessibility_smoke_test.py`
- `apk_release_preflight.py`

بوابة الجودة تجاوزت اختبار تغليف الإضافة واختبارات المرحلة 109، ثم توقفت محليًا فقط لأن مكتبة `flet` غير مثبتة في بيئة الفحص الحالية. Workflow يثبتها عبر `pip install -e .` قبل تشغيل البوابة.
