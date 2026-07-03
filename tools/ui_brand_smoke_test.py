import os
# -*- coding: utf-8 -*-
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
assets = [
    ROOT / 'assets' / 'app_icon.png',
    ROOT / 'assets' / 'app_logo.png',
    ROOT / 'assets' / 'app_logo_small.png',
    ROOT / 'assets' / 'icon.png',
    ROOT / 'assets' / 'icon_android.png',
    ROOT / 'assets' / 'icon_web.png',
    ROOT / 'assets' / 'splash_android.png',
    ROOT / 'assets' / 'brand' / 'app_wordmark.png',
    ROOT / 'assets' / 'icons' / 'app_icon_192.png',
    ROOT / 'assets' / 'icons' / 'app_icon_512.png',
]
for asset in assets:
    if not asset.exists() or asset.stat().st_size < 500:
        raise AssertionError(f'missing or invalid brand asset: {asset}')

ui_kit = ROOT / 'views' / 'ui_kit.py'
text = ui_kit.read_text(encoding='utf-8')
ast.parse(text)
assert 'def app_mark(' in text
assert 'ASSET_APP_SYMBOL' in text
assert 'ft.Image' in text
assert 'ft.Icons.FLIGHT' not in text
assert "ft.Text('H'" not in text
assert 'def app_brand(' in text
assert 'brand_wordmark' in text
assert 'brand_background' in text

for rel in ['views/splash_view.py', 'views/login_view.py', 'views/activation_view.py', 'views/app_layout.py']:
    content = (ROOT / rel).read_text(encoding='utf-8')
    ast.parse(content)
    assert 'app_brand' in content, f'app_brand not used in {rel}'

pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
assert 'icon_android.png' not in pyproject  # Flet uses assets/icon_android.png by convention
assert '[tool.flet.splash]' in pyproject
assert 'adaptive_icon_background' in pyproject
print('✅ ui_brand_smoke_test passed')
