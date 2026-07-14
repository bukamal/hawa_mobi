# Phase 92 — Dialog Open Regression Fix

إصلاح تراجع فتح النوافذ بعد إضافة حقول البحث في Phase 91.

## السبب

`SearchableLookupField` عرّف خاصية `disabled`، بينما Flet يهيئ خاصية `disabled` في كائن التحكم الأساسي أثناء `Column.__init__`. في بعض إصدارات Flet Android يتم استدعاء setter قبل إنشاء `self.field`، فيفشل إنشاء الحوار، فتبدو أزرار إضافة قيد / خدمة / سدد عني كأنها لا تفتح شيئاً.

## الإصلاح

- استخدام قيمة داخلية `_disabled` قبل استدعاء `super().__init__`.
- جعل setter الخاص بـ `disabled` آمناً قبل إنشاء TextField.
- إضافة رسائل خطأ واضحة عند فشل فتح نافذة خدمة أو سداد بالنيابة.
- إضافة اختبار يحاكي تهيئة Flet المبكرة لخاصية `disabled`.

## الاختبار

- `tools/searchable_lookup_dialog_open_guard_smoke_test.py`
