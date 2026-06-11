# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import flet as ft
from auth.activation import activate, get_device_id, get_license_details


class ActivationView(ft.Container):
    def __init__(self, page, on_success, on_cancel):
        super().__init__()
        self._page = page
        self.on_success = on_success
        self.on_cancel = on_cancel
        self._busy = False
        self.expand = True
        self.alignment = ft.Alignment.CENTER
        self.padding = 24

        details = get_license_details()
        self.device_id = get_device_id()
        self.key_field = ft.TextField(label='مفتاح الترخيص', hint_text='XXXX-XXXX-XXXX-XXXX', password=True, can_reveal_password=True, width=350, text_align=ft.TextAlign.CENTER)
        self.status_text = ft.Text(details.get('message') or '', color=ft.Colors.GREEN if details.get('activated') else ft.Colors.RED, size=12, text_align=ft.TextAlign.CENTER)
        self.license_info = ft.Text(self._format_license_info(details), size=11, color=ft.Colors.GREY_700, text_align=ft.TextAlign.CENTER, selectable=True)
        self.device_text = ft.Text(f'Device ID: {self.device_id[:12]}…{self.device_id[-8:]}', size=11, color=ft.Colors.GREY_600, selectable=True, text_align=ft.TextAlign.CENTER)
        self.progress = ft.ProgressBar(width=350, visible=False)
        self.activate_btn = ft.FilledButton(content=ft.Text('تفعيل', size=16, weight=ft.FontWeight.BOLD), width=350, height=45, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE, on_click=self._activate)
        self.copy_btn = ft.TextButton(content=ft.Text('نسخ رقم الجهاز'), on_click=self._copy_device_id)
        self.cancel_btn = ft.TextButton(content=ft.Text('إغلاق'), on_click=lambda e: self.on_cancel() if self.on_cancel else None)
        self.content = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text('🔐', size=48),
                        ft.Text('تفعيل نظام هوى الشام', size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO),
                        ft.Text('أدخل مفتاح الترخيص للتفعيل عبر الإنترنت', size=12, color=ft.Colors.GREY_600),
                        ft.Container(height=12),
                        self.license_info,
                        self.device_text,
                        self.copy_btn,
                        ft.Container(height=12),
                        self.key_field,
                        self.status_text,
                        self.progress,
                        ft.Container(height=12),
                        self.activate_btn,
                        self.cancel_btn,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=28,
                width=410,
            ),
            elevation=5,
        )

    def _format_license_info(self, details: dict) -> str:
        if not details.get('activated'):
            return 'حالة الترخيص: غير مفعل'
        expiration = details.get('expiration') or 'غير محدد'
        activated_at = details.get('activated_at') or 'غير محدد'
        preview = details.get('key_preview') or '****'
        return f'حالة الترخيص: مفعل\nالمفتاح: {preview}\nينتهي: {expiration}\nتاريخ التفعيل: {activated_at}'

    def _copy_device_id(self, e):
        try:
            self._page.set_clipboard(self.device_id)
            self.status_text.value = 'تم نسخ رقم الجهاز'
            self.status_text.color = ft.Colors.GREEN
        except Exception:
            self.status_text.value = self.device_id
            self.status_text.color = ft.Colors.BLUE
        self._page.update()

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.activate_btn.disabled = busy
        self.key_field.disabled = busy
        self.progress.visible = busy
        try:
            self.activate_btn.content.value = 'جاري التفعيل...' if busy else 'تفعيل'
        except Exception:
            pass

    def _activate(self, e):
        if self._busy:
            return
        key = (self.key_field.value or '').strip()
        if not key:
            self.status_text.value = 'يرجى إدخال مفتاح الترخيص'
            self.status_text.color = ft.Colors.RED
            self._page.update()
            return
        self._set_busy(True)
        self.status_text.value = 'جاري الاتصال بخادم التفعيل...'
        self.status_text.color = ft.Colors.BLUE
        self._page.update()
        try:
            success, msg = activate(key)
            if success:
                details = get_license_details()
                self.license_info.value = self._format_license_info(details)
                self.status_text.value = 'تم التفعيل بنجاح'
                self.status_text.color = ft.Colors.GREEN
                self._page.update()
                asyncio.create_task(self._delayed_success())
            else:
                self.status_text.value = f'فشل التفعيل: {msg}'
                self.status_text.color = ft.Colors.RED
        except Exception as ex:
            self.status_text.value = f'خطأ: {ex}'
            self.status_text.color = ft.Colors.RED
        finally:
            self._set_busy(False)
            try:
                self._page.update()
            except Exception:
                pass

    async def _delayed_success(self):
        await asyncio.sleep(1.0)
        self.on_success()
