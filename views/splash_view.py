# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sqlite3
import flet as ft

from auth.activation import check_activation
from auth.session import UserSession
from database.connection import DatabaseConnection, get_local_db_path
from views.flet_compat import ARABIC_FONT_FAMILY
from views.ui_kit import app_brand


class SplashView(ft.Container):
    def __init__(self, page, on_complete, on_error):
        super().__init__()
        self._page = page
        self.on_complete = on_complete
        self.on_error = on_error
        self.expand = True
        self.alignment = ft.Alignment.CENTER
        self.bgcolor = ft.Colors.INDIGO
        self.brand = app_brand('هوى الشام', 'نظام الحسابات الداخلية', size=104, dark=False)
        self.progress = ft.ProgressBar(width=300, bgcolor=ft.Colors.WHITE_24, color=ft.Colors.WHITE, value=0)
        self.status = ft.Text('جاري تهيئة النظام...', size=12, color=ft.Colors.WHITE_70, text_align=ft.TextAlign.CENTER, font_family=ARABIC_FONT_FAMILY)
        self.detail = ft.Text('', size=11, color=ft.Colors.WHITE_60, text_align=ft.TextAlign.CENTER, font_family=ARABIC_FONT_FAMILY)
        self.content = ft.Column(
            controls=[self.brand, ft.Container(height=30), self.progress, ft.Container(height=10), self.status, self.detail],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        asyncio.create_task(self._load_sequence())

    def _set_status(self, value: float, message: str, detail: str = ''):
        self.progress.value = value
        self.status.value = message
        self.detail.value = detail
        try:
            self._page.update()
        except Exception:
            pass

    async def _load_sequence(self):
        try:
            self._set_status(0.10, 'فحص قاعدة البيانات...')
            await asyncio.sleep(0.12)
            db_path = get_local_db_path()
            conn = sqlite3.connect(db_path)
            try:
                conn.execute('SELECT 1')
                conn.execute('SELECT key, value FROM settings LIMIT 1')
            finally:
                conn.close()

            self._set_status(0.35, 'قراءة إعدادات التشغيل...')
            await asyncio.sleep(0.12)
            db = DatabaseConnection()
            db.refresh_mode()
            mode = 'عميل شبكة' if db.is_remote() else 'محلي'

            if db.is_remote():
                self._set_status(0.55, 'فحص الاتصال بالخادم...', db.server_url)
                try:
                    health = db.get_rest_client().health()
                    if not isinstance(health, dict) or not health.get('ok'):
                        raise RuntimeError('استجابة الخادم غير صالحة')
                except Exception as exc:
                    self.on_error(f'تعذر الاتصال بالخادم قبل تسجيل الدخول: {exc}')
                    return
            else:
                self._set_status(0.55, 'وضع التشغيل المحلي جاهز', mode)

            self._set_status(0.72, 'التحقق من الترخيص...')
            await asyncio.sleep(0.12)
            activated, msg = check_activation()
            if not activated:
                self._set_status(1.0, 'يتطلب التفعيل', msg)
                await asyncio.sleep(0.2)
                self.on_complete({'activated': False, 'session': False, 'mode': mode})
                return

            self._set_status(0.88, 'فحص الجلسة الحالية...')
            await asyncio.sleep(0.12)
            has_session = UserSession.is_authenticated()
            self._set_status(1.0, 'اكتمل التحميل', 'سيتم استعادة الجلسة' if has_session else 'جاهز لتسجيل الدخول')
            await asyncio.sleep(0.25)
            self.on_complete({'activated': True, 'session': has_session, 'mode': mode})
        except Exception as exc:
            self.on_error(f'فشل فحص بدء التشغيل: {exc}')
