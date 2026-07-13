# -*- coding: utf-8 -*-
"""Guard that app dialogs still open on Android/Flet 0.28.x.

AlertDialog must be present in page.overlay to render in the pinned Android
runtime. Cleanup then removes it from overlay to avoid the white-surface bug.
"""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
code = re.sub(r'""".*?"""', '', compat, flags=re.S)
# single-quoted docstrings intentionally not stripped here
code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())
required = [
    ("open_control exists", "def open_control" in compat),
    ("AlertDialog detector exists", "def _is_alert_dialog" in compat),
    ("AlertDialog attaches overlay for rendering", "_ensure_overlay_contains(page, control)" in compat),
    ("AlertDialog sets page.dialog pointer", "page.dialog = control" in compat),
    ("close_control removes overlay", "_remove_from_overlay(page, control)" in compat),
    ("dismiss cleanup installed", "def _install_dialog_dismiss_cleanup" in compat),
    ("no native show_dialog", ".show_dialog(" not in code),
    ("no native pop_dialog", ".pop_dialog(" not in code),
    ("no page.close(control)", ".close(control" not in code),
]
missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("dialog open rendering guard failed: " + "; ".join(missing))
print("flet_dialog_open_rendering_smoke_test passed")
