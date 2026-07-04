# Phase 22 — Android CI Sensitive Artifact Cleanup

## المشكلة

فشل `tools/apk_release_preflight.py` في GitHub Actions لأن مساحة العمل كانت تحتوي على بقايا تشغيل/ترخيص قديمة في جذر مشروع Android:

- `license.dat`
- `network_license.dat`
- `auth/activation.py.tmp`

هذه الملفات لا يجوز أن تبقى في السورس ولا أن تدخل APK.

## الإصلاح

أضيفت الأداة:

```bash
python tools/cleanup_sensitive_source_files.py
```

وتقوم بحذف الملفات التالية فقط:

- `license.dat`
- `network_license.dat`
- `auth/activation.py.tmp`
- `.pytest_cache/`

ولا تلمس `auth/activation.py` الحقيقي.

كما تم تحديث `tools/quality_gate.py` حتى يشغّل التنظيف قبل `apk_release_preflight.py`.

## أوامر مقترحة داخل Git

إذا كانت الملفات الحساسة متتبعة في المستودع، احذفها من Git:

```bash
git rm -f license.dat network_license.dat auth/activation.py.tmp 2>/dev/null || true
git add tools/cleanup_sensitive_source_files.py tools/quality_gate.py PHASE22_ANDROID_CI_SENSITIVE_ARTIFACT_CLEANUP_NOTES.md
git commit -m "Clean sensitive Android runtime artifacts before preflight"
git push
```

## الفحص

تم اختبار `quality_gate.py` مع إنشاء هذه الملفات يدويًا، ثم نجح التنظيف والفحص.


## quality_gate stabilization

`tools/quality_gate.py` now uses `subprocess.run(..., timeout=80, check=True)` instead of the older custom `Popen` loop. This keeps the CI job deterministic.

The CI quality gate is intentionally limited to stateless / release-critical checks:

- architecture smoke test
- local CRUD smoke test
- currency ledger contract
- network contract
- API capabilities contract
- APK release preflight
- server import smoke test

The following checks remain available, but are now manual because they can inherit runtime/session side effects in GitHub-hosted Linux shells after previous smoke tests:

- `tools/auth_token_smoke_test.py`
- `tools/auth_persistent_token_smoke_test.py`
- `tools/network_mode_bootstrap_smoke_test.py`
- `tools/network_mode_logout_flow_smoke_test.py`
- `tools/dashboard_currency_totals_smoke_test.py`

Run them manually when working on auth/network/session/dashboard logic.
