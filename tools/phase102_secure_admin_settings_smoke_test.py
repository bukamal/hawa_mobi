# -*- coding: utf-8 -*-
"""Static and repository-level regression checks for Phase 102."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path, text):
    content = (ROOT / path).read_text(encoding="utf-8")
    assert text in content, f"missing {text!r} in {path}"


def static_checks():
    require("pyproject.toml", 'version = "1.0.50"')
    require("auth/permissions.py", "ADMIN_SETTINGS_SECTIONS")
    require("views/app_layout.py", "can_access_page(page_id)")
    require("views/settings_hub_mobile_view.py", 'f"settings/{sid}"')
    require("views/settings_mobile_view.py", "_secure_reset_async")
    require("views/settings_mobile_view.py", "حذف جميع بيانات هوى الشام")
    require("views/users_mobile_view.py", "can_delete")
    require("views/audit_log_mobile_view.py", "غير قابل للحذف")
    require("database/repositories/user_repo.py", "لا يمكن حذف آخر مدير")
    require("views/dialogs/user_dialog.py", "evaluate_password")


def repository_checks():
    tmp = tempfile.mkdtemp(prefix="hawaa_phase102_")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ["HAWAA_DB_PATH"] = str(Path(tmp) / "hawaa_data.db")
    from database.migrations import init_database
    from database import UserRepository
    from auth.session import UserSession

    init_database()
    repo = UserRepository()
    users = repo.get_all()
    admin = next(u for u in users if u.get("role") == "admin")
    UserSession.login(admin)
    from auth.permissions import can_access_page, can_access_settings_section
    assert can_access_page("users")
    assert can_access_settings_section("backup")
    allowed, reason = repo.can_delete(admin["id"])
    assert not allowed and ("المسجل" in reason or "آخر مدير" in reason)

    try:
        repo.update(admin["id"], admin.get("full_name") or "Admin", "user")
    except ValueError:
        pass
    else:
        raise AssertionError("last admin was demoted")

    try:
        repo.create("weak_phase102", "123", "Weak", "user")
    except ValueError:
        pass
    else:
        raise AssertionError("weak password was accepted")

    second_admin_id = repo.create("admin_phase102", "Abcdef12!", "Second Admin", "admin")
    allowed, reason = repo.can_delete(second_admin_id)
    assert allowed, reason

    # Runtime view policy check when Flet is available.
    try:
        import flet  # noqa: F401
        from views.settings_hub_mobile_view import SettingsHubMobileView
        from views.settings_mobile_view import SettingsMobileView

        class FakePage:
            width = 360
            height = 800
            overlay = []
            dialog = None
            snack_bar = None
            theme_mode = None
            rtl = True
            floating_action_button = None
            def update(self):
                return None

        UserSession.login({"id": 999, "username": "viewer", "role": "viewer"})
        assert not can_access_page("users")
        assert not can_access_settings_section("backup")
        assert can_access_settings_section("appearance")
        page = FakePage()
        hub = SettingsHubMobileView(page, lambda route: None)
        assert len(hub.controls) == 4, "non-admin hub must expose only appearance"
        forbidden = SettingsMobileView(page, section="backup")
        assert len(forbidden.controls) == 2, "admin settings must render access denied"
        appearance = SettingsMobileView(page, section="appearance")
        assert len(appearance.controls) == 3
    except ImportError:
        pass


if __name__ == "__main__":
    static_checks()
    repository_checks()
    print("phase102_secure_admin_settings_smoke_test passed")
