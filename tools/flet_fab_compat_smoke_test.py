#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard FloatingActionButton compatibility for Android/Flet 0.28.x.

The Android runtime rejects layout-only kwargs such as ``margin`` on
``ft.FloatingActionButton``.  All application views must create FABs through
``views.flet_compat.make_floating_action_button`` and must not pass ``margin``
to that helper either.  Margin/layout should be handled by page-level layout,
not by the FAB constructor.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "views"

violations: list[str] = []

for path in sorted(VIEWS.rglob("*.py")):
    if path.name == "flet_compat.py":
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        direct_fab = (
            isinstance(func, ast.Attribute)
            and func.attr == "FloatingActionButton"
            and isinstance(func.value, ast.Name)
            and func.value.id == "ft"
        )
        helper_fab = isinstance(func, ast.Name) and func.id == "make_floating_action_button"
        has_margin = any(kw.arg == "margin" for kw in node.keywords if kw.arg)

        if direct_fab:
            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: direct ft.FloatingActionButton")
        if helper_fab and has_margin:
            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: margin passed to make_floating_action_button")

if violations:
    raise SystemExit("FAB compatibility violations:\n" + "\n".join(violations))

print("flet_fab_compat_smoke_test passed")
