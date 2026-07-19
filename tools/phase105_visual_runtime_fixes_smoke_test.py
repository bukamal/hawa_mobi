# -*- coding: utf-8 -*-
"""Phase 105 visual/runtime acceptance checks."""
from pathlib import Path
import os
import tempfile

_tmp = tempfile.TemporaryDirectory(prefix="hawaa_phase105_")
os.environ["HAWAA_DATA_DIR"] = _tmp.name

import flet as ft
from database.migrations import ensure_db
ensure_db()
from currency import currency
from views.ui_kit import money_text
from views.design_system.responsive import bottom_safe_space

ROOT = Path(__file__).resolve().parents[1]
accounts = (ROOT / "views" / "accounts_mobile_view.py").read_text(encoding="utf-8")
reports = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")
app_layout = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")
translator = (ROOT / "i18n" / "translator.py").read_text(encoding="utf-8")

class FakePage:
    width = 390

formatted = currency.format_amount_ui(-5497, "USD", compact=False)
assert formatted == "\u2066-$5,497.00\u2069", repr(formatted)
text = money_text(formatted)
assert text.rtl is False
assert text.overflow == ft.TextOverflow.VISIBLE
assert text._get_attr("nowrap") is True
assert bottom_safe_space(FakePage(), has_fab=False) >= 100
assert bottom_safe_space(FakePage(), has_fab=True) >= 120
assert "FloatingActionButtonLocation.END_FLOAT" in accounts
assert "bottom_safe_spacer(self._page, has_fab=True)" in accounts
assert "self.filters_surface.visible = False" in reports
assert "self.edit_filters_button.visible = True" in reports
assert "height=76" in app_layout
assert "'accounts': 'الحسابات'" in translator
_tmp.cleanup()
print("phase105_visual_runtime_fixes_smoke_test passed")
