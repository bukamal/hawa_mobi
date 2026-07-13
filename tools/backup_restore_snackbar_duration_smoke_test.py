# -*- coding: utf-8 -*-
"""Guard backup restore buttons from being killed by snackbar kwargs.

Real APK diagnostics showed:
SettingsMobileView._show_snackbar() got an unexpected keyword argument 'duration'
This happened before FilePicker could open, so restore buttons looked inert.
"""

from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
settings_path = ROOT / "views" / "settings_mobile_view.py"
compat_path = ROOT / "views" / "flet_compat.py"
settings = settings_path.read_text(encoding="utf-8")
compat = compat_path.read_text(encoding="utf-8")

module = ast.parse(settings)
show_fn = None
for node in ast.walk(module):
    if isinstance(node, ast.FunctionDef) and node.name == "_show_snackbar":
        show_fn = node
        break
assert show_fn is not None, "SettingsMobileView._show_snackbar is missing"
arg_names = [a.arg for a in show_fn.args.args]
assert "duration" in arg_names, (
    "SettingsMobileView._show_snackbar must accept duration=..."
)
assert (
    "return show_snackbar(self._page, message, is_error, duration=duration)" in settings
), "settings snackbar wrapper must forward duration safely"

assert "def make_snackbar" in compat, "flet_compat must expose make_snackbar"
assert "_construct_with_keyword_fallback(ft.SnackBar" in compat, (
    "SnackBar must be created via keyword fallback"
)
assert "snack.duration = duration" in compat, (
    "duration should be set best-effort after construction"
)
assert (
    "duration=duration"
    not in compat.split("def make_snackbar", 1)[1].split("def show_snackbar", 1)[0]
    or "_construct_with_keyword_fallback" in compat
), "SnackBar duration must not be an unguarded hard dependency"
print("backup_restore_snackbar_duration_smoke_test passed")
