# -*- coding: utf-8 -*-
from __future__ import annotations

import flet as ft

from auth.permissions import access_denied_message
from auth.session import UserSession
from database import UserRepository
from i18n.translator import translate
from views.flet_compat import open_control, close_control, make_floating_action_button
from views.ui_kit import (
    page_header, summary_bar, metric_tile, data_card, pill, empty_state,
    action_text_button, show_snackbar, search_field, info_banner,
    PRIMARY, PRIMARY_SOFT, DANGER, MUTED, TEXT,
)


class UsersMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 8
        self.scroll = ft.ScrollMode.AUTO
        self._users = []

        if not UserSession.is_admin():
            self.controls = [
                page_header("إدارة المستخدمين", ft.Icons.GROUPS_OUTLINED),
                empty_state("وصول غير مسموح", access_denied_message(), ft.Icons.LOCK_OUTLINE),
            ]
            return

        self.add_btn = make_floating_action_button(
            icon=ft.Icons.PERSON_ADD, bgcolor=PRIMARY, foreground_color=ft.Colors.WHITE,
            on_click=self._add_user, tooltip=translate('add'), mini=False,
            elevation=6, shape=ft.CircleBorder(),
        )
        self._page.floating_action_button = self.add_btn
        self.search = search_field("بحث بالاسم أو اسم المستخدم", self._search_changed)
        self.summary = ft.Container()
        self.users_list = ft.Column(spacing=8)
        self.controls = [
            page_header("إدارة المستخدمين", ft.Icons.GROUPS_OUTLINED, subtitle="صلاحيات الدخول والحسابات"),
            info_banner("لا يمكن حذف المستخدم الحالي أو آخر مدير في النظام.", icon=ft.Icons.SECURITY_OUTLINED),
            self.search,
            self.summary,
            self.users_list,
            ft.Container(height=88),
        ]
        self._load_users()

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _role_meta(self, role):
        if role == 'admin':
            return translate('admin'), DANGER, ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED
        if role == 'user':
            return translate('user'), PRIMARY, ft.Icons.PERSON_OUTLINE
        return translate('viewer'), MUTED, ft.Icons.VISIBILITY_OUTLINED

    def _load_users(self):
        try:
            self._users = UserRepository().get_all()
            self._render_users(self._users)
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل المستخدمين: {ex}", True)

    def _search_changed(self, e):
        query = str(getattr(e.control, 'value', '') or '').strip().lower()
        if not query:
            self._render_users(self._users)
            return
        filtered = [u for u in self._users if query in str(u.get('username') or '').lower() or query in str(u.get('full_name') or '').lower()]
        self._render_users(filtered)

    def _render_users(self, users):
        admin_count = sum(1 for u in self._users if u.get('role') == 'admin')
        viewer_count = sum(1 for u in self._users if u.get('role') == 'viewer')
        self.summary.content = summary_bar([
            metric_tile("المستخدمون", ft.Text(str(len(self._users)), size=17, weight=ft.FontWeight.BOLD, color=PRIMARY)),
            metric_tile("المدراء", ft.Text(str(admin_count), size=17, weight=ft.FontWeight.BOLD, color=DANGER)),
            metric_tile("مشاهدة فقط", ft.Text(str(viewer_count), size=17, weight=ft.FontWeight.BOLD, color=MUTED)),
        ]).content
        self.summary.bgcolor = PRIMARY_SOFT
        self.summary.border_radius = 15
        self.summary.padding = 15
        self.summary.margin = ft.Margin(left=10, right=10, top=0, bottom=8)

        repo = UserRepository()
        cards = []
        for user in users:
            role_text, role_color, role_icon = self._role_meta(user.get('role'))
            created = (user.get('created_at') or '')[:10]
            last_login = (user.get('last_login') or 'لم يسجل بعد')[:10]
            can_delete, delete_reason = repo.can_delete(user['id'])
            cards.append(data_card(
                ft.Column([
                    ft.Row([
                        ft.Container(content=ft.Icon(role_icon, color=role_color, size=22), bgcolor=PRIMARY_SOFT, border_radius=14, padding=9),
                        ft.Column([
                            ft.Text(user.get('username', ''), size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                            ft.Text(user.get('full_name') or "بدون اسم كامل", size=12, color=MUTED),
                        ], spacing=2, expand=True),
                        pill(role_text, color=ft.Colors.WHITE, bgcolor=role_color),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([
                        ft.Text(f"تاريخ الإنشاء: {created}", size=11, color=MUTED),
                        ft.Text(f"آخر دخول: {last_login}", size=11, color=MUTED),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        action_text_button("تعديل", ft.Icons.EDIT_OUTLINED, lambda e, uid=user['id']: self._edit_user(uid)),
                        action_text_button("حذف", ft.Icons.DELETE_OUTLINE, lambda e, uid=user['id'], name=user.get('username',''): self._delete_user(uid, name), color=DANGER, visible=can_delete),
                        ft.IconButton(icon=ft.Icons.LOCK_OUTLINE, tooltip=delete_reason, visible=not can_delete, disabled=True),
                    ], alignment=ft.MainAxisAlignment.END),
                ], spacing=9), elevation=0,
            ))
        self.users_list.controls = cards or [empty_state("لا توجد نتائج", "غيّر عبارة البحث أو أضف مستخدمًا جديدًا", ft.Icons.GROUP_OFF)]
        try:
            self._page.update()
        except Exception:
            pass

    def _add_user(self, e):
        from views.dialogs.user_dialog import UserDialog
        open_control(self._page, UserDialog(page=self._page, on_save=self._load_users))

    def _edit_user(self, user_id):
        from views.dialogs.user_dialog import UserDialog
        open_control(self._page, UserDialog(page=self._page, user_id=user_id, on_save=self._load_users))

    def _delete_user(self, user_id, username):
        repo = UserRepository()
        allowed, reason = repo.can_delete(user_id)
        if not allowed:
            self._show_snackbar(reason, True)
            return

        def confirm_delete(e):
            try:
                repo.delete(user_id)
                self._show_snackbar(f"تم حذف المستخدم {username}", False)
                self._load_users()
            except Exception as ex:
                self._show_snackbar(str(ex), True)
            finally:
                close_control(self._page, dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("حذف مستخدم", color=DANGER, weight=ft.FontWeight.BOLD),
            content=ft.Text(f"سيتم حذف حساب «{username}». لا يؤثر ذلك في القيود التاريخية المنسوبة إليه. هل تريد المتابعة؟"),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda e: close_control(self._page, dlg)),
                ft.FilledButton("حذف المستخدم", bgcolor=DANGER, color=ft.Colors.WHITE, on_click=confirm_delete),
            ],
        )
        open_control(self._page, dlg)
