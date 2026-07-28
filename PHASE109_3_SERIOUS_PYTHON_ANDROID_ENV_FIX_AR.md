# المرحلة 109.3 — إصلاح بيئة إعادة بناء Serious Python على Android

## العطل

بعد نجاح ترقية AndroidManifest وGradle، كانت إعادة البناء المباشرة عبر Flutter تتوقف أثناء تقييم إضافة `serious_python_android` بالرسالة:

```text
SERIOUS_PYTHON_SITE_PACKAGES environment variable is not set.
```

السبب أن أول أمر `flet build apk` يجهز حزم Python داخل `build/site-packages` ويمرر مسارها أثناء عملية Flet، لكن مرحلة إعادة البناء اليدوية اللاحقة كانت تستدعي `flutter build apk --release` دون تمرير المسار نفسه.

## الإصلاح

تم تعديل `.github/workflows/build-apk.yml` كما يلي:

1. تعريف المتغير على مستوى مهمة البناء كاملة:

```yaml
env:
  SERIOUS_PYTHON_SITE_PACKAGES: ${{ github.workspace }}/build/site-packages
```

2. التحقق قبل إعادة البناء من أن المجلد موجود فعلًا.
3. طباعة المسار والمجلدات الفرعية لأغراض التشخيص.
4. إيقاف Gradle daemon الذي قد يبقى من محاولة Flet الأولى.
5. تمرير المتغير صراحةً إلى أمر Flutter الثاني.

## اختبارات منع التراجع

أضيف الاختبار:

```text
tools/serious_python_android_rebuild_env_smoke_test.py
```

ويتحقق من:

- وجود المتغير في نطاق المهمة قبل أول بناء.
- استخدام المسار المطلق `build/site-packages`.
- فحص وجود المجلد قبل Gradle.
- إيقاف Gradle daemon القديم.
- تمرير المتغير إلى إعادة البناء المباشرة.

كما تم تعزيز `phase109_local_notifications_smoke_test.py` وإضافة الاختبار الجديد إلى `quality_gate.py`.

## التشغيل المتوقع

بعد هذا الإصلاح ينبغي أن يظهر في GitHub Actions:

```text
Using Serious Python site-packages: /home/runner/work/.../build/site-packages
```

ثم يبدأ `flutter build apk --release` دون خطأ غياب متغير البيئة.
