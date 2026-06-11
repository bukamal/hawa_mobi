# -*- coding: utf-8 -*-
"""Static checks for dialog UX consistency and APK-safe modal behavior."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOGS = ROOT / "views" / "dialogs"

REQUIRED_DIALOG_HELPERS = [
    "dialog_title",
    "dialog_body",
    "cancel_button",
    "save_button",
    "set_button_busy",
    "show_snackbar",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    helper_src = read("views/dialogs/dialog_kit.py")
    missing = [name for name in REQUIRED_DIALOG_HELPERS if f"def {name}" not in helper_src]
    if missing:
        raise SystemExit(f"dialog_kit.py missing helpers: {missing}")

    expected = {
        "views/dialogs/add_edit_expense_dialog.py": ["_saving", "set_button_busy", "parse_non_negative_amount", "dialog_title"],
        "views/dialogs/user_dialog.py": ["_saving", "set_button_busy", "normalize_text", "dialog_title"],
        "views/dialogs/change_password_dialog.py": ["_saving", "set_button_busy", "normalize_text", "dialog_title"],
    }
    errors = []
    for rel, needles in expected.items():
        src = read(rel)
        if "from views.dialogs.dialog_kit import" not in src:
            errors.append(f"{rel}: missing dialog_kit import")
        for needle in needles:
            if needle not in src:
                errors.append(f"{rel}: missing {needle}")
    if errors:
        raise SystemExit("Dialog smoke test failed:\n" + "\n".join(errors))
    print("✅ ui_dialog_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
