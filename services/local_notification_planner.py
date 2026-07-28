# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import json
import zlib
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PlannedNotification:
    key: str
    notification_id: int
    expense_id: int
    reminder_id: int
    kind: str
    scheduled_at: dt.datetime
    title: str
    body: str
    payload: str
    channel_id: str
    channel_name: str
    channel_description: str
    importance: str
    privacy: str


def _stable_id(key: str) -> int:
    # Android notification IDs are signed 32-bit integers. Keep zero unused.
    value = zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF
    return value or 1


def _parse_clock(value: str) -> tuple[int, int]:
    try:
        hour, minute = str(value or "09:00").strip().split(":", 1)
        hour_i, minute_i = int(hour), int(minute)
        if 0 <= hour_i <= 23 and 0 <= minute_i <= 59:
            return hour_i, minute_i
    except Exception:
        pass
    return 9, 0


def _parse_days(value: str, default: tuple[int, ...]) -> tuple[int, ...]:
    try:
        values = sorted({max(0, int(item.strip())) for item in str(value).split(",") if item.strip()})
        return tuple(values) or default
    except Exception:
        return default


def _money(value, code: str) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0.0
    text = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {code or 'USD'}"


def _source_label(row: dict) -> str:
    source = str(row.get("source_type") or "").strip()
    labels = {
        "direct_service_client": "خدمة مباشرة",
        "direct_service_supplier": "خدمة مباشرة",
        "service_case_client": "ملف خدمة",
        "service_case_supplier": "ملف خدمة",
        "normal": "قيد عادي",
    }
    return labels.get(source, str(row.get("service_type") or "مطالبة مالية"))


def build_notification_plan(
    rows: Iterable[dict],
    *,
    now: dt.datetime | None = None,
    notification_time: str = "09:00",
    pre_due_days: int | str = 3,
    overdue_days: str = "3,7",
    privacy: str = "private",
) -> list[PlannedNotification]:
    """Build deterministic local-notification milestones.

    For already elapsed milestones, only the most recent one is returned. This
    prevents a newly installed build from firing four notifications at once for
    a long-overdue claim. Future milestones remain scheduled normally.
    """
    now = now or dt.datetime.now()
    hour, minute = _parse_clock(notification_time)
    try:
        pre_days = max(0, int(pre_due_days))
    except Exception:
        pre_days = 3
    late_days = _parse_days(overdue_days, (3, 7))
    privacy = privacy if privacy in {"private", "public", "secret"} else "private"
    result: list[PlannedNotification] = []

    for raw in rows:
        row = dict(raw)
        try:
            expense_id = int(row.get("expense_id") or 0)
            reminder_id = int(row.get("id") or row.get("reminder_id") or 0)
            remaining = float(row.get("remaining_amount_original") or 0)
        except Exception:
            continue
        if expense_id <= 0 or remaining <= 0.005:
            continue
        due_text = str(row.get("reminder_date") or row.get("payment_due_date") or "")[:10]
        try:
            due_date = dt.datetime.strptime(due_text, "%Y-%m-%d").date()
        except Exception:
            continue

        due_at = dt.datetime.combine(due_date, dt.time(hour, minute))
        milestones: list[tuple[str, dt.datetime, str, str, str, str]] = []
        if pre_days:
            milestones.append((
                "due_soon", due_at - dt.timedelta(days=pre_days), "استحقاق قريب",
                "hawaa_due_soon", "استحقاقات قريبة", "default",
            ))
        milestones.append((
            "due_today", due_at, "استحقاق اليوم",
            "hawaa_due_today", "استحقاقات اليوم", "high",
        ))
        for days in late_days:
            milestones.append((
                f"overdue_{days}", due_at + dt.timedelta(days=days), "دفعة متأخرة",
                "hawaa_overdue", "مبالغ متأخرة", "high",
            ))
        milestones.sort(key=lambda item: item[1])
        elapsed = [item for item in milestones if item[1] <= now]
        selected = ([elapsed[-1]] if elapsed else []) + [item for item in milestones if item[1] > now]

        party = str(row.get("person_name") or row.get("company_name") or "طرف مالي").strip()
        company = str(row.get("company_name") or "").strip()
        code = str(row.get("currency_original") or "USD")
        source = _source_label(row)
        if privacy == "secret":
            body = "لديك مطالبة مالية تحتاج المتابعة داخل تطبيق هواء"
        else:
            company_part = f" · {company}" if company and company != party else ""
            body = f"{party}{company_part} · المتبقي {_money(remaining, code)} · {source}"

        for kind, scheduled_at, title, channel_id, channel_name, importance in selected:
            key = f"payment:{expense_id}:{kind}:{due_date.isoformat()}"
            notification_id = _stable_id(key)
            payload = json.dumps({
                "route": "/payment_reminders",
                "expense_id": expense_id,
                "reminder_id": reminder_id,
                "notification_id": notification_id,
                "kind": kind,
            }, ensure_ascii=False, separators=(",", ":"))
            result.append(PlannedNotification(
                key=key,
                notification_id=notification_id,
                expense_id=expense_id,
                reminder_id=reminder_id,
                kind=kind,
                scheduled_at=scheduled_at,
                title=title,
                body=body,
                payload=payload,
                channel_id=channel_id,
                channel_name=channel_name,
                channel_description={
                    "hawaa_due_soon": "تنبيهات المطالبات التي اقترب موعدها",
                    "hawaa_due_today": "تنبيهات المطالبات المستحقة اليوم",
                    "hawaa_overdue": "تنبيهات المبالغ المتأخرة",
                }[channel_id],
                importance=importance,
                privacy=privacy,
            ))
    return sorted(result, key=lambda item: (item.scheduled_at, item.notification_id))
