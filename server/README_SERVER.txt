خادم هوى الشام - المرحلة 2

هذا الخادم مستقل عن APK. لا تستورده من main.py ولا تضفه إلى بناء Android.

التشغيل على جهاز الخادم:
1) من جذر المشروع hf:
   pip install -r server/requirements.txt
2) شغّل:
   python server/run_server.py
3) من العميل/الهاتف استخدم عنوان جهاز الخادم في نفس الشبكة:
   http://192.168.1.100:8000

نقاط API الأساسية:
- GET  /api/health بدون تسجيل دخول.
- POST /api/login لإرجاع token.
- كل العمليات الأخرى تتطلب Authorization: Bearer <token>.
- expenses/users/settings/exchange_rates/audit_log/payment_reminders.

ملاحظة APK:
pyproject.toml لا يحتوي server ولا Flask ولا waitress. التطبيق المحمول يبقى Local/Client فقط.


مرحلة 5 - تشغيل إنتاجي أكثر وضوحاً
====================================

تشغيل الخادم:
    pip install -r server/requirements.txt
    python server/run_server.py

متغيرات البيئة الاختيارية:
    HAWAA_SERVER_HOST=0.0.0.0
    HAWAA_SERVER_PORT=8000
    HAWAA_SERVER_THREADS=4
    HAWAA_TOKEN_TTL_MINUTES=720

مثال:
    HAWAA_SERVER_PORT=8080 python server/run_server.py

فحص من جهاز العميل أو من نفس الشبكة:
    python tools/network_diagnostics.py http://IP-ADDRESS:8000

ملاحظات أمنية:
    - لا تستخدم localhost في الهاتف؛ استخدم IP جهاز الخادم.
    - لا تعرض الخادم على الإنترنت قبل إضافة HTTPS وجدار ناري ومستخدمين بكلمات مرور قوية.
    - /api/health عام لفحص الحياة فقط، أما /api/server_info فيحتاج تسجيل دخول.
