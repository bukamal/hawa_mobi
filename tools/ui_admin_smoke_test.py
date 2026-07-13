import os
# -*- coding: utf-8 -*-
"""Static UI checks for administration screens."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "views/users_mobile_view.py": ["page_header", "summary_bar", "data_card", "empty_state"],
    "views/audit_log_mobile_view.py": ["page_header", "data_card", "empty_state", "pill"],
    "views/settings_mobile_view.py": ["_settings_tile", "page_header", "data_card", "localhost"],
    "views/ui_kit.py": ["show_snackbar", "data_card", "page_header"],
}

def main():
    missing = []
    for rel, needles in REQUIRED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: {needle}")
    if missing:
        raise SystemExit("UI admin smoke test failed:\n" + "\n".join(missing))
    print("UI admin smoke test passed")

if __name__ == "__main__":
    main()
