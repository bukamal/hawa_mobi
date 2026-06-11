# اختبارات الجودة

تشغيل جميع الاختبارات من جذر المشروع:

```bash
python tools/quality_gate.py
```

يشمل ذلك:

- `compileall`: فحص أخطاء الاستيراد والترجمة.
- `architecture_smoke_test.py`: فحص طبقة البيانات الجديدة.
- `local_crud_smoke_test.py`: اختبار إضافة/تعديل مبلغ صفر/حذف قيد على قاعدة مؤقتة.
- `network_contract_test.py`: فحص تطابق REST client مع مسارات الخادم، والتأكد أن APK لا يضم Flask/Waitress/server.

اختبار CRUD يستخدم قاعدة بيانات مؤقتة عبر `HAWAA_DATA_DIR` ولا يلمس بيانات التشغيل.
