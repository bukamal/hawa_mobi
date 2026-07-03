import os
# -*- coding: utf-8 -*-
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

required_files = [
    ROOT / 'views' / 'splash_view.py',
    ROOT / 'views' / 'login_view.py',
    ROOT / 'views' / 'activation_view.py',
    ROOT / 'views' / 'dialogs' / 'change_password_dialog.py',
    ROOT / 'auth' / 'session.py',
    ROOT / 'auth' / 'password_policy.py',
]

for path in required_files:
    if not path.exists():
        raise AssertionError(f'missing file: {path}')
    ast.parse(path.read_text(encoding='utf-8'))

splash = (ROOT / 'views' / 'splash_view.py').read_text(encoding='utf-8')
assert 'get_rest_client().health()' in splash
assert 'UserSession.is_authenticated()' in splash
assert "on_complete({'activated': False" in splash

login = (ROOT / 'views' / 'login_view.py').read_text(encoding='utf-8')
assert 'MAX_ATTEMPTS' in login and 'LOCK_SECONDS' in login
assert "set_setting('login/last_username'" in login
assert '.login(username, password)' in login and 'get_rest_client()' in login
assert '_set_busy' in login

activation = (ROOT / 'views' / 'activation_view.py').read_text(encoding='utf-8')
assert 'get_license_details' in activation
assert 'set_clipboard' in activation
assert '_set_busy' in activation

change = (ROOT / 'views' / 'dialogs' / 'change_password_dialog.py').read_text(encoding='utf-8')
assert 'evaluate_password' in change
assert 'old == new' in change
assert '_validate_live' in change

main = (ROOT / 'main.py').read_text(encoding='utf-8')
assert 'after_splash' in main
assert 'UserSession.logout()' in main
assert 'retry=show_splash' in main

print('✅ ui_auth_smoke_test passed')
