# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, make_floating_action_button
from views.ui_kit import page_header, summary_bar, metric_tile, data_card, pill, empty_state, action_text_button, show_snackbar
from database import UserRepository
from i18n.translator import translate


class UsersMobileView(ft.Column):
    def __init__(self, page):
        super().__init__()
        self._page = page
        self.expand = True
        self.spacing = 8
        self.scroll = ft.ScrollMode.AUTO

        self.add_btn = make_floating_action_button(
            icon=ft.Icons.PERSON_ADD,
            bgcolor=ft.Colors.INDIGO,
            foreground_color=ft.Colors.WHITE,
            on_click=self._add_user,
            tooltip=translate('add'),
            mini=False,
            elevation=6,
            shape=ft.CircleBorder(),
            margin=ft.Margin(left=0, right=16, top=0, bottom=80),
        )
        self._page.floating_action_button = self.add_btn

        self.summary = ft.Container()
        self.users_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.controls = [
            page_header("إدارة المستخدمين", ft.Icons.GROUPS, subtitle="صلاحيات الدخول والحسابات"),
            self.summary,
            self.users_list,
        ]
        self._load_users()

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _role_meta(self, role):
        if role == 'admin':
            return translate('admin'), ft.Colors.RED, ft.Icons.ADMIN_PANEL_SETTINGS
        if role == 'user':
            return translate('user'), ft.Colors.BLUE, ft.Icons.PERSON
        return translate('viewer'), ft.Colors.GREY, ft.Icons.VISIBILITY

    def _load_users(self):
        try:
            repo = UserRepository()
            users = repo.get_all()
            admin_count = sum(1 for u in users if u.get('role') == 'admin')
            viewer_count = sum(1 for u in users if u.get('role') == 'viewer')
            self.summary.content = summary_bar([
                metric_tile("المستخدمون", ft.Text(str(len(users)), size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)),
                metric_tile("المدراء", ft.Text(str(admin_count), size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)),
                metric_tile("مشاهدة فقط", ft.Text(str(viewer_count), size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)),
            ]).content
            self.summary.bgcolor = ft.Colors.INDIGO_50
            self.summary.border_radius = 15
            self.summary.padding = 15
            self.summary.margin = ft.Margin(left=10, right=10, top=0, bottom=8)

            cards = []
            for u in users:
                role_text, role_color, role_icon = self._role_meta(u.get('role'))
                created = (u.get('created_at') or '')[:10]
                last_login = (u.get('last_login') or 'لم يسجل بعد')[:10]
                card = data_card(
                    ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(role_icon, color=role_color, size=22),
                                bgcolor=ft.Colors.GREY_100,
                                border_radius=14,
                                padding=9,
                            ),
                            ft.Column([
                                ft.Text(u.get('username', ''), size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(u.get('full_name') or "بدون اسم كامل", size=12, color=ft.Colors.GREY_600),
                            ], spacing=2, expand=True),
                            pill(role_text, color=ft.Colors.WHITE, bgcolor=role_color),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([
                            ft.Text(f"تاريخ الإنشاء: {created}", size=11, color=ft.Colors.GREY_500),
                            ft.Text(f"آخر دخول: {last_login}", size=11, color=ft.Colors.GREY_500),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            action_text_button("تعديل", ft.Icons.EDIT, lambda e, uid=u['id']: self._edit_user(uid)),
                            action_text_button("حذف", ft.Icons.DELETE, lambda e, uid=u['id']: self._delete_user(uid), color=ft.Colors.RED, visible=(u.get('id') != 1)),
                        ], alignment=ft.MainAxisAlignment.END),
                    ], spacing=9),
                    elevation=1,
                )
                cards.append(card)
            self.users_list.controls = cards or [empty_state("لا يوجد مستخدمون", "استخدم زر الإضافة لإنشاء مستخدم جديد", ft.Icons.GROUP_OFF)]
            self._page.update()
        except Exception as ex:
            self._show_snackbar(f"خطأ في تحميل المستخدمين: {str(ex)}", True)

    def _add_user(self, e):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, on_save=lambda: self._load_users())
        open_control(self._page, dialog)

    def _edit_user(self, user_id):
        from views.dialogs.user_dialog import UserDialog
        dialog = UserDialog(page=self._page, user_id=user_id, on_save=lambda: self._load_users())
        open_control(self._page, dialog)

    def _delete_user(self, user_id):
        def confirm_delete(e):
            try:
                repo = UserRepository()
                if repo.delete(user_id):
                    self._show_snackbar("تم حذف المستخدم", is_error=False)
                    self._load_users()
                else:
                    self._show_snackbar("فشل الحذف", True)
            finally:
                self._close_dialog(dlg)
        dlg = ft.AlertDialog(
            title=ft.Text(translate('confirm_delete')),
            content=ft.Text("هل أنت متأكد من حذف هذا المستخدم؟"),
            actions=[ft.TextButton("نعم", on_click=confirm_delete), ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))],
        )
        open_control(self._page, dlg)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)
