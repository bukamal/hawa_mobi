# Phase 43 — Android Real Import + Flet Build Command Fix

## المشكلة
GitHub Action فشل عند:

```bash
flet build apk --yes --verbose --clear-cache
```

لأن `flet-cli 0.28.3` لا يدعم الوسيط `--yes`، فظهر:

```text
flet: error: unrecognized arguments: --yes
```

## الإصلاح
- حذف `--yes` من `.github/workflows/build-apk.yml`.
- تحديث أوامر البناء في `README.md` وملاحظات Phase 42.
- إضافة `tools/flet_build_command_smoke_test.py` لمنع عودة الوسيط غير المدعوم داخل workflow أو التوثيق.
- إبقاء تثبيت `flet==0.28.3` لأنه الخط المقصود لاستعادة FilePicker الحقيقي على Android.

## الأمر الصحيح للبناء

```bash
flet build apk --verbose --clear-cache \
  --product "هوى الشام" \
  --org com.hawaa
```

## سبب Phase 42
الاستيراد الحقيقي يحتاج FilePicker Android فعلي، وليس فقط مسار داخلي داخل التطبيق. لذلك تم تثبيت خط Flet أكثر توافقًا مع FilePicker وإبقاء fallback الداخلي كخطة احتياطية.

## النتيجة المتوقعة
بعد بناء APK بهذا الأمر، زر **استيراد نسخة احتياطية** يجب أن يفتح منتقي ملفات Android الحقيقي لاختيار ملف من Files / Downloads / Drive. إذا بقي FilePicker لا يعمل، فالسبب يكون من APK مبني بكاش قديم أو نسخة Flet مختلفة عن المثبتة في `pyproject.toml`.
