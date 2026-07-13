# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_contains(path, *needles):
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path} missing: {needle}"


def main():
    assert_contains(
        "views/app_layout.py",
        "status_area",
        "loading_view",
        "error_view",
        "safe_update",
        "_refresh_status_bar",
    )
    assert_contains(
        "views/ui_runtime.py", "network_status_chip", "loading_view", "error_view"
    )
    assert_contains(
        "views/settings_mobile_view.py",
        "network_status_chip",
        "جاري الاختبار",
        "جاري الحفظ",
    )
    assert_contains(
        "views/ui_kit.py", "responsive_wrap", "info_banner", "set_control_busy"
    )
    print("✅ ui_navigation_smoke_test passed")


if __name__ == "__main__":
    main()
