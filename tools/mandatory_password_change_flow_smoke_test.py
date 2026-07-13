# -*- coding: utf-8 -*-
"""Guard the Android first-login password-change flow.

The mandatory password change must be a full-screen navigation state.  It must
not be an optional AlertDialog; cancel must log out and return to Login, and a
successful login must not leave the LoginView stuck at "جاري التحقق...".
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / "main.py").read_text(encoding="utf-8")
login = (ROOT / "views" / "login_view.py").read_text(encoding="utf-8")
view = (ROOT / "views" / "mandatory_password_change_view.py").read_text(encoding="utf-8")

assert "MandatoryPasswordChangeView" in main, "main.py must route forced password changes to the full-screen view"
assert "ChangePasswordDialog" not in main.split("def show_change_password", 1)[1].split("def show_main_app", 1)[0], "first-login password change must not open an AlertDialog"
assert "clear_transient_ui(page, clear_fab=True)" in main.split("def show_change_password", 1)[1].split("def show_main_app", 1)[0]
assert "page.controls.clear()" in main.split("def show_change_password", 1)[1].split("def show_main_app", 1)[0]

assert "class MandatoryPasswordChangeView(ft.Container)" in view
assert "ft.AlertDialog" not in view, "mandatory password change view must not use modal AlertDialog"
assert "UserSession.logout()" in view, "Cancel must log out"
assert "on_cancel" in view, "Cancel must return to login through the provided callback"
assert "force_password_change'] = 0" in view, "successful save must clear the session force flag"
assert "preserves any remote auth token" in view, "remote token must not be lost after password change"

assert "_navigating_after_login" in login, "LoginView must avoid stale busy-state updates after navigation"
assert "if not self._navigating_after_login" in login, "LoginView finally block must not overwrite routed UI"
assert "تم تسجيل الدخول. جارٍ فتح الواجهة" in login

print("mandatory_password_change_flow_smoke_test passed")
