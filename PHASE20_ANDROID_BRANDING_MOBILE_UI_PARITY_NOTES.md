# Phase 20 — Android Branding & Mobile UI Parity

## الهدف
توحيد الهوية البصرية بين Android APK ونسخة Windows بعد مزامنة العقود المحاسبية والشبكية في Phase 18/19.

## ما تم

1. استبدال شعار Android القديم المبني على `H + airplane` بشعار هوى الشام المستخدم في Windows.
2. تحديث أصول Android:
   - `assets/app_logo.png`
   - `assets/app_logo_small.png`
   - `assets/icon_android.png`
   - `assets/icon.png`
   - `assets/icon_web.png`
   - `assets/icon_ios.png`
   - `assets/brand/app_wordmark.png`
   - `assets/splash_android.png`
   - `assets/splash_dark_android.png`
   - `assets/android_res/mipmap-*/ic_launcher.png`
3. تحويل `views/ui_kit.py` إلى مصدر مركزي للهوية:
   - ألوان Teal/Amber المطابقة للـ Windows.
   - `app_mark()` يستخدم صورة الشعار الرسمية بدل الرسم البرمجي القديم.
   - `brand_wordmark()` و `brand_background()` و `brand_card()` و `status_chip()`.
4. تحسين واجهات ما قبل الدخول:
   - `SplashView` بهوية واضحة وحالة تشغيل.
   - `LoginView` ببطاقة دخول موحدة، شريحة وضع التشغيل، ومسافات أفضل.
   - `ActivationView` ببطاقة ترخيص أوضح ومعرف الجهاز ومسار ملف الترخيص.
5. تحديث `AppLayout`:
   - Drawer يستخدم wordmark رسمي.
   - ألوان Bottom Navigation أصبحت من الهوية الجديدة.
   - إصلاح تكرار إضافة LoginView مرتين في fallback logout.
6. تحديث `pyproject.toml`:
   - وصف التطبيق لم يعد يذكر السياحة والسفر.
   - ألوان splash/adaptive icon أصبحت من هوية هوى الشام.
7. تحديث فحوصات البناء:
   - `tools/ui_brand_smoke_test.py` يمنع رجوع شعار `H + FLIGHT`.
   - `tools/apk_release_preflight.py` يفحص وجود wordmark ويمنع هوية Android القديمة.

## حدود المرحلة
لم يتم إعادة تصميم كل شاشة بيانات تفصيليًا. المرحلة ركزت على الهوية الأساسية، Splash/Login/Activation/Shell، وأصول APK. تحسين Dashboard/Accounts التفصيلي يمكن اعتباره Phase 21 إذا ظهرت ملاحظات بعد تشغيل APK.

## اختبار يدوي مقترح
1. شغّل التطبيق محليًا أو عبر Flet.
2. تأكد أن Splash يعرض شعار الحسابات وليس الطائرة.
3. تأكد أن Login يعرض وضع التشغيل ومربعات بدون تداخل.
4. تأكد أن Activation تعرض معرف الجهاز ومسار الترخيص.
5. ابنِ APK وتأكد من Launcher icon وSplash على Android.
