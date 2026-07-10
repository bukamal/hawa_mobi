# Phase 57 — Android External Backup Import Hard Fix

## المشكلة
فتح Android FilePicker لا يضمن أن Python داخل Flet يستطيع قراءة الملف الخارجي. على Android، `FilePickerFile.path` قد يكون `None` أو `content://` أو اسم ملف فقط. لذلك كانت نافذة الاختيار تفتح، لكن الاستيراد الخارجي لا يصل فعليًا إلى ملف ZIP/DB قابل للقراءة.

## الإصلاح
- زر استيراد النسخة الاحتياطية يطلب الآن `with_data=True` عند `pick_files`.
- إذا رجع FilePicker محتوى الملف في `FilePickerFile.bytes` يتم نسخه إلى cache داخلي ثم يتم الاستيراد من هذا المسار المضمون.
- تم الإبقاء على المسارات السابقة: path مباشر، file://، content:// عبر Android ContentResolver عند توفر bridge، ثم البحث بالاسم داخل Download/Hawaa وDownload.
- ZIP الخارجي لم يعد مطالبًا بأن يحتوي `hawaa_data.db` في الجذر فقط؛ يتم قبول قاعدة بيانات SQLite صالحة داخل أي مجلد داخل ZIP، مثل ملفات أعيد ضغطها أو نُقلت عبر WhatsApp/Drive.
- رسالة التشخيص تعرض الآن ما إذا كان FilePicker رجّع bytes/path/uri وحجم البيانات بدل الفشل الصامت.

## الاختبارات
- `backup_external_filepicker_bytes_smoke_test.py`
- `backup_picker_resolution_smoke_test.py`
- `backup_restore_smoke_test.py`
- `backup_import_runtime_refresh_smoke_test.py`

## ملاحظة تشغيل
إذا لم يعمل الاستيراد الخارجي بعد هذه المرحلة، فهذا يعني غالبًا أن الـ APK لم يُبنَ فعليًا من Phase 57 أو أن Flet runtime لا يدعم `with_data=True` في النسخة المبنية. في هذه الحالة ستظهر رسالة تشخيص تحتوي `bytes_len` أو عدمه.
