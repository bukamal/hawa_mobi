# Android Brand Manifest — هوى الشام

تمت مزامنة هوية Android مع هوية Windows:

- `assets/app_logo.png`: الرمز الأساسي الموحد.
- `assets/brand/app_wordmark.png`: الشعار النصي الرسمي.
- `assets/icon_android.png`: أيقونة Launcher و adaptive foreground (الرسمة الكحلية على خلفية شفافة، داخل منطقة أمان 66%).
- `assets/splash_android.png`: خلفية Splash بنمط الهوية الجديد.
- `assets/android_res/mipmap-*/ic_launcher.png`: أحجام Android launcher (مرجعية يدوية — `flet build` يتجاهلها ويولّد الأيقونات من `icon_android.png` عبر flutter_launcher_icons).

ملاحظة تقنية: `flet build apk` يقرأ فقط `assets/icon*.png` من جذر مجلد assets ولا يستخدم ملفات mipmap اليدوية إطلاقًا. خلفية الأيقونة التكيفية بيضاء `#FFFFFF` في pyproject.toml لكي تُعرض الرسمة على أبيض مطابق لشعار التطبيق في المعرض/التثبيت.

ممنوع الرجوع إلى شعار Android القديم المرسوم بالكود `H + FLIGHT` لأنه لا يطابق منتج الحسابات على Windows.
