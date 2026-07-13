# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import flet as ft
from auth.activation import activate, get_device_id, get_license_details
from views.ui_kit import app_brand, brand_background, brand_card, status_chip, PRIMARY, MUTED, DANGER, SUCCESS, WARNING
from views.flet_compat import ALIGN_CENTER, run_async_task


class ActivationView(ft.Container):
    def __init__(self, page, on_success, on_cancel):
        super().__init__()
        self._page = page
        self.on_success = on_success
        self.on_cancel = on_cancel
        self._busy = False
        self.expand = True
        self.alignment = ALIGN_CENTER
        self.padding = 0

        details = get_license_details()
        self.device_id = get_device_id()
        self.status_chip = status_chip('مفعل' if details.get('activated') else 'غير مفعل', icon=ft.Icons.VERIFIED_USER, color=SUCCESS if details.get('activated') else DANGER, bgcolor="#E9F7F1" if details.get('activated') else "#FDECEC")
        self.key_field = ft.TextField(label='مفتاح الترخيص', hint_text='XXXX-XXXX-XXXX-XXXX', password=True, can_reveal_password=True, width=360, text_align=ft.TextAlign.CENTER, border_radius=14)
        self.status_text = ft.Text(details.get('message') or '', color=SUCCESS if details.get('activated') else DANGER, size=12, text_align=ft.TextAlign.CENTER)
        self.license_info = ft.Text(self._format_license_info(details), size=11, color=MUTED, text_align=ft.TextAlign.CENTER, selectable=True)
        self.device_text = ft.Text(f'معرّف الجهاز: {self.device_id[:12]}…{self.device_id[-8:]}', size=11, color=MUTED, selectable=True, text_align=ft.TextAlign.CENTER)
        self.path_text = ft.Text(details.get('license_file') or '', size=10, color=MUTED, selectable=True, text_align=ft.TextAlign.CENTER)
        self.progress = ft.ProgressBar(width=360, visible=False, color=PRIMARY)
        self.activate_btn = ft.FilledButton(content=ft.Text('تفعيل', size=16, weight=ft.FontWeight.BOLD), width=360, height=46, bgcolor=PRIMARY, color=ft.Colors.WHITE, on_click=self._activate)
        self.copy_btn = ft.OutlinedButton(content=ft.Text('نسخ معرّف الجهاز'), on_click=self._copy_device_id)
        self.refresh_btn = ft.OutlinedButton(content=ft.Text('تحديث الحالة'), on_click=self._refresh_status)
        self.cancel_btn = ft.TextButton(content=ft.Text('إغلاق', color=MUTED), on_click=lambda e: self.on_cancel() if self.on_cancel else None)

        form = ft.Column(
            controls=[
                app_brand('تفعيل هوى الشام', 'ربط الترخيص بهذا الجهاز', size=88, dark=True),
                self.status_chip,
                self.license_info,
                self.device_text,
                self.path_text,
                ft.Row([self.copy_btn, self.refresh_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Container(height=8),
                self.key_field,
                self.status_text,
                self.progress,
                self.activate_btn,
                self.cancel_btn,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=9,
        )
        self.content = brand_background(brand_card(form, width=450, padding=24), padding=18, dark=False)

    def _format_license_info(self, details: dict) -> str:
        if not details.get('activated'):
            msg = details.get('message') or 'غير مفعل'
            return f'حالة الترخيص: غير مفعل\nالسبب: {msg}'
        expiration = details.get('expiration') or 'غير محدد'
        activated_at = details.get('activated_at') or 'غير محدد'
        preview = details.get('key_preview') or '****'
        return f'حالة الترخيص: مفعل\nالمفتاح: {preview}\nينتهي: {expiration}\nتاريخ التفعيل: {activated_at}'

    def _refresh_status(self, e=None):
        details = get_license_details()
        self.status_chip.content.controls[-1].value = 'مفعل' if details.get('activated') else 'غير مفعل'
        self.license_info.value = self._format_license_info(details)
        self.path_text.value = details.get('license_file') or ''
        self.status_text.value = details.get('message') or ''
        self.status_text.color = SUCCESS if details.get('activated') else DANGER
        try:
            self._page.update()
        except Exception:
            pass

    def _copy_device_id(self, e):
        try:
            self._page.set_clipboard(self.device_id)
            self.status_text.value = 'تم نسخ معرّف الجهاز'
            self.status_text.color = SUCCESS
        except Exception:
            self.status_text.value = self.device_id
            self.status_text.color = PRIMARY
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
            self.status_text.color = WARNING
            self._page.update()
            return
        self._set_busy(True)
        self.status_text.value = 'جاري الاتصال بخادم التفعيل...'
        self.status_text.color = PRIMARY
        self._page.update()
        try:
            success, msg = activate(key)
            if success:
                self._refresh_status()
                self.status_text.value = 'تم التفعيل بنجاح'
                self.status_text.color = SUCCESS
                self._page.update()
                run_async_task(self._page, self._delayed_success)
            else:
                self.status_text.value = f'فشل التفعيل: {msg}'
                self.status_text.color = DANGER
        except Exception as ex:
            self.status_text.value = f'خطأ: {ex}'
            self.status_text.color = DANGER
        finally:
            self._set_busy(False)
            try:
                self._page.update()
            except Exception:
                pass

    async def _delayed_success(self):
        await asyncio.sleep(1.0)
        self.on_success()
