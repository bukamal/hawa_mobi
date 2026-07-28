# المرحلة 109.4 — إصلاح تسجيل إضافة الإشعارات في APK

## العطل الظاهر

عند طلب إذن الإشعارات كان Android يعرض نافذة الإذن، لكن واجهة Flet خلفها تعرض:

```text
Unknown control: flet_notifications
```

هذا يعني أن كود Python أنشأ `LocalNotifications` وأرسله إلى واجهة Flutter، بينما تطبيق Flutter داخل APK لم يسجل المصنع المسؤول عن النوع `flet_notifications`.

## السبب الجذري المثبت

حزمة `flet-notifications` المحلية كانت تبني Wheel يحتوي فقط على:

```text
flet_notifications/__init__.py
flet_notifications/flet_notifications.py
```

لكنها لم تكن تحتوي المجلد المطلوب:

```text
flutter/flet_notifications/**
```

السبب هو أن إعداد `setuptools.packages.find.include` كان يسمح فقط بـ`flet_notifications*` ويستبعد مساحة الأسماء `flutter*`. وجود `MANIFEST.in` وحده لا يكفي عندما لا تُكتشف حزمة Flutter ضمن الحزم المضمنة في الـWheel.

## الإصلاح

1. رفع إصدار الإضافة من `0.2.0` إلى `0.2.1` لكسر Cache الحزمة القديمة.
2. تضمين `flutter*` في اكتشاف حزم Setuptools.
3. إضافة Package Data لكل ملفات Flutter:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["flet_notifications*", "flutter*"]

[tool.setuptools.package-data]
"flutter.flet_notifications" = ["**/*"]
```

4. إضافة marker لحزمة `flutter.flet_notifications` لضمان اكتشاف ثابت بين إصدارات Setuptools.
5. تحديث اعتماد التطبيق إلى `flet-notifications==0.2.1`.
6. حذف `build/flutter-packages` و`build/site-packages` قبل البناء لمنع إعادة استخدام payload قديم.
7. إضافة فحص CI بعد `flet build` وقبل Gradle يتأكد من:
   - وجود `build/flutter-packages/flet_notifications/pubspec.yaml`.
   - وجود ملفات Dart الأربعة المطلوبة.
   - وجود اعتماد `flet_notifications` في `build/flutter/pubspec.yaml`.
   - وجود import أو registration للإضافة في ملفات Dart المولدة.
8. إضافة اختبار يبني Wheel حقيقيًا دون شبكة ويفحص أن ملفات Flutter موجودة داخله.
9. رفع نسخة التطبيق إلى `1.0.54` ورقم البناء إلى `1094` لتثبيت APK الجديد كتحديث فوق النسخة الحالية.

## ملفات Flutter الموجودة الآن داخل الـWheel

```text
flutter/flet_notifications/pubspec.yaml
flutter/flet_notifications/lib/flet_notifications.dart
flutter/flet_notifications/lib/src/create_control.dart
flutter/flet_notifications/lib/src/flet_notifications.dart
```

## الخرج المتوقع في GitHub Actions

بعد خطوة Flet يجب أن يظهر ما يفيد اكتشاف الإضافة، ثم تنجح خطوة التحقق:

```text
Found Flutter extension at .../build/flutter-packages/flet_notifications
Registered Flutter user extensions

flet_notifications registration verified:
  extension_root: .../build/flutter-packages/flet_notifications
```

إذا لم تسجل الإضافة، يفشل CI قبل إنتاج APK برسالة صريحة بدل إصدار APK يعرض شاشة حمراء عند التشغيل.

## نتائج الاختبار

نجح:

- `compileall`.
- بناء Wheel محلي للإضافة دون تنزيلات.
- التحقق من وجود Flutter payload داخل الـWheel.
- اختبار fixture لتسجيل الإضافة داخل مشروع Flutter مولد.
- اختبار المرحلة 109 للإشعارات والتخطيط والإلغاء.
- `apk_release_preflight`.
- فحص متغير `SERIOUS_PYTHON_SITE_PACKAGES`.
- بوابة الجودة وصلت إلى اختبار تصميم Flet بعد نجاح اختبار التغليف الجديد والمرحلة 109 وزر الدفع. توقفت بيئة الفحص لاحقًا بسبب عدم توفر Runtime Flet المحلي، وليس بسبب هذا الإصلاح.

## التحقق على الجهاز

بعد بناء APK الجديد وتثبيته كتحديث:

1. افتح التطبيق مرة واحدة.
2. اضغط «تفعيل الإشعارات».
3. يجب ألا تظهر المساحة الحمراء أو رسالة `Unknown control`.
4. امنح إذن Android.
5. افتح «مركز التنبيهات» وشغّل «اختبار إشعار».

لا تحذف التطبيق قبل التحديث إلا بعد إنشاء نسخة احتياطية، لأن الحذف قد يزيل قاعدة البيانات المحلية.
