# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sqlite3
import flet as ft

from auth.activation import check_activation
from auth.session import UserSession
from database.connection import DatabaseConnection, get_local_db_path
from i18n.translator import translate
from views.flet_compat import ARABIC_FONT_FAMILY, ALIGN_CENTER, run_async_task
from views.ui_kit import (
    app_brand,
    brand_background,
    PRIMARY,
    PRIMARY_SOFT,
    ACCENT,
    TEXT,
    MUTED,
    BORDER,
    status_chip,
)


class SplashView(ft.Container):
    def __init__(self, page, on_complete, on_error):
        super().__init__()
        self._page = page
        self.on_complete = on_complete
        self.on_error = on_error
        self.expand = True
        self.alignment = ALIGN_CENTER

        # Use an opaque card on Android.  Some Flet Android runtimes render
        # 8-digit alpha hex colors incorrectly, which made the splash card
        # appear as a neon yellow block.  Keep the outer gradient, but make the
        # card itself solid and high-contrast.
        self.brand = app_brand(
            translate("app_name"), translate("app_subtitle"), size=96, dark=True
        )
        self.progress = ft.ProgressBar(
            width=300, bgcolor="#E4ECEA", color=ACCENT, value=0
        )
        self.status = ft.Text(
            "جاري تهيئة النظام...",
            size=13,
            color=TEXT,
            text_align=ft.TextAlign.CENTER,
            font_family=ARABIC_FONT_FAMILY,
            weight=ft.FontWeight.BOLD,
        )
        self.detail = ft.Text(
            "",
            size=11,
            color=MUTED,
            text_align=ft.TextAlign.CENTER,
            font_family=ARABIC_FONT_FAMILY,
        )
        self.mode_chip = status_chip(
            "تهيئة", icon=ft.Icons.HOURGLASS_EMPTY, color=PRIMARY, bgcolor=PRIMARY_SOFT
        )

        width = 430
        try:
            if getattr(page, "width", None):
                width = max(300, min(410, int(page.width) - 48))
        except Exception:
            pass

        card = ft.Container(
            content=ft.Column(
                controls=[
                    self.brand,
                    ft.Container(height=14),
                    self.mode_chip,
                    ft.Container(height=18),
                    self.progress,
                    ft.Container(height=8),
                    self.status,
                    self.detail,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            width=width,
            padding=26,
            border_radius=30,
            bgcolor="#FFFFFF",
            border=ft.Border(
                left=ft.BorderSide(1, BORDER),
                top=ft.BorderSide(1, BORDER),
                right=ft.BorderSide(1, BORDER),
                bottom=ft.BorderSide(1, BORDER),
            ),
            shadow=ft.BoxShadow(blur_radius=22, spread_radius=1, color="#20302D"),
        )
        self.content = brand_background(card, padding=24, dark=True)
        run_async_task(self._page, self._load_sequence)

    def _set_status(
        self, value: float, message: str, detail: str = "", mode: str | None = None
    ):
        self.progress.value = value
        self.status.value = message
        self.detail.value = detail
        if mode:
            try:
                self.mode_chip.content.controls[-1].value = mode
            except Exception:
                pass
        try:
            self._page.update()
        except Exception:
            pass

    async def _load_sequence(self):
        try:
            self._set_status(0.10, "فحص قاعدة البيانات...", mode="قاعدة البيانات")
            await asyncio.sleep(0.12)
            db_path = get_local_db_path()
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("SELECT 1")
                conn.execute("SELECT key, value FROM settings LIMIT 1")
            finally:
                conn.close()

            self._set_status(0.34, "قراءة إعدادات التشغيل...", mode="الإعدادات")
            await asyncio.sleep(0.12)
            db = DatabaseConnection()
            db.refresh_mode()
            mode = "عميل شبكة" if db.is_remote() else "محلي"

            if db.is_remote():
                self._set_status(
                    0.55, "فحص الاتصال بالخادم...", db.server_url, mode="عميل شبكة"
                )
                try:
                    health = db.get_rest_client().health()
                    if not isinstance(health, dict) or not health.get("ok"):
                        raise RuntimeError("استجابة الخادم غير صالحة")
                except Exception as exc:
                    self.on_error(f"تعذر الاتصال بالخادم قبل تسجيل الدخول: {exc}")
                    return
            else:
                self._set_status(0.55, "وضع التشغيل المحلي جاهز", mode, mode="محلي")

            self._set_status(0.72, "التحقق من الترخيص...", mode="الترخيص")
            await asyncio.sleep(0.12)
            activated, msg = check_activation()
            if not activated:
                self._set_status(1.0, "يتطلب التفعيل", msg, mode="تفعيل مطلوب")
                await asyncio.sleep(0.2)
                self.on_complete({"activated": False, "session": False, "mode": mode})
                return

            self._set_status(0.88, "فحص الجلسة الحالية...", mode="الجلسة")
            await asyncio.sleep(0.12)
            has_session = UserSession.is_authenticated()
            self._set_status(
                1.0,
                "اكتمل التحميل",
                "سيتم استعادة الجلسة" if has_session else "جاهز لتسجيل الدخول",
                mode="جاهز",
            )
            await asyncio.sleep(0.25)
            self.on_complete({"activated": True, "session": has_session, "mode": mode})
        except Exception as exc:
            self.on_error(f"فشل فحص بدء التشغيل: {exc}")
