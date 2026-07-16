# Phase 97 — Report Image True Renderer + Android RTL Fix

- شدد مسار PNG حتى يبقى توليد الصورة من بيانات الكشف/التقرير، وليس لقطة من واجهة Flet الحالية.
- أضيف fallback عربي عند غياب libraqm في Pillow على Android حتى لا تظهر النصوص العربية معكوسة داخل صور التقارير.
- لا يتم قلب الصورة كاملة؛ تتم معالجة اتجاه النص فقط.
- أضيف اختبار `tools/report_image_true_renderer_rtl_smoke_test.py` للتأكد من عرض PNG على Canvas تقارير مستقل بعرض ثابت، ومن عدم استخدام screenshot/capture/mirror.
