from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Iterable, Optional

from flet.core.control import Control


class NotificationAction:
    def __init__(self, action_id: str, title: str, *, destructive: bool = False, foreground: bool = True):
        self.id = str(action_id)
        self.title = str(title)
        self.destructive = bool(destructive)
        self.foreground = bool(foreground)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "destructive": self.destructive,
            "foreground": self.foreground,
        }


class LocalNotifications(Control):
    """Non-visual Flet extension backed by flutter_local_notifications.

    The extension deliberately uses inexact-while-idle scheduling for payment
    reminders.  Financial reminders do not need exact-alarm privileges and the
    operating system may deliver them within a small maintenance window.
    """

    def __init__(
        self,
        *,
        on_notification_action: Optional[Callable] = None,
        tooltip: Optional[str] = None,
        visible: Optional[bool] = None,
        data: Any = None,
    ):
        super().__init__(tooltip=tooltip, visible=visible, data=data)
        self.on_notification_action = on_notification_action

    def _get_control_name(self):
        return "flet_notifications"

    def build(self):
        self._add_event_handler("notification_action", self._notification_action_handler)
        super().build()

    async def _notification_action_handler(self, event):
        callback = self.on_notification_action
        if callback is None:
            return
        try:
            raw = getattr(event, "data", "") or "{}"
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
            result = callback(data.get("actionId") or "tap", data.get("payload") or "")
            if hasattr(result, "__await__"):
                await result
        except Exception as ex:
            print(f"[WARN] notification action callback failed: {ex}")

    @staticmethod
    def _actions(actions: Optional[Iterable[NotificationAction]]) -> str:
        return json.dumps([a.as_dict() for a in (actions or [])], ensure_ascii=False)

    async def initialize(self) -> bool:
        return (await self.invoke_method_async("initialize", {})) == "ok"

    async def show_notification(
        self,
        notification_id: int,
        title: str,
        body: str,
        *,
        payload: str = "",
        channel_id: str = "hawaa_due_today",
        channel_name: str = "استحقاقات اليوم",
        channel_description: str = "تنبيهات المطالبات المستحقة اليوم",
        importance: str = "high",
        privacy: str = "private",
        group_key: str = "hawaa_payments",
        actions: Optional[Iterable[NotificationAction]] = None,
    ) -> bool:
        args = {
            "id": str(int(notification_id)), "title": str(title), "body": str(body),
            "payload": payload or "", "channel_id": channel_id,
            "channel_name": channel_name, "channel_description": channel_description,
            "importance": importance, "privacy": privacy, "group_key": group_key,
            "actions": self._actions(actions),
        }
        return (await self.invoke_method_async("show_notification", args)) == "ok"

    async def schedule_notification(
        self,
        notification_id: int,
        title: str,
        body: str,
        scheduled_date: datetime,
        *,
        payload: str = "",
        channel_id: str = "hawaa_due_soon",
        channel_name: str = "استحقاقات قريبة",
        channel_description: str = "تنبيهات المطالبات التي اقترب موعدها",
        importance: str = "default",
        privacy: str = "private",
        group_key: str = "hawaa_payments",
        actions: Optional[Iterable[NotificationAction]] = None,
    ) -> bool:
        args = {
            "id": str(int(notification_id)), "title": str(title), "body": str(body),
            "scheduled_date": scheduled_date.isoformat(), "payload": payload or "",
            "channel_id": channel_id, "channel_name": channel_name,
            "channel_description": channel_description, "importance": importance,
            "privacy": privacy, "group_key": group_key,
            "actions": self._actions(actions),
        }
        return (await self.invoke_method_async("schedule_notification", args)) == "ok"

    async def cancel(self, notification_id: int) -> bool:
        return (await self.invoke_method_async("cancel", {"id": str(int(notification_id))})) == "ok"

    async def cancel_all(self) -> bool:
        return (await self.invoke_method_async("cancel_all", {})) == "ok"

    async def pending_notifications(self) -> list[dict]:
        raw = await self.invoke_method_async("pending_notifications", {}) or "[]"
        try:
            return list(json.loads(raw))
        except Exception:
            return []

    async def active_notifications(self) -> list[dict]:
        raw = await self.invoke_method_async("active_notifications", {}) or "[]"
        try:
            return list(json.loads(raw))
        except Exception:
            return []

    async def request_permissions(self) -> bool:
        return str(await self.invoke_method_async("request_permissions", {})).lower() == "true"

    async def are_notifications_enabled(self) -> bool:
        return str(await self.invoke_method_async("are_notifications_enabled", {})).lower() == "true"

    async def launch_details(self) -> dict:
        raw = await self.invoke_method_async("launch_details", {}) or "{}"
        try:
            return dict(json.loads(raw))
        except Exception:
            return {}
