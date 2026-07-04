# اختبار ربط APK مع Windows Server

هذه الصفحة هي Checklist تشغيل حقيقية بعد Phase 19. النموذج المعتمد:

```text
Windows = Server + قاعدة البيانات الرئيسية
Android APK = REST Client فقط
```

لا تنقل ملف SQLite يدويًا بين الهاتف والويندوز.

## 1. تشغيل الخادم على جهاز Windows

على جهاز الخادم شغّل النسخة التي تحتوي `server/run_server.py` أو خادم Windows المتوافق مع العقد التالي:

```text
/api/health
/api/capabilities
/api/login
/api/expenses
/api/expenses/summary
/api/payment_reminders
/api/payment_reminders/count_waiting
/api/exchange_rates
/api/exchange_rate_history
```

الخادم يجب أن يعلن:

```text
api_contract_version = 2026.07.mobile-v1
currency_contract = historic-currency-snapshot-v1
supports_historic_currency_snapshot = true
supports_amount_base = true
supports_exchange_rate_history = true
```

## 2. معرفة IP جهاز الخادم

على Windows:

```bat
ipconfig
```

استخدم IPv4 الخاص بالشبكة، مثل:

```text
192.168.1.50
```

داخل APK لا تستخدم:

```text
localhost
127.0.0.1
0.0.0.0
```

استخدم:

```text
http://192.168.1.50:8000
```

## 3. فحص الاتصال قبل APK

من نفس السورس يمكن تشغيل:

```bash
python tools/network_diagnostics.py http://192.168.1.50:8000
```

النتيجة المقبولة يجب أن تحتوي:

```text
✅ الاتصال بالخادم ناجح
currency_contract: historic-currency-snapshot-v1
supports_amount_base: True
```

## 4. اختبار من الهاتف

1. افتح APK.
2. الإعدادات > الشبكة.
3. اختر وضع عميل شبكة.
4. أدخل عنوان الخادم: `http://SERVER_IP:8000`.
5. سجّل الخروج ثم ادخل بحساب موجود على Windows Server.
6. افتح الحسابات.
7. أضف قيدًا بعملة غير USD.
8. غيّر سعر الصرف على الخادم.
9. عدّل نفس القيد من الهاتف دون تغيير العملة.
10. تأكد أن `exchange_rate_to_usd` لم يتغير.

## 5. اختبار صلاحيات سريع

- `viewer`: قراءة فقط، يجب أن يفشل عند الإضافة/التعديل/الحذف.
- `accountant`: إضافة وتعديل قيود، لا يدير المستخدمين.
- `admin`: كل العمليات.

## 6. فحص ما قبل البناء

قبل بناء APK:

```bash
PYTHONPATH=. python tools/quality_gate.py
PYTHONPATH=. python tools/apk_release_preflight.py
```

بعد بناء APK:

```bash
PYTHONPATH=. python tools/apk_release_preflight.py build/apk/release/hawaa-sham-release.apk
```

## 7. مشاكل شائعة

### يظهر فشل اتصال

تحقق أن الهاتف وجهاز Windows على نفس الشبكة، وأن جدار الحماية يسمح بالمنفذ.

### تظهر رسالة localhost

أنت أدخلت عنوانًا غير صالح للهاتف. استخدم IP جهاز الخادم.

### تظهر رسالة عقد العملات غير متوافق

الخادم قديم. يجب تحديث Windows Server إلى نسخة تدعم:

```text
historic-currency-snapshot-v1
```

### تظهر 401 أو انتهاء جلسة

سجّل الخروج ثم الدخول مجددًا. في وضع الشبكة يتم تخزين token محليًا ويُمسح عند تغيير الوضع أو الخادم.


## الربط عبر QR — Phase 26

بدل إدخال عنوان الخادم يدوياً، يمكن إنشاء QR من Windows يحتوي:

- `server_url`
- `pairing_token` مؤقت
- `currency_contract`
- `api_contract_version`

Android يقبل الرمز فقط إذا كان صالحاً ولم ينتهِ ويدعم الخادم عقد العملات التاريخي. QR لا يغني عن تسجيل الدخول.
