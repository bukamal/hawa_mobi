# -*- coding: utf-8 -*-
"""Static/runtime guard for Phase 100 unified design system."""
from __future__ import annotations

from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "views"


def main() -> int:
    required = [
        VIEWS / "design_system" / "tokens.py",
        VIEWS / "design_system" / "theme.py",
        VIEWS / "design_system" / "responsive.py",
        VIEWS / "design_system" / "components.py",
        VIEWS / "more_mobile_view.py",
    ]
    for path in required:
        assert path.exists(), path
        ast.parse(path.read_text(encoding="utf-8"))

    app_layout = (VIEWS / "app_layout.py").read_text(encoding="utf-8")
    for needle in [
        'ROOT_PAGES = ["dashboard", "accounts", "reports", "more"]',
        "NavigationRail",
        "NavigationBar",
        "_apply_responsive_mode",
        "_handle_resize",
        "MoreMobileView",
    ]:
        assert needle in app_layout, needle

    ui = (VIEWS / "ui_kit.py").read_text(encoding="utf-8")
    for needle in [
        "def page_header(", "def data_card(", "def modern_field(",
        "def primary_button(", "def secondary_button(", "def danger_button(",
        "RADIUS_CARD", "TOUCH_TARGET",
    ]:
        assert needle in ui, needle

    all_view_text = "\n".join(p.read_text(encoding="utf-8") for p in VIEWS.rglob("*.py"))
    assert "ft.Colors.INDIGO" not in all_view_text, "Legacy Indigo styling remains"

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.0.49"' in pyproject
    assert 'color = "#0A3F70"' in pyproject

    # Runtime constructor check with pinned Flet is intentionally light and has
    # no database/network dependency.
    import flet as ft
    from views.design_system.components import primary_action, secondary_action, modern_text_field, metric_card
    controls = [
        primary_action("حفظ", icon=ft.Icons.SAVE),
        secondary_action("تقرير", icon=ft.Icons.INSIGHTS),
        modern_text_field(label="الاسم"),
        metric_card("الصافي", "100 USD"),
    ]
    assert all(control is not None for control in controls)

    print("phase100_design_system_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
