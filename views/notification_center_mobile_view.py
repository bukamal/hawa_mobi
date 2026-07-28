# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import flet as ft

from database.repositories.local_notification_repo import LocalNotificationRepository
from services.local_notification_manager import get_local_notification_manager, attach_local_notifications
from views.flet_compat import run_async_task, show_snackbar
from views.ui_kit import (
    page_header, data_card, empty_state, PRIMARY, PRIMARY_SOFT, TEXT, MUTED,
    SUCCESS, WARNING, DANGER, BORDER,
)


class NotificationCenterMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.settings = LocalNotificationRepository()
        self.manager = get_local_notification_manager(page) or attach_local_notifications(page)

        self.enabled = ft.Switch(
            label="تشغيل تنبيهات الاستحقاق المحلية",
            value=self.settings.get_setting("notifications/enabled", "true") == "true",
        )
        self.time_field = ft.TextField(
            label="وقت التنبيه اليومي",
            value=self.settings.get_setting("notifications/time", "09:00"),
            hint_text="09:00",
            width=170,
            text_align=ft.TextAlign.CENTER,
        )
        self.pre_days = ft.Dropdown(
            label="التذكير قبل الاستحقاق",
            value=self.settings.get_setting("notifications/pre_due_days", "3"),
            width=210,
            options=[
                ft.dropdown.Option("1", "قبل يوم"),
                ft.dropdown.Option("2", "قبل يومين"),
                ft.dropdown.Option("3", "قبل 3 أيام"),
                ft.dropdown.Option("5", "قبل 5 أيام"),
                ft.dropdown.Option("7", "قبل 7 أيام"),
            ],
        )
        self.privacy = ft.Dropdown(
            label="خصوصية شاشة القفل",
            value=self.settings.get_setting("notifications/lockscreen_privacy", "private"),
            width=230,
            options=[
                ft.dropdown.Option("private", "إخفاء التفاصيل عند القفل"),
                ft.dropdown.Option("public", "إظهار الاسم والمبلغ"),
                ft.dropdown.Option("secret", "إشعار عام دون تفاصيل"),
            ],
        )
        self.status_host = ft.Container()
        self.list_host = ft.Column(spacing=9)
        self.controls = [
            page_header(
                "مركز التنبيهات",
                icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED,
                subtitle="تنبيهات محلية مجدولة تعمل حتى عند إغلاق التطبيق",
            ),
            self.status_host,
            self._settings_card(),
            ft.Row([
                ft.FilledButton(
                    "حفظ وإعادة الجدولة", icon=ft.Icons.SAVE_OUTLINED,
                    on_click=self._save, height=44,
                ),
                ft.OutlinedButton(
                    "اختبار الآن", icon=ft.Icons.NOTIFICATION_ADD_OUTLINED,
                    on_click=self._test, height=44,
                ),
            ], spacing=8, wrap=True),
            ft.Text("التنبيهات المجدولة", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
            self.list_host,
            ft.Container(height=24),
        ]
        self.reload()

    def _settings_card(self):
        return data_card(
            ft.Column([
                self.enabled,
                ft.Row([self.time_field, self.pre_days], spacing=10, wrap=True),
                self.privacy,
                ft.Text(
                    "التسلسل الافتراضي: قبل الاستحقاق، يوم الاستحقاق، ثم بعد التأخير بـ3 و7 أيام. "
                    "لا يستخدم التطبيق صلاحية المنبه الدقيق.",
                    size=11, color=MUTED,
                ),
            ], spacing=10),
            elevation=0,
        )

    def _status_card(self):
        native = bool(getattr(self.manager, "available", False))
        permission = getattr(self.manager, "permission_granted", None)
        if not native:
            label, color, icon = "الإضافة الأصلية غير متاحة في هذا البناء", DANGER, ft.Icons.ERROR_OUTLINE
        elif permission is True:
            label, color, icon = "الإشعارات مفعّلة على الجهاز", SUCCESS, ft.Icons.CHECK_CIRCLE_OUTLINE
        elif permission is False:
            label, color, icon = "يلزم منح إذن الإشعارات من Android", WARNING, ft.Icons.NOTIFICATIONS_OFF_OUTLINED
        else:
            label, color, icon = "جارٍ التحقق من إذن الإشعارات", PRIMARY, ft.Icons.SYNC_OUTLINED
        return data_card(
            ft.Row([
                ft.Container(ft.Icon(icon, color=color, size=24), bgcolor=PRIMARY_SOFT, padding=11, border_radius=14),
                ft.Column([
                    ft.Text(label, size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        f"آخر مزامنة: {getattr(self.manager, 'last_sync_at', '') or '—'}",
                        size=11, color=MUTED,
                    ),
                    ft.Text(
                        str(getattr(self.manager, "last_error", "") or ""),
                        size=10, color=DANGER,
                        visible=bool(getattr(self.manager, "last_error", "")),
                    ),
                ], spacing=2, expand=True),
                ft.OutlinedButton(
                    "منح الإذن", icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED,
                    on_click=self._request_permission,
                    visible=native and permission is not True,
                ),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            elevation=0,
        )

    def reload(self):
        self.status_host.content = self._status_card()
        try:
            rows = LocalNotificationRepository().list_all()
        except Exception as ex:
            self.list_host.controls = [empty_state("تعذر تحميل التنبيهات", str(ex), ft.Icons.ERROR_OUTLINE)]
            return
        if not rows:
            self.list_host.controls = [empty_state(
                "لا توجد تنبيهات مجدولة",
                "أضف تاريخ استحقاق إلى قيد أو خدمة ثم اضغط حفظ وإعادة الجدولة",
                ft.Icons.NOTIFICATIONS_NONE_OUTLINED,
            )]
            return
        self.list_host.controls = [self._notification_card(row) for row in rows]

    def _notification_card(self, row):
        status = str(row.get("status") or "planned")
        status_label = {
            "scheduled": "مجدول",
            "planned": "بانتظار الإذن",
            "shown": "ظهر على الجهاز",
            "opened": "تم فتحه",
            "failed": "فشل",
        }.get(status, status)
        color = DANGER if status == "failed" else (SUCCESS if status in {"shown", "opened"} else PRIMARY)
        scheduled = str(row.get("scheduled_at") or "").replace("T", " ")[:16]
        return data_card(
            ft.Row([
                ft.Container(
                    ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=color, size=22),
                    bgcolor=PRIMARY_SOFT, padding=10, border_radius=13,
                ),
                ft.Column([
                    ft.Text(str(row.get("title") or "تنبيه"), size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(str(row.get("body") or ""), size=11, color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{scheduled} · {status_label}", size=10, color=color),
                ], spacing=3, expand=True),
            ], spacing=10),
            elevation=0,
        )

    def _valid_time(self, value):
        try:
            dt.datetime.strptime(str(value).strip(), "%H:%M")
            return True
        except Exception:
            return False

    def _save(self, _=None):
        if not self._valid_time(self.time_field.value):
            show_snackbar(self._page, "أدخل الوقت بصيغة HH:MM مثل 09:00", is_error=True)
            return
        self.settings.set_setting("notifications/enabled", "true" if self.enabled.value else "false")
        self.settings.set_setting("notifications/time", str(self.time_field.value).strip())
        self.settings.set_setting("notifications/pre_due_days", str(self.pre_days.value or "3"))
        self.settings.set_setting("notifications/overdue_days", "3,7")
        self.settings.set_setting("notifications/lockscreen_privacy", str(self.privacy.value or "private"))

        async def apply():
            if self.enabled.value:
                await self.manager.request_permission()
                stats = await self.manager.resync(force=True)
                message = f"تمت إعادة الجدولة: {stats.get('scheduled', 0)} مجدول، {stats.get('shown', 0)} فوري"
            else:
                await self.manager.cancel_all()
                message = "تم إيقاف وإلغاء التنبيهات المحلية"
            self.reload()
            try:
                self._page.update()
            except Exception:
                pass
            show_snackbar(self._page, message, is_error=False)

        run_async_task(self._page, apply)

    def _request_permission(self, _=None):
        async def request():
            granted = await self.manager.request_permission()
            self.reload()
            try:
                self._page.update()
            except Exception:
                pass
            show_snackbar(self._page, "تم منح الإذن" if granted else "لم يُمنح إذن الإشعارات", is_error=not granted)
        run_async_task(self._page, request)

    def _test(self, _=None):
        async def test():
            ok = await self.manager.show_test_notification()
            self.reload()
            try:
                self._page.update()
            except Exception:
                pass
            show_snackbar(self._page, "تم إرسال إشعار اختبار" if ok else "تعذر إرسال إشعار الاختبار", is_error=not ok)
        run_async_task(self._page, test)
