# Phase 31 — Android QR Scanner + Company Logo Print Integration

## هدف المرحلة
إصلاح مشكلتين ظهرتا في اختبار APK:

1. ربط Android مع Windows كان يعتمد عمليًا على لصق نص QR فقط.
2. اختيار شعار الشركة للتقارير والطباعة كان غير فعّال ويعتمد على مسار يدوي غير مناسب لـ Android.

## ما تم

### 1. QR Pairing UX
أضيفت واجهة ربط موحّدة:

- `views/dialogs/qr_pairing_dialog.py`

الواجهة الجديدة تحتوي:

- زر **مسح بالكاميرا**.
- زر **لصق من الحافظة**.
- حقل نص QR كخيار احتياطي.
- تحقق أن الربط لا يمنح صلاحيات دخول.
- استخدام نفس الواجهة في Login و Settings.

ملاحظة مهمة: دعم ماسح الكاميرا يعتمد على توفر Barcode/QR scanner control في Flet runtime. إذا لم يكن موجودًا، تظهر رسالة واضحة ويُستخدم اللصق الاحتياطي.

تمت إضافة إذن الكاميرا في:

- `pyproject.toml`

```toml
android.permission.CAMERA
```

### 2. Company Logo Picker
تم استبدال رسالة "استخدم مسار الملف مباشرة" بمنطق عملي:

- فتح `FilePicker` لاختيار PNG/JPG/WEBP.
- نسخ الشعار إلى تخزين التطبيق الداخلي.
- عرض Preview للشعار داخل صفحة بيانات الشركة.
- إضافة زر إزالة الشعار.

الملف الجديد:

- `services/company_logo_service.py`

### 3. Logo Embedding in Print HTML
لم تعد تقارير HTML تعتمد على مسار صورة خارجي. عند الطباعة/المشاركة يتم تضمين الشعار كـ Base64:

```html
<img src="data:image/png;base64,...">
```

هذا يحل مشكلة عدم ظهور الشعار عند فتح التقرير خارج التطبيق أو مشاركته.

تم تعديل:

- `reports/account_statement.py`

### 4. FAB Context Fix
تم منع بقاء FloatingActionButton الخاص بصفحات أخرى داخل الإعدادات أو صفحات لا تحتاج FAB.

تم تعديل:

- `views/app_layout.py`

### 5. فحوصات جديدة
أضيفت:

- `tools/qr_pairing_ui_smoke_test.py`
- `tools/company_logo_print_smoke_test.py`

وتم تحديث:

- `tools/apk_release_preflight.py`
- `tools/quality_gate.py`

## نتيجة الفحص

```bash
PYTHONPATH=. python3 tools/quality_gate.py
```

النتيجة:

```text
quality_gate passed
```

## ما يجب اختباره على الهاتف

1. الإعدادات > الشبكة > ربط عبر QR:
   - يظهر زر مسح بالكاميرا.
   - يظهر لصق من الحافظة كخيار احتياطي.
   - الربط ينجح بعد لصق/مسح رمز Windows.

2. الإعدادات > الشركة:
   - اختيار شعار يفتح FilePicker.
   - تظهر معاينة الشعار.
   - الحفظ يخزن الشعار.
   - إزالة الشعار تعمل.

3. كشف الشركة > كشف للطباعة:
   - التقرير HTML يحتوي الشعار.
   - الشعار يظهر عند فتح التقرير أو مشاركته.

4. الإعدادات:
   - لا يظهر زر + مستخدم العائم داخل صفحة الإعدادات.
