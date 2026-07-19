# -*- coding: utf-8 -*-
"""Guard against the Android blank white AlertDialog route."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
code = re.sub(r'""".*?"""', '', compat, flags=re.S)
code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())

required = [
    ("custom modal host builder exists", "def _build_alert_dialog_host" in compat),
    ("AlertDialog is converted to host", "host = _build_alert_dialog_host(page, control)" in compat),
    ("logical page.dialog pointer retained", "page.dialog = control" in compat),
    ("host is removed on close", "_remove_modal_host(page, control)" in compat),
    ("native show_dialog is unused", ".show_dialog(" not in code),
    ("native pop_dialog is unused", ".pop_dialog(" not in code),
    ("native page.close(control) is unused", ".close(control" not in code),
]
missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("custom AlertDialog host guard failed: " + "; ".join(missing))
print("flet_alertdialog_no_overlay_blank_screen_smoke_test passed")
