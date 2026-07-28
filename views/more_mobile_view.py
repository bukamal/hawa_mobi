# -*- coding: utf-8 -*-
"""Unified 'More' hub used by phone bottom navigation and large-screen rail."""
from __future__ import annotations

import flet as ft
from auth.session import UserSession
from i18n.translator import translate
from views.ui_kit import (
    page_header, data_card, PRIMARY, PRIMARY_SOFT, TEXT, MUTED, DANGER,
)


class MoreMobileView(ft.Column):
    def __init__(self, page, on_open, on_change_password, on_logout):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 12
        self.scroll = ft.ScrollMode.AUTO
        self.on_open = on_open
        current = UserSession.get_current() or {}
        role = current.get("role") or "user"
        name = current.get("full_name") or current.get("username") or translate("login")

        items = []
        if role == "admin":
            items.extend([
                self._item("المستخدمون", "إدارة الحسابات والأدوار", ft.Icons.PEOPLE_OUTLINE, lambda e: on_open("users")),
                self._item("سجل التدقيق", "تتبّع العمليات والتغييرات الحساسة", ft.Icons.FACT_CHECK_OUTLINED, lambda e: on_open("audit_log")),
            ])
        settings_subtitle = "المظهر وإعدادات الحساب" if role != "admin" else "النظام والعملات والتقارير والاتصال"
        items.extend([
            self._item("متابعة الدفعات", "الإجمالي والمدفوع والمتبقي والتذكيرات", ft.Icons.PAYMENTS_OUTLINED, lambda e: on_open("payment_reminders")),
            self._item("مركز التنبيهات", "إشعارات الاستحقاق المحلية وحالة الجدولة", ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED, lambda e: on_open("notification_center")),
            self._item(translate("settings"), settings_subtitle, ft.Icons.SETTINGS_OUTLINED, lambda e: on_open("settings")),
            self._item(translate("change_password"), "تحديث كلمة مرور الحساب الحالي", ft.Icons.LOCK_RESET, on_change_password),
            self._item(translate("logout"), "إنهاء الجلسة على هذا الجهاز", ft.Icons.LOGOUT, on_logout, danger=True),
        ])

        profile = data_card(
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.PERSON, color=PRIMARY, size=28),
                    bgcolor=PRIMARY_SOFT,
                    border_radius=18,
                    padding=13,
                ),
                ft.Column([
                    ft.Text(name, size=17, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(self._role_label(role), size=12, color=MUTED),
                ], spacing=3, expand=True),
            ], spacing=12),
            elevation=0,
        )

        self.controls = [
            page_header("المزيد", icon=ft.Icons.MORE_HORIZ, subtitle="الإدارة والحساب والإعدادات"),
            profile,
            *items,
            ft.Container(height=20),
        ]

    @staticmethod
    def _role_label(role):
        return {"admin": "مدير النظام", "viewer": "مشاهدة فقط", "user": "مستخدم"}.get(role, str(role))

    @staticmethod
    def _item(title, subtitle, icon, on_click, danger=False):
        color = DANGER if danger else PRIMARY
        return data_card(
            ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=color, size=23),
                    bgcolor="#FDECEC" if danger else PRIMARY_SOFT,
                    border_radius=14,
                    padding=11,
                ),
                ft.Column([
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=DANGER if danger else TEXT),
                    ft.Text(subtitle, size=12, color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=3, expand=True),
                ft.Icon(ft.Icons.CHEVRON_LEFT, color=MUTED, size=21),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=on_click,
            elevation=0,
        )
