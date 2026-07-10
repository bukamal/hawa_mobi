# Phase 63 — Android Native File Share / WhatsApp Attachment Fix

## المشكلة
في APK Android لم تكن نسخة Flet الحالية توفر `ft.Share`، لذلك أزرار:

- مشاركة كشف الحساب
- واتساب
- فتح/طباعة كشف الحساب
- CSV / النسخ الاحتياطي

كانت تسقط إلى fallback نصي عبر `wa.me` أو نافذة مسار، فيتم إرسال نص مثل اسم ملف HTML بدل إرفاق الملف نفسه.

## التصحيح
تم تعديل `reports/share.py` ليضيف مسار Android native قبل أي Flet fallback:

1. نسخ الملف إلى Android `MediaStore.Downloads` داخل `Download/Hawaa`.
2. الحصول على `content://` URI صالح للمشاركة مع التطبيقات الخارجية.
3. فتح Android `ACTION_SEND` مع:
   - `Intent.EXTRA_STREAM`
   - `FLAG_GRANT_READ_URI_PERMISSION`
   - دعم WhatsApp العادي و WhatsApp Business.
4. منع fallback واتساب النصي التلقائي حتى لا تُرسل رسالة بلا ملف.

## تعديل واجهة كشف الحساب
تم اختصار رسالة WhatsApp إلى:

```text
كشف حساب - اسم الشركة
```

والملف نفسه يرسل كمرفق عبر Android intent.

## اختبارات الحماية
أضيف:

```text
tools/android_native_file_share_smoke_test.py
```

ويتحقق من وجود Android native file attachment pipeline ومنع الرجوع إلى text-only fallback.

## أوامر الفحص

```bash
PYTHONPATH=. python tools/android_native_file_share_smoke_test.py
PYTHONPATH=. python tools/report_action_share_print_whatsapp_smoke_test.py
PYTHONPATH=. python tools/share_export_fallback_smoke_test.py
PYTHONPATH=. python tools/apk_release_preflight.py
```
