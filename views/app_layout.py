# -*- coding: utf-8 -*-
import flet as ft
from views.flet_compat import open_control, close_control, close_all_dialogs, clear_transient_ui
from views.ui_runtime import make_status_bar, loading_view, error_view, safe_update
from views.ui_kit import app_brand, PRIMARY, PRIMARY_SOFT, PAGE_BG, CARD_BG
from auth.session import UserSession
from i18n.translator import translate

class AppLayout(ft.Column):
    def __init__(self, page, on_logout=None):
        super().__init__()
        self._page = page
        self.on_logout = on_logout
        self.expand = True
        self.spacing = 0

        self.current_page_id = 'accounts'
        self.status_area = ft.Container()
        self.content_area = ft.Container(expand=True, padding=10, bgcolor=PAGE_BG)
        self.nav_bar = self._build_nav_bar()
        self.drawer = self._build_drawer()

        self.controls = [self.status_area, self.content_area, self.nav_bar]
        self._page.drawer = self.drawer
        try:
            setattr(self._page, '_hawaa_app_layout', self)
            setattr(self._page, '_hawaa_refresh_current_page', self.refresh_current_page)
            setattr(self._page, '_hawaa_open_page', self.switch_page)
        except Exception:
            pass
        self._refresh_status_bar()
        self.switch_page('accounts')
        self._show_payment_alert_if_needed()


    def _refresh_status_bar(self):
        current = UserSession.get_current() or {}
        user_label = current.get('full_name') or current.get('username') or translate('login')
        self.status_area.content = make_status_bar(user_label)

    def _show_payment_alert_if_needed(self):
        try:
            from database import ExpenseRepository
            repo = ExpenseRepository()
            waiting = repo.count_waiting_payment()
            reminders = repo.get_pending_payment_reminders()
            if waiting <= 0 and not reminders:
                return
            overdue = 0
            try:
                from datetime import datetime
                today = datetime.now().strftime('%Y-%m-%d')
                overdue = len([r for r in reminders if r.get('reminder_date') and r.get('reminder_date') < today])
            except Exception:
                overdue = 0
            message = f"⏳ يوجد {waiting} عملية بانتظار الدفع"
            if overdue:
                message += f" | ⚠️ متأخرة: {overdue}"
            snack = ft.SnackBar(
                content=ft.Text(message, size=13),
                bgcolor=ft.Colors.ORANGE,
                duration=5000,
            )
            self._page.overlay.append(snack)
            snack.open = True
            self._page.update()
        except Exception as ex:
            print(f"[WARN] تعذر عرض تنبيهات الدفع: {ex}")

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
            bgcolor=CARD_BG,
            indicator_color=PRIMARY_SOFT,
            indicator_shape=ft.RoundedRectangleBorder(radius=10),
            elevation=5
        )
        return nav_bar

    def _build_drawer(self):
        controls = [
            ft.Container(
                content=ft.Column([
                    app_brand(translate('app_name'), translate('app_subtitle'), size=72, dark=True, wordmark=True),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                bgcolor=PRIMARY_SOFT,
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

    def refresh_current_page(self):
        self.switch_page(getattr(self, 'current_page_id', 'accounts'))

    def switch_page(self, page_id):
        # A page switch must start from a clean transient state.  Without this,
        # Android/Flet can keep a blank modal route from a previous dialog above
        # the newly rendered screen until the user presses Back.
        clear_transient_ui(self._page, clear_fab=True)
        self.current_page_id = page_id
        # Do not let a FAB from the previous page leak into settings/audit/dashboard.
        # Individual pages that need a FAB (accounts/users) set their own button.
        try:
            self._page.floating_action_button = None
        except Exception:
            pass
        self._refresh_status_bar()
        self.content_area.content = loading_view('جاري فتح الشاشة...' if translate('settings') == 'الإعدادات' else 'Loading screen...')
        safe_update(self._page)
        try:
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
                view = error_view('الصفحة غير موجودة' if translate('settings') == 'الإعدادات' else 'Page not found')
            self.content_area.content = view
        except Exception as ex:
            self.content_area.content = error_view(str(ex), on_retry=lambda e: self.switch_page(page_id))
        safe_update(self._page)

    def _change_password(self, e):
        from views.dialogs.change_password_dialog import ChangePasswordDialog
        dialog = ChangePasswordDialog(page=self._page, on_save=lambda: None)
        open_control(self._page, dialog)

    def _logout(self, e):
        dlg = None

        def cancel_logout(e):
            if dlg:
                close_control(self._page, dlg)

        def confirm_logout(e):
            # Close the modal first.  If the session is already invalid, any
            # remote /logout call may fail; it must not block the confirmation
            # buttons or leave a modal barrier above the app.
            if dlg:
                close_control(self._page, dlg)
            # Do not call the remote /logout endpoint here.  If the server is
            # unreachable or the token is already invalid, a blocking network
            # call can make the confirmation buttons appear dead.  Clearing the
            # local session/token is enough for the APK client; the server token
            # will expire by TTL.
            try:
                close_all_dialogs(self._page)
            except Exception:
                pass
            UserSession.logout()
            if self.on_logout:
                self.on_logout()
            else:
                self._page.controls.clear()
                from views.login_view import LoginView
                login = LoginView(page=self._page, on_login_success=lambda u: self._rebuild_after_login(), on_exit=self.on_logout)
                self._page.add(login)
                self._page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(translate('logout')),
            content=ft.Text("هل تريد تسجيل الخروج؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm_logout),
                ft.TextButton("لا", on_click=cancel_logout),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_control(self._page, dlg)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)

    def _rebuild_after_login(self):
        self._page.controls.clear()
        new_layout = AppLayout(self._page, on_logout=self.on_logout)
        self._page.add(new_layout)
