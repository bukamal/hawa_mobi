# -*- coding: utf-8 -*-
import flet as ft
from auth.session import UserSession
from i18n.translator import translate

class AppLayout(ft.Column):
    def __init__(self, page, on_logout=None):
        super().__init__()
        self._page = page
        self.on_logout = on_logout
        self.expand = True
        self.spacing = 0

        self.content_area = ft.Container(expand=True, padding=10, bgcolor=ft.Colors.GREY_50)
        self.nav_bar = self._build_nav_bar()
        self.drawer = self._build_drawer()

        self.controls = [self.content_area, self.nav_bar]
        self._page.drawer = self.drawer
        self.switch_page('accounts')

    def _build_nav_bar(self):
        user_role = UserSession.get_current().get('role') if UserSession.get_current() else 'user'
        destinations = [
            ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label=translate('dashboard')),
            ft.NavigationBarDestination(icon=ft.Icons.ACCOUNT_BALANCE, label=translate('accounts')),
        ]
        if user_role == 'admin':
            destinations.append(ft.NavigationBarDestination(icon=ft.Icons.PEOPLE, label=translate('users')))
            destinations.append(ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT, label=translate('audit_log')))
        destinations.append(ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label=translate('settings')))

        nav_bar = ft.NavigationBar(
            selected_index=1,
            destinations=destinations,
            on_change=self._nav_change,
            bgcolor=ft.Colors.WHITE,
            indicator_color=ft.Colors.INDIGO,
            indicator_shape=ft.RoundedRectangleBorder(radius=10),
            elevation=5
        )
        return nav_bar

    def _build_drawer(self):
        controls = [
            ft.Container(
                content=ft.Column([
                    ft.Text("🏢 هوى الشام", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO),
                    ft.Text("نظام الحسابات الداخلية", size=12, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                bgcolor=ft.Colors.INDIGO_50,
                border_radius=20
            ),
            ft.Divider(),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCK),
                title=ft.Text(translate('change_password')),
                on_click=self._change_password
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOGOUT),
                title=ft.Text(translate('logout')),
                on_click=self._logout
            )
        ]
        return ft.NavigationDrawer(controls=controls)

    def _nav_change(self, e):
        index = e.control.selected_index
        user_role = UserSession.get_current().get('role') if UserSession.get_current() else 'user'
        if user_role == 'admin':
            pages = ['dashboard', 'accounts', 'users', 'audit_log', 'settings']
        else:
            pages = ['dashboard', 'accounts', 'settings']
        if index < len(pages):
            self.switch_page(pages[index])

    def switch_page(self, page_id):
        if page_id == 'dashboard':
            from views.dashboard_mobile_view import DashboardMobileView
            view = DashboardMobileView(self._page)
        elif page_id == 'accounts':
            from views.accounts_mobile_view import AccountsMobileView
            view = AccountsMobileView(self._page)
        elif page_id == 'users':
            from views.users_mobile_view import UsersMobileView
            view = UsersMobileView(self._page)
        elif page_id == 'audit_log':
            from views.audit_log_mobile_view import AuditLogMobileView
            view = AuditLogMobileView(self._page)
        elif page_id == 'settings':
            from views.settings_mobile_view import SettingsMobileView
            view = SettingsMobileView(self._page)
        else:
            view = ft.Text("الصفحة غير موجودة")
        self.content_area.content = view
        self._page.update()

    def _change_password(self, e):
        from views.dialogs.change_password_dialog import ChangePasswordDialog
        dialog = ChangePasswordDialog(page=self._page, on_save=lambda: None)
        self._page.open(dialog)

    def _logout(self, e):
        dlg = None  # سيتم تعيينه لاحقاً
        def confirm_logout(e):
            if e.control.text == "نعم":
                from database.connection import DatabaseConnection
                db = DatabaseConnection()
                if db.is_remote():
                    try: db.get_rest_client().logout()
                    except: pass
                UserSession.logout()
                if self.on_logout:
                    self.on_logout()
                else:
                    self._page.controls.clear()
                    from views.login_view import LoginView
                    login = LoginView(page=self._page, on_login_success=lambda u: self._rebuild_after_login(), on_exit=self.on_logout)
                    self._page.add(login)
            if dlg:
                dlg.open = False
                self._page.update()
        dlg = ft.AlertDialog(
            title=ft.Text(translate('logout')),
            content=ft.Text("هل تريد تسجيل الخروج؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm_logout),
                ft.TextButton("لا", on_click=lambda e: self._close_dialog(dlg))
            ]
        )
        self._page.open(dlg)

    def _close_dialog(self, dialog):
        dialog.open = False
        self._page.update()

    def _rebuild_after_login(self):
        self._page.controls.clear()
        new_layout = AppLayout(self._page, on_logout=self.on_logout)
        self._page.add(new_layout)
