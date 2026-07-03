# Phase 19 — Android Build & Windows Pairing QA

## الهدف

تحويل فرع Android بعد Phase 18 من “متوافق منطقيًا” إلى فرع قابل للبناء والربط مع Windows Server بفحص واضح قبل إصدار APK.

## ما أضيف

- `/api/capabilities` كـ endpoint عام يعلن عقد API وعقد العملات.
- `RestClient.capabilities()`.
- `NetworkService.check_connection()` يفحص عقد العملات ولا يكتفي بأن الخادم يرد على `/health`.
- `tools/api_capabilities_contract_smoke_test.py`.
- `tools/apk_release_preflight.py`.
- تحديث `tools/network_diagnostics.py` لإظهار health/capabilities.
- تحديث GitHub Action لتشغيل quality gate وpreflight قبل بناء APK وبعده.
- `APK_WINDOWS_PAIRING_QA.md` كدليل اختبار فعلي للهاتف مع Windows Server.

## عقد التوافق الحالي

```text
api_contract_version = 2026.07.mobile-v1
currency_contract = historic-currency-snapshot-v1
base_currency = USD
supports_historic_currency_snapshot = true
supports_amount_base = true
supports_exchange_rate_history = true
```

## نتيجة الفحص

تم تشغيل:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/network_contract_test.py
PYTHONPATH=. python3 tools/api_capabilities_contract_smoke_test.py
PYTHONPATH=. python3 tools/apk_release_preflight.py
PYTHONPATH=. python3 tools/currency_ledger_contract_smoke_test.py
PYTHONPATH=. python3 tools/local_crud_smoke_test.py
```

كلها نجحت في بيئة الفحص.

## ملاحظة

بناء APK الفعلي يحتاج بيئة Flet/Flutter/Android toolchain، لذلك لم يتم إنتاج APK داخل بيئة الفحص هنا. GitHub Action محدث ليبني APK ويعيد فحص artifact بعد البناء.
