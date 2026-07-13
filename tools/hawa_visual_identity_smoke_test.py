# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ui = (ROOT / "views" / "ui_kit.py").read_text(encoding="utf-8")
    assert 'PRIMARY = "#0A3F70"' in ui
    assert 'SUCCESS = "#1FA56A"' in ui
    assert 'DANGER = "#E54848"' in ui
    assert 'def money_text(' in ui
    assert 'def modern_action_button(' in ui
    tr = (ROOT / "i18n" / "translator.py").read_text(encoding="utf-8")
    assert 'إدارة ذمم وخدمات السياحة والسفر' in tr
    reports = (ROOT / "reports" / "account_statement.py").read_text(encoding="utf-8")
    assert '#0A3F70' in reports
    assert 'unicode-bidi:isolate' in reports
    accounts = (ROOT / "views" / "accounts_mobile_view.py").read_text(encoding="utf-8")
    assert 'money_text("0", size=24, color=PRIMARY)' in accounts
    print('hawa_visual_identity_smoke_test passed')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
