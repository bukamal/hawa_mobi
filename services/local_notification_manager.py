# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Optional

from database import ExpenseRepository
from database.repositories.local_notification_repo import LocalNotificationRepository
from services.local_notification_planner import PlannedNotification, build_notification_plan

try:
    from flet_notifications import LocalNotifications, NotificationAction
except Exception:  # Desktop tests and source-only analysis can run without the extension.
    LocalNotifications = None
    NotificationAction = None


class LocalNotificationCoordinator:
    """Coordinates SQLite reminders with Android's native alarm store."""

    def __init__(self, page):
        self.page = page
        self.native = None
        self.available = LocalNotifications is not None
        self.permission_granted: Optional[bool] = None
        self.last_error = ""
        self.last_sync_at = ""
        self._sync_lock = asyncio.Lock()
        self._wake_event: asyncio.Event | None = None
        self._background_started = False

    def attach(self):
        if self.available and self.native is None:
            self.native = LocalNotifications(on_notification_action=self._on_notification_action)
            try:
                self.page.overlay.append(self.native)
                self.page.update()
            except Exception as ex:
                self.available = False
                self.last_error = str(ex)
        self._run_task(self.initialize())
        if not self._background_started:
            self._background_started = True
            self._run_task(self._background_loop())
        return self

    def _run_task(self, coroutine):
        try:
            from views.flet_compat import run_async_task
            return run_async_task(self.page, coroutine)
        except Exception:
            try:
                loop = asyncio.get_running_loop()
                return loop.create_task(coroutine)
            except Exception:
                return None

    async def initialize(self):
        if not self.available or self.native is None:
            return False
        try:
            await self.native.initialize()
            self.permission_granted = await self.native.are_notifications_enabled()
            details = await self.native.launch_details()
            if details.get("didLaunch") and details.get("payload"):
                await self._on_notification_action(details.get("actionId") or "tap", details.get("payload") or "")
            await self.resync(force=True)
            return True
        except Exception as ex:
            self.last_error = str(ex)
            return False

    async def request_permission(self) -> bool:
        if not self.available or self.native is None:
            self.last_error = "إضافة الإشعارات الأصلية غير متاحة في هذا البناء"
            return False
        try:
            self.permission_granted = bool(await self.native.request_permissions())
            LocalNotificationRepository().set_setting("notifications/permission_prompted", "true")
            if self.permission_granted:
                await self.resync(force=True)
            return self.permission_granted
        except Exception as ex:
            self.last_error = str(ex)
            return False

    def prompt_permission_if_needed(self):
        try:
            settings = LocalNotificationRepository()
            if settings.get_setting("notifications/enabled", "true") != "true":
                return
            if settings.get_setting("notifications/permission_prompted", "false") == "true":
                return
            if not self.available:
                return
            import flet as ft
            from views.flet_compat import open_control, close_control
            dialog = None

            def close(_=None):
                settings.set_setting("notifications/permission_prompted", "true")
                close_control(self.page, dialog)

            async def enable_async():
                granted = await self.request_permission()
                close_control(self.page, dialog)
                try:
                    from views.flet_compat import show_snackbar
                    show_snackbar(
                        self.page,
                        "تم تفعيل تنبيهات الاستحقاق" if granted else "لم يُمنح إذن الإشعارات",
                        is_error=not granted,
                    )
                except Exception:
                    pass

            def enable(_=None):
                self._run_task(enable_async())

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("تفعيل تنبيهات الاستحقاق", weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "ستظهر تنبيهات المطالبات القريبة والمتأخرة حتى عند إغلاق التطبيق. "
                    "يمكنك التحكم في الوقت والخصوصية من مركز التنبيهات."
                ),
                actions=[
                    ft.TextButton("ليس الآن", on_click=close),
                    ft.FilledButton("تفعيل الإشعارات", icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED, on_click=enable),
                ],
            )
            open_control(self.page, dialog)
        except Exception as ex:
            self.last_error = str(ex)

    async def _load_plan(self) -> list[PlannedNotification]:
        def load():
            settings = LocalNotificationRepository()
            if settings.get_setting("notifications/enabled", "true") != "true":
                return []
            rows = ExpenseRepository().get_pending_payment_reminders()
            return build_notification_plan(
                rows,
                notification_time=settings.get_setting("notifications/time", "09:00"),
                pre_due_days=settings.get_setting("notifications/pre_due_days", "3"),
                overdue_days=settings.get_setting("notifications/overdue_days", "3,7"),
                privacy=settings.get_setting("notifications/lockscreen_privacy", "private"),
            )
        return await asyncio.to_thread(load)

    async def resync(self, *, force: bool = False) -> dict:
        async with self._sync_lock:
            repo = LocalNotificationRepository()
            if not force and not repo.is_dirty():
                return {"scheduled": 0, "shown": 0, "cancelled": 0, "unchanged": 0}
            desired = await self._load_plan()
            existing = {row["notification_key"]: row for row in await asyncio.to_thread(repo.list_all)}
            desired_by_key = {item.key: item for item in desired}
            stats = {"scheduled": 0, "shown": 0, "cancelled": 0, "unchanged": 0}

            for key, old in list(existing.items()):
                item = desired_by_key.get(key)
                unchanged = item and (
                    old.get("scheduled_at") == item.scheduled_at.isoformat(timespec="seconds")
                    and old.get("title") == item.title
                    and old.get("body") == item.body
                    and old.get("status") in {"scheduled", "shown", "opened"}
                )
                if unchanged:
                    stats["unchanged"] += 1
                    continue
                if self.available and self.native is not None:
                    try:
                        await self.native.cancel(int(old["notification_id"]))
                    except Exception:
                        pass
                await asyncio.to_thread(repo.remove, key)
                stats["cancelled"] += 1

            now = dt.datetime.now()
            actions = []
            if NotificationAction is not None:
                actions = [
                    NotificationAction("open", "فتح المطالبة"),
                    NotificationAction("pay", "تسجيل دفعة"),
                ]
            for item in desired:
                old = existing.get(item.key)
                if old and old.get("status") in {"scheduled", "shown", "opened"} and (
                    old.get("scheduled_at") == item.scheduled_at.isoformat(timespec="seconds")
                    and old.get("title") == item.title and old.get("body") == item.body
                ):
                    continue
                if not self.available or self.native is None or self.permission_granted is False:
                    await asyncio.to_thread(repo.upsert, item, status="planned")
                    continue
                try:
                    if item.scheduled_at <= now:
                        ok = await self.native.show_notification(
                            item.notification_id, item.title, item.body,
                            payload=item.payload, channel_id=item.channel_id,
                            channel_name=item.channel_name,
                            channel_description=item.channel_description,
                            importance=item.importance, privacy=item.privacy,
                            actions=actions,
                        )
                        status = "shown" if ok else "failed"
                        stats["shown"] += int(ok)
                    else:
                        ok = await self.native.schedule_notification(
                            item.notification_id, item.title, item.body, item.scheduled_at,
                            payload=item.payload, channel_id=item.channel_id,
                            channel_name=item.channel_name,
                            channel_description=item.channel_description,
                            importance=item.importance, privacy=item.privacy,
                            actions=actions,
                        )
                        status = "scheduled" if ok else "failed"
                        stats["scheduled"] += int(ok)
                    await asyncio.to_thread(repo.upsert, item, status=status, last_error=None if ok else "native scheduling failed")
                except Exception as ex:
                    self.last_error = str(ex)
                    await asyncio.to_thread(repo.upsert, item, status="failed", last_error=str(ex))
            await asyncio.to_thread(repo.set_dirty, False)
            self.last_sync_at = dt.datetime.now().isoformat(timespec="seconds")
            return stats

    async def cancel_all(self):
        if self.available and self.native is not None:
            try:
                await self.native.cancel_all()
            except Exception as ex:
                self.last_error = str(ex)
        repo = LocalNotificationRepository()
        for row in await asyncio.to_thread(repo.list_all):
            await asyncio.to_thread(repo.remove, row["notification_key"])

    async def show_test_notification(self):
        if not self.available or self.native is None:
            self.last_error = "الإضافة الأصلية غير متاحة"
            return False
        if not await self.request_permission():
            return False
        return await self.native.show_notification(
            109000001,
            "اختبار تنبيهات هواء",
            "الإشعارات المحلية تعمل بصورة صحيحة على هذا الجهاز",
            payload=json.dumps({"route": "/notification_center"}),
            channel_id="hawaa_system",
            channel_name="النظام والمزامنة",
            channel_description="تنبيهات حالة التطبيق المحلية",
            importance="high",
            privacy="private",
            actions=[NotificationAction("open", "فتح المركز")] if NotificationAction else [],
        )

    async def _on_notification_action(self, action_id: str, payload: str):
        try:
            data = json.loads(payload or "{}")
        except Exception:
            data = {}
        notification_id = int(data.get("notification_id") or 0)
        if notification_id:
            try:
                await asyncio.to_thread(LocalNotificationRepository().mark_opened, notification_id)
            except Exception:
                pass
        expense_id = int(data.get("expense_id") or 0)
        try:
            setattr(self.page, "_hawaa_notification_focus_expense_id", expense_id or None)
            setattr(self.page, "_hawaa_notification_action", action_id or "open")
        except Exception:
            pass
        opener = getattr(self.page, "_hawaa_open_page", None)
        if callable(opener):
            opener("payment_reminders" if expense_id else "notification_center")

    async def _background_loop(self):
        await asyncio.sleep(3)
        last_full_sync = dt.datetime.min
        while True:
            try:
                if self._wake_event is None:
                    self._wake_event = asyncio.Event()
                try:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
                self._wake_event.clear()
                repo = LocalNotificationRepository()
                periodic_due = (dt.datetime.now() - last_full_sync).total_seconds() >= 300
                if repo.is_dirty() or periodic_due:
                    await self.resync(force=True)
                    last_full_sync = dt.datetime.now()
            except asyncio.CancelledError:
                return
            except Exception as ex:
                self.last_error = str(ex)
                await asyncio.sleep(10)

    def request_resync(self):
        try:
            LocalNotificationRepository().set_dirty(True)
        except Exception:
            pass
        if self._wake_event is not None:
            self._wake_event.set()
        else:
            self._run_task(self.resync(force=True))


def attach_local_notifications(page) -> LocalNotificationCoordinator:
    manager = getattr(page, "_hawaa_local_notifications", None)
    if isinstance(manager, LocalNotificationCoordinator):
        manager.attach()
        return manager
    manager = LocalNotificationCoordinator(page)
    setattr(page, "_hawaa_local_notifications", manager)
    return manager.attach()


def get_local_notification_manager(page) -> LocalNotificationCoordinator | None:
    manager = getattr(page, "_hawaa_local_notifications", None)
    return manager if isinstance(manager, LocalNotificationCoordinator) else None


def request_local_notification_resync(page=None):
    manager = get_local_notification_manager(page) if page is not None else None
    if manager is not None:
        manager.request_resync()
    else:
        try:
            LocalNotificationRepository().set_dirty(True)
        except Exception:
            pass
