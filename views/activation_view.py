# -*- coding: utf-8 -*-
import flet as ft
import asyncio
from auth.activation import activate

class ActivationView(ft.Container):
    def __init__(self, page, on_success, on_cancel):
        super().__init__()
        self._page = page
        self.on_success = on_success
        self.on_cancel = on_cancel
        self.expand = True
        self.alignment = ft.Alignment.CENTER
        self.padding = 30
        self.key_field = ft.TextField(label="مفتاح الترخيص", hint_text="XXXX-XXXX-XXXX-XXXX", password=True, can_reveal_password=True, width=350, text_align=ft.TextAlign.CENTER)
        self.status_text = ft.Text("", color=ft.Colors.RED, size=12)
        self.progress = ft.ProgressBar(width=350, visible=False)
        self.activate_btn = ft.FilledButton(content=ft.Text("تفعيل", size=16, weight=ft.FontWeight.BOLD), width=350, height=45, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._activate)
        self.cancel_btn = ft.TextButton(content=ft.Text("إلغاء"), on_click=lambda e: self.on_cancel() if self.on_cancel else None)
        self.content = ft.Card(content=ft.Container(content=ft.Column(controls=[
            ft.Text("🔐", size=48), ft.Text("تفعيل نظام هوى الشام", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO),
            ft.Text("أدخل مفتاح الترخيص للتفعيل عبر الإنترنت", size=12, color=ft.Colors.GREY_600), ft.Container(height=20),
            self.key_field, self.status_text, self.progress, ft.Container(height=15), self.activate_btn, self.cancel_btn
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True), padding=30, width=400), elevation=5)

    def _activate(self, e):
        key = self.key_field.value.strip()
        if not key:
            self.status_text.value = "يرجى إدخال مفتاح الترخيص"
            self.status_text.color = ft.Colors.RED
            self._page.update()
            return
        self.activate_btn.disabled = True
        self.progress.visible = True
        self.status_text.value = "جاري الاتصال بالخادم..."
        self.status_text.color = ft.Colors.BLUE
        self._page.update()
        try:
            success, msg = activate(key)
            self.progress.visible = False
            self.activate_btn.disabled = False
            if success:
                self.status_text.value = "تم التفعيل بنجاح!"
                self.status_text.color = ft.Colors.GREEN
                self._page.update()
                asyncio.create_task(self._delayed_success())
            else:
                self.status_text.value = f"فشل التفعيل: {msg}"
                self.status_text.color = ft.Colors.RED
                self._page.update()
        except Exception as ex:
            self.progress.visible = False
            self.activate_btn.disabled = False
            self.status_text.value = f"خطأ: {str(ex)}"
            self.status_text.color = ft.Colors.RED
            self._page.update()

    async def _delayed_success(self):
        await asyncio.sleep(1.5)
        self.on_success()
