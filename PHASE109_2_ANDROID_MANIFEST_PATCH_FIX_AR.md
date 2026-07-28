# المرحلة 109.2 — إصلاح اختيار Android Manifest في GitHub Actions

## العطل

فشل الأمر:

```bash
python tools/patch_android_local_notifications.py build/flutter
```

بالرسالة:

```text
RuntimeError: No <application> in .../android/app/src/debug/AndroidManifest.xml
```

## السبب

مشروع Flutter المولد يحتوي عادةً على عدة ملفات Manifest:

- `android/app/src/main/AndroidManifest.xml` — الملف الرئيسي ويحتوي عنصر `<application>`.
- `android/app/src/debug/AndroidManifest.xml` — ملف Overlay خاص بوضع Debug وقد لا يحتوي `<application>`.
- `android/app/src/profile/AndroidManifest.xml` — ملف Overlay خاص بوضع Profile.

أداة المرحلة 109 كانت تبحث عن أي ملف باسم `AndroidManifest.xml` ثم تختار أول مسار مرتب. وبسبب سبق كلمة `debug` لكلمة `main`، كانت تختار ملف Debug الخطأ.

## الإصلاح

تم استبدال البحث العام بدالتين صريحتين:

- `find_main_manifest()` لا تقبل إلا `app/src/main/AndroidManifest.xml`.
- `find_app_gradle()` تختار ملف Gradle الخاص بوحدة `app` فقط.

إذا لم يوجد Main Manifest، تعرض الأداة رسالة تشخيصية تتضمن جميع ملفات Manifest التي عثرت عليها، بدل تعديل ملف Overlay أو الفشل برسالة مضللة.

## اختبار منع الارتداد

أضيفت بنية اختبار تحتوي على:

```text
android/app/src/debug/AndroidManifest.xml    بلا <application>
android/app/src/profile/AndroidManifest.xml  بلا <application>
android/app/src/main/AndroidManifest.xml     يحتوي <application>
```

ويتحقق الاختبار من أن:

1. الأداة تختار ملف `src/main` تحديدًا.
2. تضيف الصلاحيات ومستقبلات الإشعارات إلى Main Manifest فقط.
3. لا تتأثر ملفات Debug وProfile.
4. تشغيل الأداة مرة ثانية لا يكرر التعديلات؛ أي أنها Idempotent.

## أثر التعديل

لا يوجد تغيير في:

- قاعدة البيانات.
- منطق الدفعات.
- واجهة التطبيق.
- جدولة الإشعارات نفسها.

الإصلاح خاص بمرحلة بناء Android بعد توليد مشروع Flutter.

## التشغيل

بعد تطبيق الإصلاح:

```bash
python tools/patch_android_local_notifications.py build/flutter
```

يجب أن يطبع مسارًا منتهيًا بـ:

```text
android/app/src/main/AndroidManifest.xml
```
