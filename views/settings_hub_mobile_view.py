# -*- coding: utf-8 -*-
"""Modern settings information architecture with role-aware sections."""
from __future__ import annotations

import flet as ft

from auth.permissions import is_admin
from i18n.translator import translate
from views.ui_kit import (
    page_header, data_card, info_banner, PRIMARY, PRIMARY_SOFT, TEXT, MUTED,
)


class SettingsHubMobileView(ft.Column):
    def __init__(self, page, on_open):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.AUTO
        self._on_open = on_open
        admin = is_admin()

        sections = [
            ("appearance", "اللغة والمظهر", "اللغة، اتجاه الواجهة والمظهر", ft.Icons.PALETTE_OUTLINED),
        ]
        if admin:
            sections = [
                ("currency", "العملات", "العملة الأساسية وعملة العرض وتنسيق الأرقام", ft.Icons.PAID_OUTLINED),
                ("rates", "أسعار الصرف", "إدارة الأسعار وتحديثها ومراجعة تاريخها", ft.Icons.CURRENCY_EXCHANGE),
                ("company", "بيانات الشركة", "الاسم والشعار وبيانات التقارير الرسمية", ft.Icons.BUSINESS_OUTLINED),
                ("reports", "التقارير والطباعة", "قالب الكشف والأعمدة والملاحظات", ft.Icons.PRINT_OUTLINED),
                ("appearance", "اللغة والمظهر", "اللغة، اتجاه الواجهة والمظهر", ft.Icons.PALETTE_OUTLINED),
                ("network", "الاتصال والخادم", "وضع التشغيل، الخادم، QR والتشخيص", ft.Icons.LAN_OUTLINED),
                ("backup", "النسخ الاحتياطي", "النسخ والاستعادة وأدوات الإدارة", ft.Icons.CLOUD_SYNC_OUTLINED),
            ]

        subtitle = "إعدادات الحساب والمظهر" if not admin else "إعدادات النظام موزعة إلى أقسام واضحة"
        controls = [page_header(translate("settings"), ft.Icons.SETTINGS_OUTLINED, subtitle=subtitle)]
        if not admin:
            controls.append(info_banner(
                "الإعدادات المالية والشبكة والنسخ الاحتياطي محمية بصلاحية مدير النظام.",
                icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
            ))
        controls.extend(self._section_card(*section) for section in sections)
        controls.append(ft.Container(height=24))
        self.controls = controls

    def _section_card(self, section_id, title, subtitle, icon):
        return data_card(
            ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=PRIMARY, size=24),
                    bgcolor=PRIMARY_SOFT,
                    border_radius=15,
                    padding=12,
                ),
                ft.Column([
                    ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(subtitle, size=12, color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=3, expand=True),
                ft.Icon(ft.Icons.CHEVRON_LEFT, color=MUTED, size=22),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda e, sid=section_id: self._on_open(f"settings/{sid}"),
            elevation=0,
        )
