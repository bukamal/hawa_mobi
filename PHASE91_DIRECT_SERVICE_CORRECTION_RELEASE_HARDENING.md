# Phase 91 — Direct Service Correction & Release Hardening

## الهدف
تقوية مسار الخدمة المباشرة حتى يصبح صالحًا للتشغيل المحاسبي العملي: التعديل والعكس يتمان على العملية الأصلية، وليس على القيود المنفردة، مع سجل تدقيق وسبب إلزامي.

## التغييرات
- إضافة تعديل آمن للخدمة المباشرة عبر `DirectServiceRepository.update`.
- إضافة عكس آمن للخدمة المباشرة عبر `DirectServiceRepository.reverse`.
- منع تعديل الخدمة المباشرة بعد عكسها.
- الحفاظ على قيد العميل وقيد المورد كقيود مقفلة مترابطة.
- إذا أزيل المورد/التكلفة أثناء تصحيح الخدمة، يتم إزالة قيد المورد المولّد ضمن Transaction واحدة.
- إذا أضيف مورد أثناء التصحيح، يتم إنشاء قيد المورد المولّد ضمن نفس Transaction.
- إضافة زر `تعديل الخدمة` وزر `عكس الخدمة` في شاشة تفاصيل الشركة للقيود المباشرة.
- إضافة سبب إلزامي للتعديل والعكس.
- إضافة REST endpoints للخدمات المباشرة في خادم Android/Windows API:
  - `GET /api/direct_services`
  - `POST /api/direct_services`
  - `GET /api/direct_services/{reference}`
  - `PUT /api/direct_services/{reference}`
  - `POST /api/direct_services/{reference}/reverse`
- إضافة RestClient methods المقابلة.

## الاختبارات
- `tools/direct_service_correction_smoke_test.py`
- `tools/direct_service_api_contract_smoke_test.py`
