# -*- coding: utf-8 -*-
from __future__ import annotations

from urllib.parse import quote, unquote

import flet as ft

from views.flet_compat import (
    open_control, close_control, close_all_dialogs, clear_transient_ui,
    show_snackbar, run_async_task,
)
from views.ui_runtime import make_status_bar, loading_view, error_view, safe_update
from views.ui_kit import (
    app_brand, PRIMARY, PRIMARY_SOFT, PAGE_BG, CARD_BG, TEXT, MUTED,
    BORDER, DANGER,
)
from views.design_system.responsive import form_factor, page_gutter, safe_top_height
from auth.session import UserSession
from auth.permissions import can_access_page, access_denied_message
from i18n.translator import translate


class AppLayout(ft.Column):
    """Responsive application shell with route-aware Android navigation.

    Phase 104 keeps the existing single-shell architecture but gives every
    screen a stable route.  Native/browser Back can therefore return from a
    company or settings section instead of closing the app or losing context.
    """

    ROOT_PAGES = ["dashboard", "accounts", "reports", "more"]
    ROUTED_PAGES = {"dashboard", "accounts", "reports", "more", "users", "audit_log", "payment_reminders", "settings"}

    def __init__(self, page, on_logout=None, on_exit=None):
        super().__init__()
        self._page = page
        self.on_logout = on_logout
        self.on_exit = on_exit
        self.expand = True
        self.spacing = 0
        self.current_page_id = "dashboard"
        self._route_context: dict[str, dict] = {}
        self._rendering_route = False

        self.status_area = ft.Container(bgcolor=CARD_BG)
        self.content_area = ft.Container(expand=True, padding=10, bgcolor=PAGE_BG)
        self.nav_bar = self._build_nav_bar()
        self.nav_rail = self._build_nav_rail()
        self.drawer = self._build_drawer()

        self.main_panel = ft.Column([self.status_area, self.content_area], expand=True, spacing=0)
        self.body = ft.Row([self.nav_rail, self.main_panel], expand=True, spacing=0)
        self.safe_top_spacer = ft.Container(height=28, bgcolor=PAGE_BG)
        self.controls = [self.safe_top_spacer, self.body, self.nav_bar]

        self._page.drawer = self.drawer
        self._page.on_resize = self._handle_resize
        self._install_navigation_handlers()
        try:
            setattr(self._page, "_hawaa_app_layout", self)
            setattr(self._page, "_hawaa_refresh_current_page", self.refresh_current_page)
            setattr(self._page, "_hawaa_open_page", self.switch_page)
            setattr(self._page, "_hawaa_handle_back", self.handle_back)
            setattr(self._page, "_hawaa_open_company", self.open_company_details)
        except Exception:
            pass

        self._apply_responsive_mode()
        self._refresh_status_bar()
        initial = self._normalize_route(getattr(self._page, "route", "") or "/dashboard")
        if initial == "/":
            initial = "/dashboard"
        self._set_route_without_event(initial)
        self._render_route(initial)
        self._show_payment_alert_if_needed()

    # ------------------------------------------------------------------
    # Navigation shell and routes
    # ------------------------------------------------------------------
    def _install_navigation_handlers(self):
        try:
            self._page.on_route_change = self._on_route_change
        except Exception:
            pass
        try:
            self._page.on_view_pop = self._on_view_pop
        except Exception:
            pass
        try:
            self._page.on_keyboard_event = self._on_keyboard_event
        except Exception:
            pass

    @staticmethod
    def _normalize_route(route: str) -> str:
        route = str(route or "/").split("?", 1)[0].strip()
        if not route.startswith("/"):
            route = "/" + route
        while "//" in route:
            route = route.replace("//", "/")
        return route.rstrip("/") or "/"

    @staticmethod
    def _route_for_page(page_id: str) -> str:
        page_id = str(page_id or "dashboard").strip("/")
        if page_id in AppLayout.ROUTED_PAGES or page_id.startswith("settings/"):
            return "/" + page_id
        return "/dashboard"

    def _set_route_without_event(self, route: str):
        try:
            self._page.route = route
        except Exception:
            pass

    def _go(self, route: str, *, context: dict | None = None, refresh: bool = False):
        route = self._normalize_route(route)
        if context is not None:
            self._route_context[route] = dict(context)
        current = self._normalize_route(getattr(self._page, "route", "") or "/")
        if refresh or current == route:
            self._set_route_without_event(route)
            self._render_route(route)
            return
        go = getattr(self._page, "go", None)
        if callable(go):
            try:
                go(route)
                return
            except Exception:
                pass
        self._set_route_without_event(route)
        self._render_route(route)

    def _on_route_change(self, event):
        route = self._normalize_route(getattr(event, "route", None) or getattr(self._page, "route", "/dashboard"))
        self._render_route(route)

    def _on_view_pop(self, event=None):
        self.handle_back()

    def _on_keyboard_event(self, event):
        key = str(getattr(event, "key", "") or "").lower()
        if key in {"escape", "esc", "go back", "browser back"}:
            self.handle_back()

    def _close_top_transient(self) -> bool:
        try:
            dialog = getattr(self._page, "dialog", None)
            if dialog is not None and bool(getattr(dialog, "open", False)):
                close_control(self._page, dialog)
                return True
        except Exception:
            pass
        try:
            for control in reversed(list(getattr(self._page, "overlay", []) or [])):
                if bool(getattr(control, "open", False)):
                    close_control(self._page, control)
                    return True
        except Exception:
            pass
        return False

    def parent_route(self, route: str | None = None) -> str | None:
        route = self._normalize_route(route or getattr(self._page, "route", "/dashboard"))
        if route.startswith("/accounts/company/"):
            return "/accounts"
        if route.startswith("/settings/"):
            return "/settings"
        if route in {"/users", "/audit_log", "/payment_reminders", "/settings"}:
            return "/more"
        if route in {"/accounts", "/reports", "/more"}:
            return "/dashboard"
        return None

    def handle_back(self, event=None) -> bool:
        """Close transient UI first, then navigate to the deterministic parent."""
        if self._close_top_transient():
            return True
        parent = self.parent_route()
        if parent:
            self._go(parent)
            return True
        self._confirm_exit()
        return False

    def _confirm_exit(self):
        dlg = None

        def close_dialog(_=None):
            if dlg:
                close_control(self._page, dlg)

        def confirm_exit(_=None):
            close_dialog()
            if callable(self.on_exit):
                self.on_exit()
            else:
                show_snackbar(self._page, translate("exit_app_confirm"), is_error=False, duration=3500)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(translate("exit_app"), weight=ft.FontWeight.BOLD),
            content=ft.Text(translate("exit_app_confirm")),
            actions=[
                ft.TextButton(translate("cancel"), on_click=close_dialog, height=48),
                ft.FilledButton(
                    translate("exit_app"), icon=ft.Icons.EXIT_TO_APP,
                    on_click=confirm_exit, bgcolor=DANGER, color=ft.Colors.WHITE,
                    height=48,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_control(self._page, dlg)

    # ------------------------------------------------------------------
    # Responsive navigation controls
    # ------------------------------------------------------------------
    def _destinations(self, *, rail=False):
        data = [
            (ft.Icons.HOME_OUTLINED, ft.Icons.HOME, translate("dashboard")),
            (ft.Icons.ACCOUNT_BALANCE_OUTLINED, ft.Icons.ACCOUNT_BALANCE, translate("accounts")),
            (ft.Icons.INSERT_CHART_OUTLINED, ft.Icons.INSERT_CHART, translate("reports")),
            (ft.Icons.MORE_HORIZ, ft.Icons.MORE, translate("more")),
        ]
        if rail:
            return [ft.NavigationRailDestination(icon=icon, selected_icon=selected, label=label) for icon, selected, label in data]
        return [ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label) for icon, selected, label in data]

    def _build_nav_bar(self):
        return ft.NavigationBar(
            selected_index=0,
            destinations=self._destinations(),
            on_change=self._nav_change,
            bgcolor=CARD_BG,
            indicator_color=PRIMARY_SOFT,
            indicator_shape=ft.RoundedRectangleBorder(radius=14),
            elevation=4,
            height=76,
        )

    def _build_nav_rail(self):
        return ft.NavigationRail(
            selected_index=0,
            destinations=self._destinations(rail=True),
            on_change=self._rail_change,
            bgcolor=CARD_BG,
            indicator_color=PRIMARY_SOFT,
            min_width=76,
            min_extended_width=210,
            label_type=ft.NavigationRailLabelType.ALL,
            group_alignment=-0.8,
            visible=False,
        )

    def _build_drawer(self):
        return ft.NavigationDrawer(controls=[
            ft.Container(
                content=ft.Column([
                    app_brand(translate("app_name"), translate("app_subtitle"), size=72, dark=True, wordmark=True),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                bgcolor=PRIMARY_SOFT,
                border_radius=18,
            ),
            ft.Divider(),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCK_RESET),
                title=ft.Text(translate("change_password")),
                on_click=self._change_password,
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOGOUT, color=DANGER),
                title=ft.Text(translate("logout"), color=DANGER),
                on_click=self._logout,
            ),
        ])

    def _handle_resize(self, e=None):
        self._apply_responsive_mode()
        self._notify_responsive_content()
        safe_update(self._page)

    def _notify_responsive_content(self):
        """Let active route controls rebuild when a layout breakpoint changes."""
        stack = [getattr(self.content_area, "content", None)]
        visited = set()
        while stack:
            control = stack.pop()
            if control is None or id(control) in visited:
                continue
            visited.add(id(control))
            callback = getattr(control, "_on_responsive_resize", None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass
            content = getattr(control, "content", None)
            if content is not None:
                stack.append(content)
            controls = getattr(control, "controls", None)
            if controls:
                stack.extend(list(controls))

    def _apply_responsive_mode(self):
        factor = form_factor(self._page)
        large = factor in {"tablet", "desktop"}
        self.nav_bar.visible = not large
        self.nav_rail.visible = large
        try:
            self.nav_rail.extended = factor == "desktop"
            self.nav_rail.label_type = ft.NavigationRailLabelType.NONE if factor == "desktop" else ft.NavigationRailLabelType.ALL
        except Exception:
            pass
        gutter = page_gutter(self._page)
        self.content_area.padding = ft.Padding(gutter, 8, gutter, 8)
        self.safe_top_spacer.height = safe_top_height(self._page)
        try:
            self._page.floating_action_button_location = (
                ft.FloatingActionButtonLocation.END_FLOAT if not large
                else ft.FloatingActionButtonLocation.END_FLOAT
            )
        except Exception:
            pass

    def _refresh_status_bar(self):
        current = UserSession.get_current() or {}
        user_label = current.get("full_name") or current.get("username") or translate("login")
        self.status_area.content = make_status_bar(user_label)

    def _show_payment_alert_if_needed(self):
        # Keep startup responsive: repository aggregation runs off the UI thread.
        async def _load_alert():
            try:
                import asyncio
                from database import ExpenseRepository

                def _read():
                    repo = ExpenseRepository()
                    return repo.count_waiting_payment(), repo.get_pending_payment_reminders()

                waiting, reminders = await asyncio.to_thread(_read)
                if waiting <= 0 and not reminders:
                    return
                overdue = 0
                try:
                    from datetime import datetime
                    today = datetime.now().strftime("%Y-%m-%d")
                    overdue = len([r for r in reminders if r.get("reminder_date") and r.get("reminder_date") < today])
                except Exception:
                    pass
                message = f"يوجد {waiting} عملية بانتظار الدفع"
                if overdue:
                    message += f" — متأخرة: {overdue}"
                show_snackbar(self._page, message, is_error=False, duration=5000)
            except Exception as ex:
                print(f"[WARN] تعذر عرض تنبيهات الدفع: {ex}")

        run_async_task(self._page, _load_alert)

    def _nav_change(self, e):
        self._switch_root_index(e.control.selected_index)

    def _rail_change(self, e):
        self._switch_root_index(e.control.selected_index)

    def _switch_root_index(self, index):
        if 0 <= int(index) < len(self.ROOT_PAGES):
            self.switch_page(self.ROOT_PAGES[int(index)])

    def _set_navigation_selection(self, page_id):
        if page_id == "company_details":
            root = "accounts"
        elif page_id in self.ROOT_PAGES:
            root = page_id
        else:
            root = "more"
        index = self.ROOT_PAGES.index(root)
        self.nav_bar.selected_index = index
        self.nav_rail.selected_index = index

    # ------------------------------------------------------------------
    # Public navigation API retained for existing views/tests
    # ------------------------------------------------------------------
    def refresh_current_page(self):
        route = self._normalize_route(getattr(self._page, "route", "") or self._route_for_page(self.current_page_id))
        self._go(route, refresh=True)

    def switch_page(self, page_id):
        self._go(self._route_for_page(page_id))

    def open_company_details(self, company_name, records=None, search_query=None):
        encoded = quote(str(company_name or ""), safe="")
        route = f"/accounts/company/{encoded}"
        self._go(route, context={
            "company_name": str(company_name or ""),
            "records": records,
            "search_query": search_query,
        })

    # ------------------------------------------------------------------
    # Route renderer
    # ------------------------------------------------------------------
    def _render_route(self, route: str):
        if self._rendering_route:
            return
        self._rendering_route = True
        try:
            route = self._normalize_route(route)
            clear_transient_ui(self._page, clear_fab=True)
            try:
                self._page.floating_action_button = None
            except Exception:
                pass
            self._refresh_status_bar()
            self.content_area.content = loading_view(translate("loading_screen"))
            safe_update(self._page)

            if route.startswith("/accounts/company/"):
                self.current_page_id = "company_details"
                self._set_navigation_selection("company_details")
                self._render_company_route(route)
                return

            page_id = route.strip("/") or "dashboard"
            self.current_page_id = page_id
            self._set_navigation_selection(page_id)
            if not can_access_page(page_id):
                self.content_area.content = error_view(access_denied_message())
                safe_update(self._page)
                return

            if page_id == "dashboard":
                from views.dashboard_mobile_view import DashboardMobileView
                view = DashboardMobileView(self._page)
            elif page_id == "accounts":
                from views.accounts_mobile_view import AccountsMobileView
                view = AccountsMobileView(self._page)
            elif page_id == "reports":
                from views.reports_center_mobile_view import ReportsCenterMobileView
                view = ReportsCenterMobileView(self._page)
            elif page_id == "more":
                from views.more_mobile_view import MoreMobileView
                view = MoreMobileView(self._page, self.switch_page, self._change_password, self._logout)
            elif page_id == "users":
                from views.users_mobile_view import UsersMobileView
                view = UsersMobileView(self._page)
            elif page_id == "audit_log":
                from views.audit_log_mobile_view import AuditLogMobileView
                view = AuditLogMobileView(self._page)
            elif page_id == "payment_reminders":
                from views.payment_reminders_mobile_view import PaymentRemindersMobileView
                view = PaymentRemindersMobileView(
                    self._page,
                    on_open_company=lambda company: self.open_company_details(company) if company else None,
                )
            elif page_id == "settings":
                from views.settings_hub_mobile_view import SettingsHubMobileView
                view = SettingsHubMobileView(self._page, self.switch_page)
            elif page_id.startswith("settings/"):
                from views.settings_mobile_view import SettingsMobileView
                view = SettingsMobileView(self._page, section=page_id.split("/", 1)[1])
            else:
                view = error_view(translate("page_not_found"))
            self.content_area.content = view
        except Exception as ex:
            self.content_area.content = error_view(
                str(ex), on_retry=lambda e: self._go(route, refresh=True)
            )
        finally:
            self._rendering_route = False
            safe_update(self._page)

    def _render_company_route(self, route: str):
        context = self._route_context.get(route, {})
        company_name = context.get("company_name") or unquote(route.rsplit("/", 1)[-1])
        records = context.get("records")
        search_query = context.get("search_query")

        def go_back(e=None):
            self._go("/accounts")

        try:
            from views.company_details_mobile_view import CompanyDetailsMobileView
            back_icon = ft.Icons.ARROW_FORWARD if bool(getattr(self._page, "rtl", True)) else ft.Icons.ARROW_BACK
            header = ft.Container(
                content=ft.Row([
                    ft.IconButton(
                        icon=back_icon, tooltip=translate("back"), on_click=go_back,
                        icon_color=PRIMARY, width=48, height=48,
                    ),
                    ft.Container(
                        content=ft.Icon(ft.Icons.BUSINESS, color=PRIMARY, size=22),
                        bgcolor=PRIMARY_SOFT, border_radius=14, padding=10,
                    ),
                    ft.Column([
                        ft.Text(
                            str(company_name), size=20, weight=ft.FontWeight.BOLD,
                            color=TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(translate("company_details_subtitle"), size=12, color=MUTED),
                    ], spacing=2, expand=True),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=CARD_BG,
                padding=ft.Padding(8, 8, 8, 8),
                border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
            )
            details = CompanyDetailsMobileView(
                self._page, company_name, records=records,
                on_changed=lambda: None, search_query=search_query,
            )
            self.content_area.content = ft.Column([header, details], expand=True, spacing=0)
        except Exception as ex:
            self.content_area.content = error_view(
                str(ex), on_retry=lambda e: self._go(route, refresh=True)
            )

    # ------------------------------------------------------------------
    # Account actions
    # ------------------------------------------------------------------
    def _change_password(self, e=None):
        from views.dialogs.change_password_dialog import ChangePasswordDialog
        dialog = ChangePasswordDialog(page=self._page, on_save=lambda: None)
        open_control(self._page, dialog)

    def _logout(self, e=None):
        dlg = None

        def cancel_logout(_):
            if dlg:
                close_control(self._page, dlg)

        def confirm_logout(_):
            if dlg:
                close_control(self._page, dlg)
            try:
                close_all_dialogs(self._page)
            except Exception:
                pass
            UserSession.logout()
            if self.on_logout:
                self.on_logout()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(translate("logout"), weight=ft.FontWeight.BOLD),
            content=ft.Text(translate("logout_confirm")),
            actions=[
                ft.TextButton(translate("cancel"), on_click=cancel_logout, height=48),
                ft.FilledButton(
                    translate("logout"), on_click=confirm_logout,
                    bgcolor=DANGER, color=ft.Colors.WHITE, height=48,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_control(self._page, dlg)

    def _close_dialog(self, dialog):
        close_control(self._page, dialog)

    def _rebuild_after_login(self):
        self._page.controls.clear()
        new_layout = AppLayout(self._page, on_logout=self.on_logout, on_exit=self.on_exit)
        self._page.add(new_layout)
