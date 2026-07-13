# -*- coding: utf-8 -*-
"""Guard that SnackBar does not use page.overlay as the normal Android path."""

from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
files = {
    "views/flet_compat.py": (ROOT / "views" / "flet_compat.py").read_text(
        encoding="utf-8"
    ),
    "views/ui_kit.py": (ROOT / "views" / "ui_kit.py").read_text(encoding="utf-8"),
    "views/dialogs/dialog_kit.py": (
        ROOT / "views" / "dialogs" / "dialog_kit.py"
    ).read_text(encoding="utf-8"),
    "views/app_layout.py": (ROOT / "views" / "app_layout.py").read_text(
        encoding="utf-8"
    ),
}
compat = files["views/flet_compat.py"]
required = [
    ("compat snackbar uses page.snack_bar", "page.snack_bar = snack" in compat),
    ("compat snackbar opens snack", "snack.open = True" in compat),
    (
        "ui_kit delegates to compat snackbar",
        "compat_show_snackbar" in files["views/ui_kit.py"],
    ),
    (
        "dialog_kit delegates to compat snackbar",
        "compat_show_snackbar" in files["views/dialogs/dialog_kit.py"],
    ),
    (
        "app_layout uses compat snackbar",
        "show_snackbar(self._page, message" in files["views/app_layout.py"],
    ),
]
# Direct page.overlay.append(snack) is forbidden outside compatibility fallback.
violations = []
for path, text in files.items():
    code = re.sub(r'""".*?"""', "", text, flags=re.S)
    code = re.sub(r"'''.*?'''", "", code, flags=re.S)
    if path != "views/flet_compat.py" and "overlay.append(snack" in code:
        violations.append(path)
required.append(("no direct snackbar overlay append outside compat", not violations))
missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("snackbar route guard failed: " + "; ".join(missing))
print("flet_snackbar_no_overlay_route_smoke_test passed")
