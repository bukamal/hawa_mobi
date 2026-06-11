# -*- coding: utf-8 -*-
import flet as ft
import asyncio
from views.flet_compat import ARABIC_FONT_FAMILY

class SplashView(ft.Container):
    def __init__(self, page, on_complete, on_error):
        super().__init__()
        self._page = page
        self.on_complete = on_complete
        self.on_error = on_error
        self.expand = True
        self.alignment = ft.Alignment.CENTER
        self.bgcolor = ft.Colors.INDIGO
        self.logo = ft.Text("هوى الشام", size=36, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER, font_family=ARABIC_FONT_FAMILY)
        self.subtitle = ft.Text("نظام الحسابات الداخلية", size=14, color=ft.Colors.WHITE_70, text_align=ft.TextAlign.CENTER, font_family=ARABIC_FONT_FAMILY)
        self.progress = ft.ProgressBar(width=300, bgcolor=ft.Colors.WHITE_24, color=ft.Colors.WHITE, value=0)
        self.status = ft.Text("جاري تهيئة النظام...", size=12, color=ft.Colors.WHITE_70, text_align=ft.TextAlign.CENTER, font_family=ARABIC_FONT_FAMILY)
        self.content = ft.Column(
            controls=[self.logo, ft.Container(height=10), self.subtitle, ft.Container(height=30),
                      self.progress, ft.Container(height=10), self.status],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        asyncio.create_task(self._load_sequence())

    async def _load_sequence(self):
        steps = [
            (0.1, "جاري تهيئة قاعدة البيانات..."),
            (0.3, "التحقق من الترخيص..."),
            (0.5, "تحميل الإعدادات..."),
            (0.7, "تهيئة العملات..."),
            (0.9, "جاري التحضير..."),
            (1.0, "اكتمل!"),
        ]
        for progress, message in steps:
            self.progress.value = progress
            self.status.value = message
            await asyncio.sleep(0.3)
            self._page.update()
        await asyncio.sleep(0.5)
        self.on_complete()
