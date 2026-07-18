# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
accounts = (ROOT / 'views' / 'accounts_mobile_view.py').read_text(encoding='utf-8')
layout = (ROOT / 'views' / 'app_layout.py').read_text(encoding='utf-8')
ui = (ROOT / 'views' / 'ui_kit.py').read_text(encoding='utf-8')
main = (ROOT / 'main.py').read_text(encoding='utf-8')

assert 'layout.open_company_details(company_name' in accounts, 'company details must route through AppLayout'
show_details_block = accounts.split('def _show_details', 1)[1].split('def _close_dialog', 1)[0]
assert 'layout.open_company_details' in show_details_block, 'route call missing from _show_details'
assert 'def open_company_details' in layout, 'AppLayout must provide open_company_details'
assert 'TEXT' in layout and 'MUTED' in layout and 'BORDER' in layout, 'company details header must import UI identity constants used at runtime'
assert 'from views.ui_kit import' in layout and 'TEXT' in layout.split('from views.ui_kit import', 1)[1].split(')', 1)[0], 'TEXT must be imported from ui_kit, not left as a runtime NameError'
assert 'self.safe_top_spacer' in layout and 'height=28' in layout, 'AppLayout must reserve Android status-bar safe area'
assert 'window_full_screen' in main, 'main must explicitly avoid fullscreen mode'
assert '\\u2066' in ui and 'max_lines=1' in ui, 'money values must be LTR-isolated and single-line'
print('✅ company_details_route_safearea_smoke_test passed')
