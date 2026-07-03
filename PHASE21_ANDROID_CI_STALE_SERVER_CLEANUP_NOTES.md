# Phase 21 — Android CI Stale Server Cleanup

## المشكلة

فشل GitHub Action في `tools/network_contract_test.py` بسبب وجود ملف قديم في جذر المشروع:

```text
flask_server.py
```

هذا الملف لا يوجد في نسخة Phase 20 النظيفة، لكنه يبقى إذا تم نسخ ملفات المرحلة الجديدة فوق مستودع قديم بدون حذف الملفات القديمة. الاختبار يعتبر أي ملف Python خارج `server/` ويحتوي على `flask` خطرًا على حزمة APK.

## الإصلاح

أضيفت أداة:

```text
tools/cleanup_legacy_root_server_entries.py
```

وتحذف فقط الملفات القديمة المعروفة من جذر المشروع:

```text
flask_server.py
run_server.py
```

ولا تمس الخادم الرسمي الموجود في:

```text
server/flask_server.py
server/run_server.py
```

كما تم تحديث `tools/quality_gate.py` ليشغل أداة التنظيف قبل فحص العقد الشبكي.

## التصحيح المفضل في Git

رغم أن CI صار ينظف الملفات القديمة، الأفضل حذفها من المستودع نهائيًا:

```bash
git rm -f flask_server.py run_server.py
git add tools/cleanup_legacy_root_server_entries.py tools/quality_gate.py PHASE21_ANDROID_CI_STALE_SERVER_CLEANUP_NOTES.md
git commit -m "Clean stale root server entries before APK quality gate"
```

## النتيجة المتوقعة

بعد الإصلاح، يجب أن يمر:

```bash
PYTHONPATH=. python tools/quality_gate.py
```

حتى لو بقيت الملفات القديمة مؤقتًا في workspace قبل تشغيل الفحص.
