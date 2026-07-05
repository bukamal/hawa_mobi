# Phase 36 — API Parity + Real Network Contract

## الهدف
توحيد عقد API بين نسخة Windows Server ونسخة Android/Flet حتى لا ينجح الربط عبر QR ثم تفشل شاشات Android بعد تسجيل الدخول بسبب endpoints ناقصة.

## Windows
تمت إضافة endpoints التي يحتاجها Android:

- `GET /api/health`
- `GET /api/server_info`
- `GET /api/expenses/summary`
- `GET /api/payment_reminders`
- `GET /api/payment_reminders/count_waiting`
- `POST /api/audit_log`
- `GET /api/settings`

كما تم تحديث `/api/capabilities` ليعلن صراحة:

- `supports_payment_reminders = true`
- `supports_audit_post = true`
- `supports_expense_summary = true`
- `supports_amount_base = true`
- `supports_exchange_rate_history = true`
- `supports_mobile_pairing = true`

## Android
تم تشديد قبول الربط عبر QR. Android لم يعد يكتفي بأن الخادم يعمل ويدعم السعر التاريخي فقط، بل يرفض الخادم إذا لم يعلن دعم:

- `amount_base`
- `exchange_rate_history`
- `expense_summary`
- `payment_reminders`
- `audit_post`

هذا يمنع ربط APK بخادم Windows قديم ظاهريًا يعمل لكنه غير متوافق وظيفيًا.

## الاختبارات
Windows:

```bash
python3 scripts/check_project_readiness.py
python3 -m compileall -q .
PYTHONPATH=. pytest -q
```

Android:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/quality_gate.py
```

## ملاحظة اختبار الشبكة
إذا كان الهاتف حقيقيًا، يجب أن يفتح هذا الرابط من متصفح الهاتف قبل اختبار التطبيق:

```text
http://IP_WINDOWS:8000/api/health
```

إذا لم يفتح في المتصفح، فالمشكلة شبكة/Firewall وليست QR ولا تسجيل دخول.
