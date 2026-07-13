# -*- coding: utf-8 -*-
"""Guard against Android blank white screen after closing AlertDialog.

The Android Flet runtime used by this APK may leave a hidden white modal surface
when AlertDialog is managed through page.overlay or closed through page.close.
AlertDialog must use page.dialog + open=True, and close_control must not call
page.close/pop_dialog.
"""

from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
code = re.sub(r'""".*?"""', "", compat, flags=re.S)
code = re.sub(r"'''.*?'''", "", code, flags=re.S)
code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())

required = [
    ("AlertDialog detector exists", "def _is_alert_dialog" in compat),
    ("AlertDialog path uses page.dialog", "page.dialog = control" in compat),
    (
        "AlertDialog path explicitly removes overlay",
        "_remove_from_overlay(page, control)" in compat,
    ),
    ("close_control does not call page.close", ".close(control" not in code),
    ("close_control does not call pop_dialog", ".pop_dialog(" not in code),
    ("close_all_dialogs clears page.dialog", "page.dialog = None" in compat),
]
missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("alert dialog blank-screen guard failed: " + "; ".join(missing))
print("flet_alertdialog_no_overlay_blank_screen_smoke_test passed")
