# -*- coding: utf-8 -*-
"""User-friendly Android network diagnostics for Windows pairing/client mode."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class DiagnosticHint:
    title: str
    message: str
    technical: str = ""


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def classify_connection_error(url: str, exc_or_message) -> DiagnosticHint:
    """Convert requests/urllib exceptions into Arabic messages fit for UI."""
    text = str(exc_or_message or "")
    lower = text.lower()
    host = _host_of(url)
    same_device_hosts = {"127.0.0.1", "localhost", "0.0.0.0"}  # nosec B104 - address comparison/normalization, not socket binding

    if "network is unreachable" in lower or "errno 101" in lower:
        return DiagnosticHint(
            "الشبكة غير قابلة للوصول",
            "الهاتف لا يرى هذا العنوان. تأكد أن الهاتف والكمبيوتر على نفس الشبكة، أو استخدم عنوان الخادم الصحيح من صفحة Windows.",
            text,
        )
    if "timed out" in lower or "read timed out" in lower or "connecttimeout" in lower:
        return DiagnosticHint(
            "انتهت مهلة الاتصال",
            "العنوان صحيح شكليًا لكن الخادم لا يرد. تأكد أن خادم Windows يعمل، وأن جدار الحماية يسمح بالمنفذ 8000.",
            text,
        )
    if "connection refused" in lower or "errno 111" in lower:
        return DiagnosticHint(
            "الخادم رفض الاتصال",
            "الجهاز وصل إلى العنوان، لكن لا يوجد خادم يعمل على هذا المنفذ. شغّل الخادم من إعدادات Windows ثم أعد الاختبار.",
            text,
        )
    if host in same_device_hosts:
        return DiagnosticHint(
            "عنوان محلي",
            "هذا العنوان يصلح فقط إذا كان Android وWindows يعملان على نفس الجهاز/المحاكي. للهاتف الحقيقي استخدم IP الكمبيوتر مثل 192.168.x.x.",
            text,
        )
    return DiagnosticHint(
        "تعذر الاتصال بالخادم",
        "افتح الرابط من متصفح الهاتف أولًا: /api/health. إذا لم يفتح، فالمشكلة شبكة أو جدار حماية وليست من التطبيق.",
        text,
    )


def build_diagnostic_steps(url: str) -> list[str]:
    host = _host_of(url)
    steps = [
        "افتح على Windows: الإعدادات ← الشبكة وتأكد أن الحالة: الخادم يعمل.",
        f"افتح من متصفح الهاتف: {url.rstrip('/')}/api/health",
        "تأكد أن الهاتف والكمبيوتر على نفس Wi‑Fi أو نفس نقطة الاتصال.",
        "اسمح للمنفذ 8000 في جدار الحماية على Windows.",
    ]
    if host in {"127.0.0.1", "localhost", "0.0.0.0"}:  # nosec B104 - address comparison/normalization, not socket binding
        steps.append(
            "للهاتف الحقيقي لا تستخدم localhost؛ استخدم IP الكمبيوتر داخل الشبكة."
        )
    if host.startswith("192.168.43."):
        steps.append(
            "عنوان 192.168.43.x غالبًا من Hotspot. تأكد أن الجهازين متصلان بنفس نقطة الاتصال وأن عزل العملاء غير مفعل."
        )
    return steps


def can_open_tcp(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, "اتصال TCP ناجح"
    except Exception as exc:
        return False, str(exc)
