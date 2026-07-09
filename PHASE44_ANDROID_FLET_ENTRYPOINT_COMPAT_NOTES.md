# Phase 44 — Android Flet Entrypoint Compatibility

## المشكلة
بعد تثبيت `flet==0.28.3` لاستعادة FilePicker الحقيقي على Android، التطبيق انهار عند التشغيل:

```text
AttributeError: module 'flet' has no attribute 'run'
```

السبب أن خط Flet 0.28.x يستخدم `ft.app(target=...)`، بينما بعض التوثيق/الأكواد الأحدث تستخدم `ft.run(...)`.

## الإصلاح
- إضافة `run_hawaa_app()` في `main.py`.
- إذا كان runtime يدعم `ft.run` يستخدمه.
- إذا لم يدعمه، يستخدم المسار المتوافق مع Flet 0.28.x:

```python
ft.app(target=main, assets_dir="assets")
```

## علاقة الإصلاح بالاستيراد الحقيقي
الاستيراد الحقيقي يعتمد على بناء APK بخط Flet يدعم `FilePicker` على Android. لذلك أبقينا `flet==0.28.3`، وأصلحنا نقطة الدخول بدل الرجوع إلى Flet جديد يعطل FilePicker.

## البناء الصحيح
لا تستخدم `--yes` مع `flet-cli 0.28.3`:

```bash
flet build apk --verbose --clear-cache \
  --product "هوى الشام" \
  --org com.hawaa
```
