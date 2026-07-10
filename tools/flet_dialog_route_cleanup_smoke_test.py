# -*- coding: utf-8 -*-
"""Static guard for Android dialog-route cleanup.

Flet Android can keep a native dialog route above the rebuilt app shell when
``page.show_dialog`` is used but the source control's ``open`` flag is stale.
The runtime symptom is a blank white surface that only disappears after Android
Back.  This guard ensures close_control trusts the app-managed dialog stack and
not the unreliable ``open`` flag.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
main = (ROOT / "main.py").read_text(encoding="utf-8")
app_layout = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")

required = [
    ("open_control marks dialogs open after show_dialog", "control.open = True" in compat and "page.show_dialog(control)" in compat),
    ("close_control pops stacked dialog without was_open gate", "_is_dialog_like(control) and is_top and hasattr(page, \"pop_dialog\")" in compat),
    ("old was_open-gated pop path removed", "_is_dialog_like(control) and was_open and is_top" not in compat),
    ("clear_transient_ui helper exists", "def clear_transient_ui" in compat),
    ("main cleans transient ui before rebuilding main shell", "clear_transient_ui(page, clear_fab=True)" in main),
    ("app layout cleans transient ui before page switch", "clear_transient_ui(self._page, clear_fab=True)" in app_layout),
]

missing = [name for name, ok in required if not ok]
if missing:
    raise SystemExit("dialog route cleanup guard failed: " + "; ".join(missing))

print("flet_dialog_route_cleanup_smoke_test passed")
