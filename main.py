#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

# ========== تحديد مسار ثابت (نفس مسار قاعدة البيانات) ==========
_FIXED_DATA_DIR = os.path.expanduser('~/.hawaa')
os.environ['HAWAA_DATA_DIR'] = _FIXED_DATA_DIR

# ========== استيراد الوحدات ==========
import flet as ft
import asyncio
import traceback
import sqlite3

from database.migrations import ensure_db
from auth.activation import check_activation, start_license_checker, stop_license_checker
from auth.session import UserSession
from i18n.translator import translate, set_language
from views.login_view import LoginView
from views.splash_view import SplashView
from views.app_layout import AppLayout
from database import SettingsRepository
from database.connection import get_local_db_path

# ========== إعدادات Termux ==========
if os.path.exists("/data/data/com.termux"):
    os.environ.setdefault('DISPLAY', ':1')
    os.environ.setdefault('FLET_SERVER_PORT', '8551')
    os.environ.setdefault('FLET_SERVER_IP', '127.0.0.1')

def main(page: ft.Page):
    # ========== الخطوة 1: التأكد من وجود الجداول ==========
    # نستدعي ensure_db() التي تنشئ الجداول إذا لم تكن موجودة
    ensure_db()
    
    # إجراء إضافي: التأكد من وجود جدول settings حتى لو فشلت ensure_db()
    db_path = get_local_db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1 FROM settings LIMIT 1")
    except sqlite3.OperationalError:
        # الجدول غير موجود، نقوم بإنشائه يدوياً
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        # إدراج القيم الافتراضية
        defaults = [
            ('language', 'ar'), ('theme', 'light'), ('base_currency', 'USD'),
            ('display_currency', 'USD'), ('currency_decimals', '2'),
            ('number_format', 'western'), ('abbreviate_numbers', 'false')
        ]
        conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", defaults)
        conn.commit()
        print("✅ تم إنشاء جدول settings وإدراج القيم الافتراضية")
    finally:
        conn.close()

    page.title = translate('app_title')
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.padding = 0
    page.spacing = 0
    page.bgcolor = ft.Colors.GREY_50

    repo = SettingsRepository()
    set_language(repo.get('language', 'ar'))
    theme = repo.get('theme', 'light')
    page.theme_mode = ft.ThemeMode.LIGHT if theme == 'light' else ft.ThemeMode.DARK

    def show_splash():
        page.controls.clear()
        splash = SplashView(page=page, on_complete=check_license, on_error=lambda msg: show_error(msg))
        page.add(splash)

    def check_license():
        activated, _ = check_activation()
        if activated:
            show_login()
        else:
            show_activation()

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
        page.show_dialog(dialog)

    def show_main_app():
        page.controls.clear()
        app = AppLayout(page=page, on_logout=close_app)
        page.add(app)
        start_license_checker(24, on_license_invalid)

    def on_license_invalid():
        def close_app_after_dialog(e):
            asyncio.create_task(close_app_async())
        dlg = ft.AlertDialog(
            title=ft.Text("ترخيص منتهي", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Text("انتهت صلاحية الترخيص.\nسيتم إغلاق التطبيق."),
            actions=[ft.TextButton("إغلاق", on_click=close_app_after_dialog)],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.show_dialog(dlg)

    async def close_app_async():
        stop_license_checker()
        try:
            from flask_server import stop_flask_server
            stop_flask_server()
        except:
            pass
        try:
            if hasattr(page.window, 'close') and callable(page.window.close):
                await page.window.close()
        except:
            pass

    def close_app():
        asyncio.create_task(close_app_async())

    def show_error(message):
        page.controls.clear()
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=ft.Colors.RED),
                    ft.Text("خطأ فادح", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(message, size=14, text_align=ft.TextAlign.CENTER),
                    ft.FilledButton("إغلاق", on_click=lambda _: close_app(),
                                    bgcolor=ft.Colors.RED, color=ft.Colors.WHITE)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.Alignment.CENTER, expand=True
            )
        )

    try:
        show_splash()
    except Exception as e:
        show_error(str(e))

if __name__ == "__main__":
    ft.run(main)
