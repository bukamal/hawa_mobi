# -*- coding: utf-8 -*-
"""Preflight checks before building a real Android APK.

This script is intentionally static/offline so it can run in CI before Flet/Flutter
build. It verifies that the client bundle is clean, branded, and aligned with the
Windows/server API and historic-currency contract.
"""
from __future__ import annotations
import os

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "main.py",
    "pyproject.toml",
    "assets/app_logo.png",
    "assets/icon_android.png",
    "assets/splash_android.png",
    "assets/brand/app_wordmark.png",
    "assets/icons/app_icon_1024.png",
    "services/currency_ledger_service.py",
    "database/connection_rest.py",
    "server/flask_server.py",
    "APK_WINDOWS_COMPATIBILITY_MATRIX.md",
]

FORBIDDEN_SOURCE_PATTERNS = [
    "license.dat",
    "network_license.dat",
    ".pytest_cache",
    "auth/activation.py.tmp",
]

FORBIDDEN_ARTIFACT_PATTERNS = FORBIDDEN_SOURCE_PATTERNS + [
    ".pyc",
    "__pycache__",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(message: str) -> int:
    print("❌", message)
    return 1


def main() -> int:
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    if missing:
        return fail("ملفات مطلوبة غير موجودة: " + ", ".join(missing))

    bad: list[str] = []
    for path in ROOT.rglob("*"):
        r = rel(path)
        for token in FORBIDDEN_SOURCE_PATTERNS:
            if token in r:
                bad.append(r)
                break
    if bad:
        return fail("ملفات حساسة لا يجب أن تبقى في السورس: " + ", ".join(sorted(bad)[:20]))


    ui_kit = (ROOT / "views" / "ui_kit.py").read_text(encoding="utf-8")
    if "ft.Icons.FLIGHT" in ui_kit or "ft.Text('H'" in ui_kit:
        return fail("ui_kit ما زال يستخدم شعار Android القديم H + Flight بدل شعار هوى الشام الموحد")
    if "ASSET_APP_SYMBOL" not in ui_kit or "brand_wordmark" not in ui_kit:
        return fail("ui_kit لا يستخدم أصول الهوية البصرية الموحدة")
    if "ft.ImageFit" in ui_kit:
        return fail("ui_kit يستخدم ft.ImageFit؛ بعض إصدارات Flet داخل APK لا تدعمها. استخدم image_fit() بقيم نصية")
    if "def image_fit(" not in ui_kit:
        return fail("ui_kit لا يحتوي helper image_fit للتوافق مع إصدارات Flet")

    # Flet Android has shown inconsistent rendering for 8-digit alpha hex colors
    # in early startup controls; use solid colors or named opacity controls.
    alpha_hex_files = [ROOT / "views" / "splash_view.py", ROOT / "views" / "ui_kit.py"]
    bad_alpha = []
    import re
    for candidate in alpha_hex_files:
        content = candidate.read_text(encoding="utf-8")
        for match in re.findall(r"#[0-9A-Fa-f]{8}", content):
            bad_alpha.append(f"{rel(candidate)}:{match}")
    if bad_alpha:
        return fail("ألوان alpha hex تسبب خللاً في Flet Android: " + ", ".join(bad_alpha[:10]))


    share_module = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
    if "org.kivy.android.PythonActivity" in share_module or "from jnius import" in share_module:
        return fail("مشاركة Android لا يجب أن تعتمد على Kivy/pyjnius داخل Flet APK؛ استخدم ft.Share")
    if "ft.Share" not in share_module or "ShareFile" not in share_module or "share_files" not in share_module:
        return fail("مشاركة الملفات يجب أن تستخدم Flet Share service و ShareFile")
    if "page.launch_url(file_uri(path))" in share_module:
        return fail("لا تعتبر فتح file:// مشاركة ناجحة على Android؛ استخدم share sheet")
    file_export = (ROOT / "services" / "file_export_service.py").read_text(encoding="utf-8")
    if ".backup(" not in file_export or "sqlite_snapshot=backup_api" not in file_export:
        return fail("نسخ SQLite الاحتياطي يجب أن يستخدم SQLite backup API حتى لا يفقد بيانات WAL")

    settings_view = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
    if "سيتم تطبيق اللغة بعد إعادة التشغيل" in settings_view:
        return fail("تغيير اللغة لا يزال يتطلب إعادة تشغيل؛ يجب تطبيقه فورياً عبر _hawaa_rebuild_main")
    if "_hawaa_refresh_current_page" not in settings_view or "currency.save_runtime_settings" not in settings_view:
        return fail("تغيير عملة العرض يجب أن يطبق فوراً عبر currency.save_runtime_settings و _hawaa_refresh_current_page")
    currency_module = (ROOT / "currency.py").read_text(encoding="utf-8")
    if "def invalidate_cache" not in currency_module or "def save_runtime_settings" not in currency_module:
        return fail("CurrencyManager لا يحتوي آلية تحديث إعدادات العملة فورياً بدون إعادة تشغيل")
    settings_repo_module = (ROOT / "database" / "repositories" / "settings_repo.py").read_text(encoding="utf-8")
    if "_shared_cache" not in settings_repo_module or "invalidate_cache" not in settings_repo_module:
        return fail("SettingsRepository يحتاج cache مشترك وإبطال cache لمنع بقاء عملة العرض القديمة")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if "android.permission.INTERNET" not in pyproject:
        return fail("pyproject.toml لا يعلن إذن INTERNET المطلوب للاتصال بالخادم")

    if "android.permission.CAMERA" not in pyproject:
        return fail("pyproject.toml لا يعلن إذن CAMERA المطلوب لمسح QR بالكاميرا")
    if "[tool.flet.android.permission]" not in pyproject or '"android.permission.CAMERA" = true' not in pyproject:
        return fail("إذن الكاميرا يجب أن يعلن بصيغة Flet الحديثة داخل [tool.flet.android.permission]")
    if 'permissions = ["camera"]' not in pyproject:
        return fail('أضف permissions = ["camera"] كحزمة Flet cross-platform للكاميرا')
    if '"server*"' in pyproject or "Flask" in pyproject or "waitress" in pyproject:
        return fail("pyproject.toml لا يجب أن يحزم server/ أو Flask داخل APK client")
    if "resources/sounds" in pyproject:
        return fail("هذا فرع Flet/Android لا يجب أن يرث resources/sounds الخاصة بسطح المكتب دون قرار واضح")

    server = (ROOT / "server" / "flask_server.py").read_text(encoding="utf-8")
    required_terms = [
        "API_CONTRACT_VERSION",
        "CURRENCY_CONTRACT_VERSION",
        "historic-currency-snapshot-v1",
        "/api/capabilities",
        "supports_historic_currency_snapshot",
        "amount_base",
        "exchange_rate_history",
        "/api/mobile/pairing-token",
        "/api/mobile/pair",
        "hawaa-mobile-pairing-v1",
    ]
    missing_terms = [t for t in required_terms if t not in server]
    if missing_terms:
        return fail("عقد الخادم ناقص: " + ", ".join(missing_terms))

    rest = (ROOT / "database" / "connection_rest.py").read_text(encoding="utf-8")
    if "/api/capabilities" not in rest:
        return fail("RestClient لا يفحص /api/capabilities")
    if "localhost" not in rest or "127.0.0.1" not in rest:
        return fail("RestClient يجب أن يمنع localhost في APK client mode")

    if "def pair_mobile" not in rest or "/api/mobile/pair" not in rest:
        return fail("RestClient لا يدعم تحقق رمز ربط Android عبر /api/mobile/pair")
    pairing = (ROOT / "services" / "pairing_service.py").read_text(encoding="utf-8")
    if "MobilePairingService" not in pairing or "pair_from_qr_text" not in pairing:
        return fail("خدمة ربط QR غير مكتملة في Android")
    if "NetworkService.save_mode(\"client\"" not in pairing:
        return fail("نجاح ربط QR يجب أن يحفظ وضع عميل الشبكة فوراً")
    login_view = (ROOT / "views" / "login_view.py").read_text(encoding="utf-8")
    if "ربط مع Windows عبر QR" not in login_view:
        return fail("واجهة تسجيل الدخول يجب أن توفر ربط Android مع Windows عبر QR قبل تسجيل الدخول")
    if "ربط عبر QR" not in settings_view:
        return fail("إعدادات الشبكة يجب أن توفر ربط QR")
    camera_permission = (ROOT / "services" / "camera_permission_service.py").read_text(encoding="utf-8")
    if "PermissionHandler" not in camera_permission or "request_permission" not in camera_permission:
        return fail("خدمة صلاحية الكاميرا يجب أن تستخدم PermissionHandler عند توفره")
    qr_dialog = (ROOT / "views" / "dialogs" / "qr_pairing_dialog.py").read_text(encoding="utf-8")
    if "مسح بالكاميرا" not in qr_dialog or "لصق من الحافظة" not in qr_dialog:
        return fail("واجهة ربط QR يجب أن توفر مسحاً بالكاميرا مع لصق احتياطي")
    if "استخدم مسار الملف مباشرة" in settings_view:
        return fail("اختيار شعار الشركة لا يزال يعتمد على مسار يدوي؛ يجب استخدام FilePicker ونسخ الشعار للتخزين الداخلي")
    if "make_file_picker" not in settings_view or "company_logo_service" not in settings_view:
        return fail("اختيار شعار الشركة يجب أن يستخدم make_file_picker و company_logo_service")
    if "FilePicker(on_result" in settings_view:
        return fail("لا تستخدم FilePicker(on_result=...)؛ بعض إصدارات Flet ترفضها. استخدم make_file_picker().")
    if "make_file_picker" not in settings_view:
        return fail("اختيار الملفات يجب أن يستخدم make_file_picker للتوافق مع إصدارات Flet المختلفة")
    logo_service = (ROOT / "services" / "company_logo_service.py").read_text(encoding="utf-8")
    if "image_to_data_uri" not in logo_service or "base64" not in logo_service:
        return fail("خدمة شعار الشركة يجب أن تدعم تضمين Base64 في التقارير")
    statement = (ROOT / "reports" / "account_statement.py").read_text(encoding="utf-8")
    if "image_to_data_uri" not in statement or "company-logo" not in statement:
        return fail("تقرير كشف الحساب يجب أن يضمّن شعار الشركة كـ Base64 وليس كمسار ملف")

    # Optional sanity check for produced release ZIP/APK when the operator passes it.
    if len(sys.argv) > 1:
        artifact = Path(sys.argv[1])
        if not artifact.exists():
            return fail(f"الأثر المطلوب فحصه غير موجود: {artifact}")
        if artifact.suffix.lower() in {".zip", ".apk", ".aab"}:
            with zipfile.ZipFile(artifact) as zf:
                names = zf.namelist()
                forbidden_inside = [n for n in names if any(t in n for t in FORBIDDEN_ARTIFACT_PATTERNS)]
                if forbidden_inside:
                    return fail("الأثر يحتوي ملفات ممنوعة: " + ", ".join(forbidden_inside[:20]))

    print("✅ apk_release_preflight passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush() if "sys" in globals() else None
    sys.stderr.flush() if "sys" in globals() else None
    os._exit(code)
