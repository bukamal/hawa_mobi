# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_contains(path, text):
    content = (ROOT / path).read_text(encoding="utf-8")
    assert text in content, f"Missing {text!r} in {path}"


def main():
    assert_contains("services/network_service.py", "UserSession.logout()")
    assert_contains("services/network_service.py", "auth/network_token")
    assert_contains("views/settings_mobile_view.py", "_hawaa_logout")
    assert_contains("views/app_layout.py", "close_all_dialogs")
    assert_contains("views/app_layout.py", "modal=True")
    print("network_mode_logout_flow_smoke_test OK")


if __name__ == "__main__":
    main()
