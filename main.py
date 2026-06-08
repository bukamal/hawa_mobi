#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import traceback
import asyncio

# ========== إعداد التسجيل (logging) أولاً ==========
from logger import logger

try:
    logger.info("بدء تشغيل تطبيق هوى الشام")
    logger.info(f"المسار الحالي: {os.getcwd()}")
    logger.info(f"المتغيرات البيئية: HAWAA_DATA_DIR={os.environ.get('HAWAA_DATA_DIR')}")
except Exception as e:
    print(f"فشل إعداد التسجيل: {e}")

# ========== تحديد مسار ثابت (نفس مسار قاعدة البيانات) ==========
_FIXED_DATA_DIR = os.path.expanduser('~/.hawaa')
os.environ['HAWAA_DATA_DIR'] = _FIXED_DATA_DIR

# ========== استيراد الوحدات ==========
import flet as ft
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
    logger.info("تم الكشف عن بيئة Termux")

def handle_exception(page: ft.Page, error: Exception, message: str = "خطأ غير متوقع"):
    """عرض الخطأ في واجهة المستخدم وتسجيله في الملف"""
    error_details = traceback.format_exc()
    logger.error(f"{message}: {str(error)}\n{error_details}")
    
    # محاولة عرض الخطأ في واجهة التطبيق إذا كانت الصفحة موجودة
    try:
        dlg = ft.AlertDialog(
            title=ft.Text("❗ خطأ", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            content=ft.Column([
                ft.Text(message, size=14, weight=ft.FontWeight.BOLD),
                ft.Text(str(error), size=12, color=ft.Colors.RED),
                ft.Text("راجع ملف السجل لمزيد من التفاصيل", size=12, color=ft.Colors.GREY_600),
            ], tight=True, spacing=10),
            actions=[ft.TextButton("إغلاق", on_click=lambda e: close_dialog(dlg))],
        )
        page.overlay.append(dlg)
        page.open(dlg)
    except Exception as e:
        logger.error(f"فشل عرض الخطأ في الواجهة: {e}")

def close_dialog(dialog):
    dialog.open = False
    if dialog.page:
        dialog.page.update()

def main(page: ft.Page):
    logger.info("تم استدعاء main()، تهيئة الصفحة...")
    
    try:
        # ========== الخطوة 1: التأكد من وجود الجداول ==========
        ensure_db()
        logger.info("تم التأكد من قاعدة البيانات")
        
        # إجراء إضافي: التأكد من وجود جدول settings
        db_path = get_local_db_path()
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1 FROM settings LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            defaults = [
                ('language', 'ar'), ('theme', 'light'), ('base_currency', 'USD'),
                ('display_currency', 'USD'), ('currency_decimals', '2'),
                ('number_format', 'western'), ('abbreviate_numbers', 'false')
            ]
            conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", defaults)
            conn.commit()
            logger.info("تم إنشاء جدول settings وإدراج القيم الافتراضية")
        finally:
            conn.close()
    except Exception as e:
        handle_exception(page, e, "فشل في تهيئة قاعدة البيانات")
        return

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
    logger.info(f"تم ضبط اللغة: {repo.get('language', 'ar')}، المظهر: {theme}")

    def show_splash():
        page.controls.clear()
        splash = SplashView(page=page, on_complete=check_license, on_error=lambda msg: show_error(msg))
        page.add(splash)
        logger.info("شاشة البداية معروضة")

    def check_license():
        logger.info("التحقق من الترخيص...")
        try:
            activated, msg = check_activation()
            if activated:
                logger.info("الترخيص صالح")
                show_login()
            else:
                logger.warning(f"الترخيص غير صالح: {msg}")
                show_activation()
        except Exception as e:
            logger.error(f"خطأ في التحقق من الترخيص: {e}")
            show_error(str(e))

    def show_activation():
        page.controls.clear()
        from views.activation_view import ActivationView
        activation = ActivationView(page=page, on_success=show_login, on_cancel=close_app)
        page.add(activation)
        logger.info("شاشة التفعيل معروضة")

    def show_login():
        page.controls.clear()
        login = LoginView(page=page, on_login_success=on_login_success, on_exit=close_app)
        page.add(login)
        logger.info("شاشة تسجيل الدخول معروضة")

    def on_login_success(user):
        logger.info(f"تسجيل دخول ناجح: {user.get('username')}")
        if UserSession.force_password_change():
            show_change_password()
        else:
            show_main_app()

    def show_change_password():
        from views.dialogs.change_password_dialog import ChangePasswordDialog
        dialog = ChangePasswordDialog(page=page, on_save=lambda: show_main_app())
        page.open(dialog)
        logger.info("فتح حوار تغيير كلمة المرور")

    def show_main_app():
        logger.info("فتح التطبيق الرئيسي")
        page.controls.clear()
        app = AppLayout(page=page, on_logout=close_app)
        page.add(app)
        start_license_checker(24, on_license_invalid)

    def on_license_invalid():
        logger.warning("الترخيص أصبح غير صالح أثناء التشغيل")
        def close_app_after_dialog(e):
            asyncio.create_task(close_app_async())
        dlg = ft.AlertDialog(
            title=ft.Text("ترخيص منتهي", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Text("انتهت صلاحية الترخيص.\nسيتم إغلاق التطبيق."),
            actions=[ft.TextButton("إغلاق", on_click=close_app_after_dialog)],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.open(dlg)

    async def close_app_async():
        logger.info("إغلاق التطبيق...")
        stop_license_checker()
        try:
            from flask_server import stop_flask_server
            stop_flask_server()
        except:
            pass
        try:
            if hasattr(page.window, 'close') and callable(page.window.close):
                page.window.close()
        except Exception as e:
            logger.error(f"خطأ أثناء إغلاق النافذة: {e}")

    def close_app():
        asyncio.create_task(close_app_async())

    def show_error(message):
        logger.error(f"عرض خطأ فادح: {message}")
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
        handle_exception(page, e, "خطأ في تشغيل التطبيق")

if __name__ == "__main__":
    # توجيه الأخطاء غير المعالجة إلى logger
    sys.excepthook = lambda exctype, value, tb: logger.critical("Unhandled exception", exc_info=(exctype, value, tb))
    ft.app(target=main)
