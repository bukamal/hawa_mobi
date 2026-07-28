# -*- coding: utf-8 -*-
"""Regression checks for Phase 104 navigation, recovery and accessibility."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(path: str, text: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    assert text in content, f"missing {text!r} in {path}"


def static_checks() -> None:
    require("pyproject.toml", 'version = "1.0.50"')
    require("views/connection_recovery_view.py", "class ConnectionRecoveryView")
    require("views/connection_recovery_view.py", "_local_admin_is_valid")
    require("views/connection_recovery_view.py", "asyncio.to_thread")
    require("views/connection_recovery_view.py", "open_qr_pairing_dialog")
    require("views/app_layout.py", "on_route_change")
    require("views/app_layout.py", "def handle_back")
    require("views/app_layout.py", "/accounts/company/")
    require("views/app_layout.py", "on_keyboard_event")
    require("views/splash_view.py", "asyncio.to_thread")
    require("views/ui_runtime.py", "def offline_banner")
    require("views/ui_runtime.py", "skeletons")
    require("views/ui_kit.py", "width=TOUCH_TARGET, height=TOUCH_TARGET")
    require("main.py", "show_connection_recovery")
    require("main.py", "on_exit=close_app")


def runtime_checks() -> None:
    try:
        import flet  # noqa: F401
    except ImportError:
        return

    tmp = tempfile.mkdtemp(prefix="hawaa_phase104_")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ["HAWAA_DB_PATH"] = str(Path(tmp) / "hawaa_data.db")

    from database.migrations import init_database
    from database.connection import get_local_db_path
    from auth.password import hash_password
    from auth.session import UserSession
    import sqlite3

    init_database()
    pwd_hash, salt = hash_password("LocalAdmin#104")
    conn = sqlite3.connect(get_local_db_path())
    try:
        conn.execute("DELETE FROM users WHERE username=?", ("phase104admin",))
        conn.execute(
            "INSERT INTO users (username,password_hash,salt,full_name,role,created_at) VALUES (?,?,?,?,?,datetime('now'))",
            ("phase104admin", pwd_hash, salt, "Phase 104 Admin", "admin"),
        )
        conn.commit()
    finally:
        conn.close()

    from views.connection_recovery_view import _local_admin_is_valid
    assert _local_admin_is_valid("phase104admin", "LocalAdmin#104")
    assert not _local_admin_is_valid("phase104admin", "wrong")

    UserSession.login({"id": 1, "username": "phase104admin", "role": "admin", "full_name": "Admin"})

    class FakePage:
        width = 360
        height = 800
        overlay = []
        dialog = None
        snack_bar = None
        theme_mode = None
        rtl = True
        route = "/"
        floating_action_button = None
        drawer = None
        on_resize = None
        on_route_change = None
        on_view_pop = None
        on_keyboard_event = None
        controls = []

        def update(self):
            return None

        def go(self, route):
            self.route = route
            if self.on_route_change:
                event = type("RouteEvent", (), {"route": route})()
                self.on_route_change(event)

    page = FakePage()
    from views.app_layout import AppLayout
    layout = AppLayout(page, on_logout=lambda: None)
    assert page.route == "/dashboard"
    layout.switch_page("accounts")
    assert page.route == "/accounts"
    layout.open_company_details("شركة اختبار")
    assert page.route.startswith("/accounts/company/")
    assert layout.current_page_id == "company_details"
    assert layout.parent_route() == "/accounts"
    assert layout.handle_back()
    assert page.route == "/accounts"
    layout.switch_page("settings/appearance")
    assert page.route == "/settings/appearance"
    assert layout.parent_route() == "/settings"
    assert layout.handle_back()
    assert page.route == "/settings"

    from views.connection_recovery_view import ConnectionRecoveryView
    recovery = ConnectionRecoveryView(page, "network error", lambda: None, lambda: None)
    assert not recovery.local_panel.visible
    recovery._toggle_local()
    assert recovery.local_panel.visible
    recovery._toggle_technical()
    assert recovery.technical_box.visible


if __name__ == "__main__":
    static_checks()
    runtime_checks()
    print("phase104_navigation_recovery_accessibility_smoke_test passed")
