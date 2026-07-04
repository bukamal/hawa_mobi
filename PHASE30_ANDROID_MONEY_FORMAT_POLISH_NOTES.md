# Phase 30 — Android Money Format Polish

## الهدف
تفعيل خيار "اختصار الأعداد الكبيرة" بشكل موحّد داخل واجهات Android، خصوصًا Dashboard وكشف الشركة، حتى لا تتكسر الأرقام الطويلة داخل البطاقات الضيقة.

## التعديلات
- جعل الإعداد الافتراضي لاختصار الأرقام مفعّلًا على Android، مع احترام تعطيله يدويًا من الإعدادات.
- تحسين `currency.format_amount()` لدعم:
  - `compact=None`: اتباع إعداد المستخدم.
  - `compact=True`: اختصار قسري للبطاقات الضيقة.
  - `compact=False`: رقم كامل للتقارير والطباعة.
- إضافة دوال:
  - `format_amount_full()` للتقارير/HTML/CSV.
  - `format_amount_compact()` للواجهات الضيقة.
- إصلاح الاختصار للأرقام السالبة مثل `-1.4M`.
- استبدال التنسيق اليدوي في كشف الشركة `f"{amount:,.2f}"` بتنسيق مركزي من `CurrencyManager`.
- إبقاء تقارير HTML/CSV بالأرقام الكاملة عبر `format_amount_full()`.
- تقليل خطر كسر النصوص داخل `stat_card` و `key_value_tile` باستخدام حجم مناسب وحدود أسطر.

## أمثلة
مع تفعيل الاختصار:
- `200000 SYP` → `200K ل.س`
- `1600000 SYP` → `1.6M ل.س`
- `-1400000 SYP` → `-1.4M ل.س`

مع تعطيل الاختصار:
- `1600000 SYP` → `1,600,000.00 ل.س`

## الاختبارات
أضيف:
- `tools/mobile_money_format_smoke_test.py`

وتم تشغيل:
```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/mobile_money_format_smoke_test.py
PYTHONPATH=. python3 tools/quality_gate.py
```

النتيجة:
```text
mobile_money_format_smoke_test passed
quality_gate passed
```
