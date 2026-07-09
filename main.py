#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import traceback
import asyncio
import flet as ft
import sqlite3

from database.migrations import ensure_db
from auth.activation import check_activation, start_license_checker, stop_license_checker
from auth.session import UserSession
from i18n.translator import translate, set_language, is_rtl
from views.login_view import LoginView
from views.splash_view import SplashView
from views.app_layout import AppLayout
from database import SettingsRepository
from database.connection import get_local_db_path
from views.flet_compat import open_control, close_control, apply_arabic_ui_defaults, ALIGN_CENTER, run_async_task

print("[INFO] بدء تشغيل تطبيق هوى الشام")

_FIXED_DATA_DIR = os.environ.get('FLET_APP_STORAGE_DATA') or os.path.expanduser('~/.hawaa')
os.environ.setdefault('HAWAA_DATA_DIR', _FIXED_DATA_DIR)

if os.path.exists("/data/data/com.termux"):
    os.environ.setdefault('DISPLAY', ':1')
    os.environ.setdefault('FLET_SERVER_PORT', '8551')
    os.environ.setdefault('FLET_SERVER_IP', '127.0.0.1')
    print("[INFO] تم الكشف عن بيئة Termux")

def close_dialog(dialog):
    if dialog:
        # Use the active page from the dialog if available; otherwise closing is best-effort.
        page = getattr(dialog, 'page', None)
        if page is not None:
            close_control(page, dialog)
        else:
            try:
                dialog.open = False
            except Exception:
                pass

def handle_exception(page: ft.Page, error: Exception, message: str = "خطأ غير متوقع"):
    error_details = traceback.format_exc()
    print(f"[ERROR] {message}: {str(error)}\n{error_details}")
    try:
        dlg = ft.AlertDialog(
            title=ft.Text("❗ خطأ", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            content=ft.Column([
                ft.Text(message, size=14, weight=ft.FontWeight.BOLD),
                ft.Text(str(error), size=12, color=ft.Colors.RED),
                ft.Text("راجع مخرجات الطرفية لمزيد من التفاصيل", size=12, color=ft.Colors.GREY_600),
            ], tight=True, spacing=10),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: close_dialog(dlg))],
        )
        open_control(page, dlg)
    except Exception as e:
        print(f"[ERROR] فشل عرض الخطأ في الواجهة: {e}")

def main(page: ft.Page):
    print("[INFO] تم استدعاء main()")
    
    try:
        ensure_db()
        print("[INFO] تم التأكد من قاعدة البيانات")
        
        db_path = get_local_db_path()
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1 FROM settings LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            defaults = [
                ('language', 'ar'), ('theme', 'light'), ('base_currency', 'USD'),
                ('display_currency', 'USD'), ('currency_decimals', '2'),
                ('number_format', 'western'), ('abbreviate_numbers', 'false'),
                ('network/mode', 'local'), ('network/server_url', '')
            ]
            conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", defaults)
            conn.commit()
            print("[INFO] تم إنشاء جدول settings")
        finally:
            conn.close()
    except Exception as e:
        handle_exception(page, e, "فشل في تهيئة قاعدة البيانات")
        return

    apply_arabic_ui_defaults(page)
    page.title = translate('app_title')
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#F6FAF9"

    repo = SettingsRepository()
    set_language(repo.get('language', 'ar'))
    page.rtl = is_rtl()
    page.title = translate('app_title')
    theme = repo.get('theme', 'light')
    page.theme_mode = ft.ThemeMode.LIGHT if theme == 'light' else ft.ThemeMode.DARK

    def show_splash():
        page.controls.clear()
        splash = SplashView(page=page, on_complete=after_splash, on_error=lambda msg: show_error(msg, retry=show_splash))
        page.add(splash)

    def after_splash(result=None):
        try:
            result = result or {}
            if not result.get('activated'):
                show_activation()
                return
            if result.get('session') and UserSession.is_authenticated():
                if UserSession.force_password_change():
                    show_change_password()
                else:
                    show_main_app()
                return
            show_login()
        except Exception as e:
            handle_exception(page, e, "خطأ في التحقق من بدء التشغيل")

    def show_activation():
        page.controls.clear()
        from views.activation_view import ActivationView
        activation = ActivationView(page=page, on_success=show_login, on_cancel=close_app)
        page.add(activation)

    def show_login():
        page.controls.clear()
        login = LoginView(page=page, on_login_success=on_login_success, on_exit=close_app)
        page.add(login)

    def on_login_success(user):
        if UserSession.force_password_change():
            show_change_password()
        else:
            show_main_app()

    def show_change_password():
        from views.dialogs.change_password_dialog import ChangePasswordDialog
        dialog = ChangePasswordDialog(page=page, on_save=lambda: show_main_app())
        open_control(page, dialog)

    def show_main_app():
        # Expose central hooks for nested views such as settings.
        # The language hook rebuilds the current shell immediately after a
        # language change instead of requiring an Android process restart.
        def rebuild_main_app():
            page.rtl = is_rtl()
            page.title = translate('app_title')
            page.controls.clear()
            app = AppLayout(page=page, on_logout=logout)
            page.add(app)
            page.update()

        try:
            setattr(page, '_hawaa_logout', logout)
            setattr(page, '_hawaa_rebuild_main', rebuild_main_app)
        except Exception:
            pass
        rebuild_main_app()
        start_license_checker(24, on_license_invalid)

    def logout():
        from views.flet_compat import close_all_dialogs
        stop_license_checker()
        try:
            close_all_dialogs(page)
        except Exception:
            pass
        UserSession.logout()
        show_login()

    def on_license_invalid():
        def close_app_after_dialog(e):
            run_async_task(page, close_app_async)
        dlg = ft.AlertDialog(
            title=ft.Text("ترخيص منتهي", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Text("انتهت صلاحية الترخيص.\nسيتم إغلاق التطبيق."),
            actions=[ft.TextButton("إغلاق", on_click=close_app_after_dialog)],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        open_control(page, dlg)

    async def close_app_async():
        stop_license_checker()
        try:
            if hasattr(page.window, 'close') and callable(page.window.close):
                page.window.close()
        except Exception as e:
            print(f"[ERROR] خطأ أثناء الإغلاق: {e}")

    def close_app():
        run_async_task(page, close_app_async)

    def show_error(message, retry=None):
        print(f"[ERROR] عرض خطأ فادح: {message}")
        page.controls.clear()
        controls = [
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=ft.Colors.RED),
            ft.Text("تعذر بدء التطبيق", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(message, size=14, text_align=ft.TextAlign.CENTER),
        ]
        if retry:
            controls.append(ft.FilledButton("إعادة المحاولة", on_click=lambda _: retry(), bgcolor="#118276", color=ft.Colors.WHITE))
        controls.append(ft.TextButton("إغلاق", on_click=lambda _: close_app()))
        page.add(
            ft.Container(
                content=ft.Column(controls, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ALIGN_CENTER, expand=True, padding=24
            )
        )

    try:
        show_splash()
    except Exception as e:
        handle_exception(page, e, "خطأ في تشغيل التطبيق")

def run_hawaa_app():
    """Run the Flet app across old and new Flet runtimes.

    The Android APK currently pins the FilePicker-stable Flet 0.28.x line.
    That runtime exposes ``ft.app(...)`` but not ``ft.run(...)``.  Newer Flet
    documentation may use ``ft.run(...)``.  Keep both paths so the same source
    can start under either runtime without crashing before Splash/Login.
    """
    if hasattr(ft, "run") and callable(getattr(ft, "run")):
        return ft.run(main, assets_dir="assets")
    # Flet 0.28.x compatible path.
    return ft.app(target=main, assets_dir="assets")


if __name__ == "__main__":
    sys.excepthook = lambda exctype, value, tb: print(f"[CRITICAL] Unhandled exception: {value}")
    run_hawaa_app()
