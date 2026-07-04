# Phase 26 — QR Network Pairing

هذه المرحلة تضيف ربط Android مع خادم Windows عبر QR / نص QR، بدون إدخال IP والمنفذ يدوياً.

## القاعدة الأمنية

- QR لا يسجّل الدخول.
- QR لا يحتوي كلمة مرور أو Token دائم.
- QR يحتوي `pairing_token` مؤقتاً صالحاً 5 دقائق فقط.
- بعد الربط يجب تسجيل الدخول باسم المستخدم وكلمة المرور.
- الرمز يربط الهاتف بالخادم فقط ويتحقق من أن الخادم يدعم عقد العملات التاريخي.

## Windows / Server

أضيفت endpoints:

- `POST /api/mobile/pairing-token` — يحتاج `admin` أو `manager` وينشئ payload صالحاً للـ QR.
- `POST /api/mobile/pair` — يستقبل `pairing_token` من Android ويتحقق منه.

يجب أن ترسل واجهة Windows عنوان الشبكة المحلي في body عند إنشاء QR، مثال:

```json
{"server_url":"http://192.168.1.50:8000"}
```

ويرجع الخادم:

```json
{
  "ok": true,
  "qr_text": "{...}",
  "payload": {
    "app": "hawaa-sham",
    "kind": "mobile_pairing",
    "pairing_contract": "hawaa-mobile-pairing-v1",
    "server_url": "http://192.168.1.50:8000",
    "pairing_token": "...",
    "expires_at": "...Z",
    "currency_contract": "historic-currency-snapshot-v1"
  }
}
```

واجهة Windows يمكنها عرض `qr_text` كـ QR Code بأي مكتبة QR مناسبة.

## Android

أضيفت:

- `services/pairing_service.py`
- زر ربط داخل شاشة تسجيل الدخول.
- زر ربط داخل الإعدادات > الشبكة.

حالياً يوجد fallback عملي: إذا لم تكن كاميرا/QR scanner متاحة في Flet build، يتم لصق نص QR داخل الحوار.

## الاختبارات

أضيف:

- `tools/mobile_pairing_contract_smoke_test.py`

وتم تحديث:

- `tools/quality_gate.py`
- `tools/apk_release_preflight.py`
- `tools/api_capabilities_contract_smoke_test.py`

نتيجة الفحص:

```bash
PYTHONPATH=. python3 tools/quality_gate.py
# ✅ quality_gate passed
```
