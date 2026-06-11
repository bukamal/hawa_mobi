# -*- coding: utf-8 -*-
"""Static UI checks for the mobile interface layer."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "views"

REQUIRED_HELPERS = [
    "page_header",
    "search_field",
    "summary_bar",
    "metric_tile",
    "empty_state",
    "show_snackbar",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_ui_kit_has_expected_helpers() -> None:
    src = read(VIEWS / "ui_kit.py")
    tree = ast.parse(src)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = [name for name in REQUIRED_HELPERS if name not in functions]
    if missing:
        raise AssertionError(f"ui_kit.py missing helpers: {missing}")


def assert_core_views_use_ui_kit() -> None:
    expected = {
        "accounts_mobile_view.py": ["page_header", "search_field", "summary_bar"],
        "dashboard_mobile_view.py": ["page_header"],
        "company_details_mobile_view.py": ["empty_state", "show_snackbar"],
    }
    for filename, helpers in expected.items():
        src = read(VIEWS / filename)
        if "from views.ui_kit import" not in src:
            raise AssertionError(f"{filename} does not import views.ui_kit")
        for helper in helpers:
            if helper not in src:
                raise AssertionError(f"{filename} does not use {helper}")


def assert_ui_kit_is_presentation_only() -> None:
    src = read(VIEWS / "ui_kit.py")
    tree = ast.parse(src)
    banned_roots = {"database", "requests", "services"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in banned_roots:
                    raise AssertionError(f"ui_kit.py must not import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in banned_roots:
                raise AssertionError(f"ui_kit.py must not import from {module}")


def main() -> int:
    assert_ui_kit_has_expected_helpers()
    assert_core_views_use_ui_kit()
    assert_ui_kit_is_presentation_only()
    print("✅ ui_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
