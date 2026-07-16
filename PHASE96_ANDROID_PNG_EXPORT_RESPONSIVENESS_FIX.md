# Phase 96 — Android PNG Export Responsiveness Fix

يعالج هذا الإصلاح مشكلة ظهور زر صورة/PNG كأنه لا يستجيب داخل تفاصيل الشركة ومركز التقارير.

## السبب

مسار PNG السابق كان يعتمد على جدولة إضافية عبر run_async_task، ويولّد صورًا طويلة جدًا عند وجود قيود أو تقارير كثيرة. على Android قد يؤدي ذلك إلى استهلاك ذاكرة/وقت كبير أو فشل صامت، فيبدو الزر غير مستجيب. كذلك بعض إصدارات Pillow على Android ترفض اتجاه RTL عند الرسم إذا لم يتوفر دعم libraqm أو خط مناسب.

## التعديل

- جعل زر صورة في تفاصيل الشركة async مباشرًا بدل wrapper إضافي.
- جعل زر PNG في مركز التقارير async مباشرًا بدل wrapper إضافي.
- جعل صور الكشوف مختصرة ومناسبة للمشاركة مع حد صفوف افتراضي.
- جعل صور التقارير مختصرة بحد 40 صفًا افتراضيًا.
- إضافة ملاحظة داخل الصورة عند قص الصفوف، مع الإبقاء على HTML/CSV للمخرجات الكاملة.
- تقليل استهلاك الحفظ عبر optimize=False وcompress_level=3.
- جعل رسم النص العربي لا يفشل عند غياب دعم direction/RTL داخل Pillow.

## الاختبارات

- report_image_export_smoke_test
- image_export_button_responsive_smoke_test
- image_export_android_responsiveness_regression_test
- reporting_center_core_smoke_test
- reporting_center_advanced_smoke_test
- apk_release_preflight
