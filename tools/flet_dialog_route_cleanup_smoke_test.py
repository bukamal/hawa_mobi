# -*- coding: utf-8 -*-
"""Static guard against Android blank-white dialog routes.

The APK pins Flet 0.28.x. On this runtime, opening AlertDialog/DatePicker via
native ``page.show_dialog`` can leave a blank white route above the app after
login/save/edit/delete. The route disappears only when the user presses Android
Back. The app must therefore use the legacy overlay/open path for dialogs.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
compat_path = ROOT / "views" / "flet_compat.py"
compat = compat_path.read_text(encoding="utf-8")
main = (ROOT / "main.py").read_text(encoding="utf-8")
app_layout = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")

# Strip comments/docstrings roughly enough for a static guard, then check calls.
code_only = re.sub(r'""".*?"""', '', compat, flags=re.S)
code_only = re.sub(r"'''.*?'''", '', code_only, flags=re.S)
code_only = "\n".join(line.split("#", 1)[0] for line in code_only.splitlines())

required = [
    ("open_control helper exists", "def open_control" in compat),
    ("close_control helper exists", "def close_control" in compat),
    ("open path uses overlay helper", "_ensure_overlay_contains(page, control)" in compat),
    ("open path sets control.open true", "control.open = True" in compat),
    ("close path sets control.open false", "control.open = False" in compat),
    ("native show_dialog is not called", ".show_dialog(" not in code_only),
    ("native pop_dialog is not called", ".pop_dialog(" not in code_only),
    ("clear_transient_ui helper exists", "def clear_transient_ui" in compat),
    ("main cleans transient ui before rebuilding main shell", "clear_transient_ui(page, clear_fab=True)" in main),
    ("app layout cleans transient ui before page switch", "clear_transient_ui(self._page, clear_fab=True)" in app_layout),
]

missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("dialog route cleanup guard failed: " + "; ".join(missing))

print("flet_dialog_route_cleanup_smoke_test passed")
