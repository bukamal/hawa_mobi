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


## Phase 23 — Flet ImageFit compatibility

إذا ظهر على Android الخطأ `module 'flet' has no attribute 'ImageFit'`، فقد تم إصلاحه باستبدال `ft.ImageFit` بقيم نصية عبر `views/ui_kit.py::image_fit()`. يمنع `apk_release_preflight.py` الرجوع لهذا الاستخدام.

## Phase 24 — Android Runtime Language & Splash Visual Fixes

- Language changes in Settings now apply immediately by rebuilding the active mobile shell instead of requiring an Android app restart.
- Login language selection now persists the language setting and updates visible login labels immediately.
- Splash screen no longer uses 8-digit alpha hex colors in Android startup controls because some Flet Android runtimes render them incorrectly.
- Splash card was changed to an opaque, high-contrast card over the brand gradient for better readability on phones.
- APK preflight now blocks regressions that reintroduce Flet Android alpha-hex startup colors or the old restart-only language message.

## Phase 25 — Runtime Display Currency Fix

تم إصلاح تطبيق عملة العرض على Android فورياً بدون إعادة تشغيل التطبيق. يعتمد الإصلاح على إبطال cache إعدادات العملة مركزياً، وتحديث الصفحة الحالية بعد حفظ إعدادات العملة أو أسعار الصرف. راجع `PHASE25_ANDROID_RUNTIME_DISPLAY_CURRENCY_FIX_NOTES.md`.


## Phase 26 — QR Network Pairing

تمت إضافة ربط Android مع Windows عبر QR / نص QR:

- Windows Server ينشئ `pairing_token` مؤقتاً عبر `/api/mobile/pairing-token`.
- Android يتحقق من QR عبر `/api/mobile/pair`.
- QR لا يحتوي كلمة مرور ولا يسجل الدخول.
- بعد الربط يجب تسجيل الدخول بحساب المستخدم.
- يتم التحقق من `historic-currency-snapshot-v1` قبل قبول الربط.

راجع: `PHASE26_QR_NETWORK_PAIRING_NOTES.md` و `QR_NETWORK_PAIRING_QA.md`.

## Phase 29 — Android Share / Print / Backup Export

تم إصلاح مسار المشاركة والطباعة والنسخ الاحتياطي في Android ليمر عبر Flet Share service بدل `file://` أو Intents غير موثوقة. الطباعة تعمل بإنشاء HTML ثم اختيار تطبيق الطباعة/المتصفح من نافذة المشاركة. النسخ الاحتياطي المحلي يستخدم SQLite backup API لضمان لقطة سليمة مع WAL.


## Phase 30 — Android Money Format Polish

تم توحيد تنسيق المبالغ على Android بحيث يحترم خيار اختصار الأعداد الكبيرة فورًا داخل Dashboard وكشف الشركة والبطاقات، مع إبقاء التقارير والطباعة بالأرقام الكاملة. راجع `PHASE30_ANDROID_MONEY_FORMAT_POLISH_NOTES.md`.

## Phase 31 — QR Scanner and Logo Printing

- شاشة ربط Android مع Windows أصبحت موحدة وتحتوي على زر مسح بالكاميرا مع لصق نص الربط كخيار احتياطي.
- تمت إضافة إذن CAMERA لبناء APK.
- اختيار شعار الشركة يستخدم FilePicker ويخزن الصورة داخل app storage.
- تقارير HTML تضمّن الشعار كـ Base64 حتى يظهر عند الطباعة والمشاركة.
- تم منع بقاء زر FAB الخاص بصفحات أخرى داخل الإعدادات.

## Phase 35 — Network diagnostics and backup restore

Android now includes a local-mode backup restore flow. Restore is disabled in client mode because the authoritative database belongs to Windows Server. Network errors are also translated into user-facing diagnostics instead of raw `HTTPConnectionPool` messages.

Run:

```bash
PYTHONPATH=. python tools/backup_restore_smoke_test.py
PYTHONPATH=. python tools/network_diagnostics_smoke_test.py
PYTHONPATH=. python tools/quality_gate.py
```

## Phase 36 — API Parity + Real Network Contract
تم توحيد عقد API بين Windows Server وAndroid. الربط عبر QR لا يُقبل إلا إذا أعلن الخادم دعم `amount_base`، السعر التاريخي، سجل أسعار الصرف، ملخص القيود، تنبيهات الدفع، وإرسال سجل التدقيق من Android. لاختبار الشبكة من هاتف حقيقي افتح أولًا: `http://IP_WINDOWS:8000/api/health` من متصفح الهاتف.


## Phase 37 — Android FilePicker + Camera Permission Compatibility

- إصلاح استيراد النسخة الاحتياطية على Flet runtimes التي ترفض `FilePicker(on_result=...)`.
- إصلاح اختيار شعار الشركة بنفس مسار التوافق.
- إضافة صيغة أذونات الكاميرا الحديثة في pyproject وطلب صلاحية وقت التشغيل عند توفر PermissionHandler.
- ملاحظة: صلاحية الكاميرا لا تكفي وحدها لماسح QR؛ يجب توفر QR scanner control/extension داخل نسخة Flet، ويبقى لصق نص الربط خيارًا احتياطيًا.

## Phase 38 — Pairing UX + Local QA Fixes

This phase improves Android/Windows pairing diagnostics and permits localhost pairing for same-device/emulator QA. Real phones must still use the Windows LAN IP, and the Android dialog now summarizes QR payloads and hides low-level network exceptions behind clearer diagnostic messages.

## Phase 39
- Android service controls now avoid fatal `Unknown control: FilePicker` red overlay by preferring service registration and refusing unsafe mobile overlay fallback.

## Phase 40 — FilePicker fallback on Android
If the APK runtime does not support Flet FilePicker, backup restore and logo import now show an in-app fallback: recent Hawaa backups created by the app, or a manual readable path inside app storage. This avoids the red `Unknown control: FilePicker` failure and keeps restore possible without a native picker.
