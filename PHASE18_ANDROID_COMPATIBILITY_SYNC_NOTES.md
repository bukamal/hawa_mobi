# Phase 18 — Android Compatibility Sync

الغرض: مزامنة مشروع Flet/Android مع عقد مشروع هوى الشام Windows بعد مراحل Document Shell والعملات والسعر التاريخي.

## تغييرات محاسبية

- إضافة `amount_base` إلى جدول `expenses`.
- إبقاء `amount` كمرآة Legacy للقيمة المحاسبية بالدولار حتى لا تنكسر شاشات APK القديمة.
- اعتماد العقد التالي:
  - `amount_original`: المبلغ الأصلي الذي أدخله المستخدم.
  - `currency_original`: عملة القيد الأصلية.
  - `exchange_rate_to_usd`: سعر الصرف التاريخي المثبت على القيد.
  - `amount_base`: القيمة المحاسبية الأساسية بالدولار USD.
  - `display_currency`: عملة عرض فقط.
- عند تعديل قيد بنفس العملة، يتم الحفاظ على `exchange_rate_to_usd` القديم.
- عند تغيير عملة القيد، يتم التقاط Snapshot جديد.

## خدمات جديدة

- `services/currency_ledger_service.py`:
  - بناء Snapshot للقيد.
  - حساب `amount_base`.
  - الحفاظ على السعر التاريخي عند تعديل نفس العملة.

## قاعدة البيانات

- `database/migrations.py`:
  - إضافة `amount_base`.
  - إضافة `exchange_rate_history`.
  - رفع `schema_version` إلى `18`.
- `database/connection.py` و `database/data_sources/local.py`:
  - دعم `amount_base` في add/update.
  - تسجيل تاريخ أسعار الصرف.

## REST / Server

- `server/flask_server.py`:
  - الخادم يعيد حساب `amount_base` و `exchange_rate_to_usd` ولا يثق بقيم العميل.
  - دعم `GET /api/exchange_rate_history`.
  - تسجيل `exchange_rate_history` عند تعديل الأسعار.
  - إضافة حماية صلاحيات أولية على عمليات الكتابة.

## APK hygiene

- إزالة `license.dat`, `network_license.dat`, `*.pyc`, `__pycache__`.
- إزالة ملفات الخادم القديمة من جذر مشروع APK:
  - `flask_server.py`
  - `run_server.py`
- بقاء الخادم الرسمي فقط داخل `server/` حتى لا يدخل في حزمة العميل عن طريق الخطأ.

## الترخيص

- نقل الترخيص إلى مسار دائم قابل للكتابة:
  - Android/Flet: `FLET_APP_STORAGE_DATA/config/license.dat`
  - Desktop fallback: `~/.hawaa/config/license.dat`
- دعم صيغ انتهاء متعددة: ISO, `DD/MM/YYYY`, `DD.MM.YYYY`, Unix timestamp, `lifetime`, `unlimited`, `غير محدود`, `مدى الحياة`.

## اختبارات

- أضيف `tools/currency_ledger_contract_smoke_test.py`.
- تم تحديث `tools/local_crud_smoke_test.py` لفحص `amount_base` والحفاظ على السعر التاريخي.
- تم تحديث `tools/network_contract_test.py` ليمر بعد إزالة ملفات الخادم القديمة من مسار APK.

## ملاحظة مهمة

هذه المرحلة تجعل APK متوافقًا محاسبيًا أكثر مع مشروع Windows، لكنها لا تعني أن APK النهائي بُني. يجب تنفيذ Build عبر Flet/Android ثم اختبار الاتصال بخادم Windows الحقيقي على شبكة محلية.
