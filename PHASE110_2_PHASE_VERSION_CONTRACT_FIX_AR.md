# المرحلة 110.2 — إصلاح عقود إصدار اختبارات المراحل 102–104

## سبب الفشل

كانت اختبارات المراحل 102 و103 و104 تتحقق من وجود النص الحرفي التالي داخل `pyproject.toml`:

```text
version = "1.0.50"
```

بعد رفع إصدار التطبيق إلى `1.0.55` أصبح هذا الشرط يفشل رغم أن الإصدار الجديد يشتمل على وظائف المراحل السابقة ولا يقل عنها.

## الإصلاح

تم تعديل الاختبارات الثلاثة لتقرأ `pyproject.toml` بواسطة `tomllib`، ثم تتحقق من أن الإصدار الحالي يساوي `1.0.50` أو أحدث:

```python
pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
version = str(pyproject["project"]["version"])
numeric = tuple(int(part) for part in version.split(".")[:3])
assert numeric >= (1, 0, 50), version
```

الملفات المعدلة:

- `tools/phase102_secure_admin_settings_smoke_test.py`
- `tools/phase103_accounts_reports_performance_smoke_test.py`
- `tools/phase104_navigation_recovery_accessibility_smoke_test.py`

لم يتغير إصدار التطبيق أو قاعدة البيانات أو منطق التشغيل.

## التحقق

نجحت الاختبارات الثلاثة منفردة:

- `phase102_secure_admin_settings_smoke_test passed`
- `phase103_accounts_reports_performance_smoke_test passed`
- `phase104_navigation_recovery_accessibility_smoke_test passed`

كما تم البحث في مجلد `tools` ولم يبقَ أي اختبار يفرض `version = "1.0.50"` حرفيًا.
