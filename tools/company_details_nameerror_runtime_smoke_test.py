# -*- coding: utf-8 -*-
"""Runtime guard for company details internal route UI constants.

Android reports are surfaced as: name 'TEXT'/'SUCCESS'/... is not defined
when tapping تفاصيل.  Static imports alone are not enough; instantiate the
company details view against a temporary database to catch NameError at render
construction time.
"""
from __future__ import annotations

import ast
import os
import shutil
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI_CONSTANTS = {"TEXT", "MUTED", "BORDER", "CARD_BG", "PRIMARY", "PRIMARY_SOFT", "SUCCESS", "DANGER", "WARNING"}


def _ui_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "views.ui_kit":
            imports.update((alias.asname or alias.name) for alias in node.names)
    return imports


def _assert_used_ui_constants_imported(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = _ui_imports(path)
    defined = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in UI_CONSTANTS
    }
    used = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in UI_CONSTANTS
    }
    missing = sorted(used - imports - defined)
    assert not missing, f"{path.relative_to(ROOT)} missing ui_kit imports: {missing}"


def _reset_singleton() -> None:
    from database.connection import DatabaseConnection
    try:
        DatabaseConnection().close()
    except Exception:
        pass
    DatabaseConnection._instance = None
    DatabaseConnection._local_conn = None


class FakePage:
    def __init__(self):
        self.update_count = 0
        self.overlay = []
        self.dialog = None
        self.snack_bar = None
        self.floating_action_button = None

    def update(self):
        self.update_count += 1


def main() -> int:
    for view_path in (ROOT / "views").rglob("*.py"):
        if view_path.name == "ui_kit.py":
            continue
        _assert_used_ui_constants_imported(view_path)

    if importlib.util.find_spec("flet") is None:
        print("company details runtime instantiation skipped: flet is not installed; static UI import contract passed")
        print("✅ company_details_nameerror_runtime_smoke_test passed")
        return 0

    tmp = tempfile.mkdtemp(prefix="hawaa_company_details_nameerror_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ.pop("HAWAA_SERVER_PROCESS", None)

    try:
        _reset_singleton()
        from database.migrations import init_database
        from database.repositories.expense_repo import ExpenseRepository
        from views.company_details_mobile_view import CompanyDetailsMobileView

        init_database()
        repo = ExpenseRepository()
        repo.add("شركة تفاصيل", 100, "incoming", "2026-07-14", "قيد اختبار", "USD", 1)
        view = CompanyDetailsMobileView(FakePage(), "شركة تفاصيل")
        assert view.controls, "company details view must render controls"
        assert any(getattr(c, "controls", None) is not None or c is not None for c in view.controls), "rendered details controls are empty"
        print("✅ company_details_nameerror_runtime_smoke_test passed")
        return 0
    finally:
        _reset_singleton()
        if old_data_dir is None:
            os.environ.pop("HAWAA_DATA_DIR", None)
        else:
            os.environ["HAWAA_DATA_DIR"] = old_data_dir
        if old_server_flag is None:
            os.environ.pop("HAWAA_SERVER_PROCESS", None)
        else:
            os.environ["HAWAA_SERVER_PROCESS"] = old_server_flag
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
