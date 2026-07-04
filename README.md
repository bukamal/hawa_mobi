# hawa_mobi

## Phase 18 — Android / Windows Compatibility

تمت إضافة مزامنة محاسبية مع نسخة Windows الحديثة:

- `amount_base` كقيمة محاسبية بالدولار.
- `amount_original` و `currency_original` و `exchange_rate_to_usd` كسعر تاريخي ثابت.
- عدم إعادة تسعير القيد القديم عند تعديل نفس العملة.
- دعم سجل تاريخ أسعار الصرف.
- نقل الترخيص إلى مسار بيانات دائم بدل حفظه داخل مجلد المشروع.

للفحص:

```bash
python -m compileall -q .
PYTHONPATH=. python tools/local_crud_smoke_test.py
PYTHONPATH=. python tools/currency_ledger_contract_smoke_test.py
PYTHONPATH=. python tools/network_contract_test.py
```


## Phase 19 — Android / Windows Pairing QA

قبل بناء APK فعلي أو ربط الهاتف بجهاز Windows، شغّل:

```bash
PYTHONPATH=. python tools/quality_gate.py
PYTHONPATH=. python tools/apk_release_preflight.py
```

ولفحص خادم Windows من نفس الشبكة:

```bash
PYTHONPATH=. python tools/network_diagnostics.py http://SERVER_IP:8000
```

العقد المطلوب بين APK وWindows Server:

```text
api_contract_version = 2026.07.mobile-v1
currency_contract = historic-currency-snapshot-v1
supports_amount_base = true
supports_exchange_rate_history = true
```

راجع:

```text
APK_WINDOWS_PAIRING_QA.md
PHASE19_ANDROID_BUILD_PAIRING_QA_NOTES.md
```

## Phase 20 — Android Branding & Mobile UI Parity

تمت مزامنة الهوية البصرية بين Android وWindows:

- استبدال شعار Android القديم `H + airplane` بشعار هوى الشام الرسمي.
- تحديث أيقونات Android وSplash وWordmark.
- تحسين Splash/Login/Activation/AppLayout.
- اعتماد ألوان Teal/Amber نفسها الموجودة في نسخة Windows.
- تحديث فحوصات `ui_brand_smoke_test` و `apk_release_preflight` لمنع رجوع الهوية القديمة.

للفحص:

```bash
PYTHONPATH=. python tools/ui_brand_smoke_test.py
PYTHONPATH=. python tools/apk_release_preflight.py
PYTHONPATH=. python tools/quality_gate.py
```

راجع:

```text
PHASE20_ANDROID_BRANDING_MOBILE_UI_PARITY_NOTES.md
assets/brand/ANDROID_BRAND_MANIFEST.md
```


## Phase 21 — CI cleanup for stale root server files

If the Android project was updated by copying phase files over an older checkout, old root-level files such as `flask_server.py` or `run_server.py` may remain and fail `tools/network_contract_test.py`. Phase 21 adds `tools/cleanup_legacy_root_server_entries.py`, and `tools/quality_gate.py` runs it before the APK safety checks.

Preferred Git cleanup:

```bash
git rm -f flask_server.py run_server.py
PYTHONPATH=. python tools/quality_gate.py
```


## CI cleanup notes

Before Android quality gates, run:

```bash
PYTHONPATH=. python tools/quality_gate.py
```

The quality gate now removes stale runtime artifacts before preflight:

- `flask_server.py` and `run_server.py` from the repository root only
- `license.dat`
- `network_license.dat`
- `auth/activation.py.tmp`
- `.pytest_cache/`

If any of these files are tracked by Git, remove them permanently:

```bash
git rm -f license.dat network_license.dat auth/activation.py.tmp 2>/dev/null || true
git rm -f flask_server.py run_server.py 2>/dev/null || true
```
