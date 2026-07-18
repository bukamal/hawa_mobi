# -*- coding: utf-8 -*-
"""Central role-based access policy for Android/desktop presentation routes.

UI hiding is never treated as authorization.  Views and repository operations
use these helpers so a direct route or stale callback cannot bypass the policy.
"""
from __future__ import annotations

from auth.session import UserSession

ADMIN_ONLY_PAGES = {"users", "audit_log"}
ADMIN_SETTINGS_SECTIONS = {
    "currency", "rates", "company", "reports", "network", "backup",
}
PERSONAL_SETTINGS_SECTIONS = {"appearance"}


def current_role() -> str:
    user = UserSession.get_current() or {}
    return str(user.get("role") or "viewer")


def is_admin() -> bool:
    return current_role() == "admin"


def can_access_page(page_id: str) -> bool:
    page_id = str(page_id or "")
    if page_id in ADMIN_ONLY_PAGES:
        return is_admin()
    if page_id.startswith("settings/"):
        section = page_id.split("/", 1)[1]
        return can_access_settings_section(section)
    return True


def can_access_settings_section(section: str) -> bool:
    section = str(section or "appearance")
    if section in PERSONAL_SETTINGS_SECTIONS:
        return True
    if section in ADMIN_SETTINGS_SECTIONS:
        return is_admin()
    return False


def access_denied_message() -> str:
    return "ليس لديك صلاحية لتنفيذ هذا الإجراء. يلزم حساب مدير النظام."
