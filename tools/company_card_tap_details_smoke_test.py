# -*- coding: utf-8 -*-
"""Guard that company cards open details by tapping the card body.

The old tiny "تفاصيل" action was easy to hide on narrow Android screens once
more operation buttons were added.  The card itself must now be tappable and
route through AppLayout.open_company_details.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
accounts_src = (ROOT / "views" / "accounts_mobile_view.py").read_text(encoding="utf-8")
uikit_src = (ROOT / "views" / "ui_kit.py").read_text(encoding="utf-8")

assert "def data_card(content, padding=15, elevation=2, margin=None, on_click=None):" in uikit_src
assert 'container_kwargs["on_click"] = on_click' in uikit_src
assert 'container_kwargs["ink"] = True' in uikit_src

assert "on_click=lambda e, c=company, r=vals['records'], q=details_query: self._show_details(c, r, q)" in accounts_src
assert "اضغط على البطاقة لفتح الحساب" in accounts_src
assert "layout.open_company_details(company_name, records=records, search_query=search_query)" in accounts_src

# The crowded old details button should not be part of the quick-action row.
assert 'action_text_button("تفاصيل"' not in accounts_src

print("company_card_tap_details_smoke_test passed")
