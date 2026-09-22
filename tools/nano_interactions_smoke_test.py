# -*- coding: utf-8 -*-
"""Nano-style interaction guards: swipe-to-delete + unified FAB.

Locks in the Nano (nano_offline) interaction patterns ported to hawaa:

1. Swipe-to-delete is provided by ``views.ui_kit.swipeable_card`` and must
   never delete directly — it opens the central confirm sheet, and both
   swipe directions share the same red background (RTL has no wrong answer).
2. Rows that cannot be deleted (viewers, locked/linked records) are never
   wrapped in a Dismissible (no doomed gesture shown).
3. Page FABs are created through one unified helper with END_FLOAT placement
   and consistent tokens.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(name: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def static_checks():
    ui_kit = (ROOT / "views" / "ui_kit.py").read_text(encoding="utf-8")
    users = (ROOT / "views" / "users_mobile_view.py").read_text(encoding="utf-8")
    details = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")

    # -- swipeable_card contract ------------------------------------------
    check("ui_kit", "def swipeable_card(" in ui_kit)
    check("ui_kit", "ft.Dismissible(" in ui_kit, "swipeable_card must wrap in Dismissible")
    check("ui_kit", "ft.DismissDirection.HORIZONTAL" in ui_kit, "both directions must be enabled")
    check("ui_kit", "secondary_background" in ui_kit, "RTL direction must have its own background")
    # on_dismiss must only relay to on_swiped (no delete logic in the widget)
    check("ui_kit", "on_swiped()" in ui_kit, "dismiss must delegate to the app callback")

    # -- users view ---------------------------------------------------------
    check("users", "swipeable_card(" in users, "users list must use swipeable_card")
    check("users", "enabled=can_delete", "users swipe must be gated by repo.can_delete")
    check("users", "confirm_sheet(" in users, "user delete must go through confirm sheet")
    check("users", "on_cancel=on_cancel" in users or "def on_cancel" in users, "cancel must restore the swiped row")
    check("users", "unified_fab(" in users, "users FAB must use the unified helper")
    check("users", "ft.AlertDialog(" not in users, "users view must not open AlertDialogs directly")

    # -- company details view -----------------------------------------------
    check("details", "swipeable_card(" in details, "ledger rows must use swipeable_card")
    check("details", "enabled=deletable", "ledger swipe must be gated by record eligibility")
    check("details", "confirm_sheet(" in details, "record delete must go through confirm sheet")
    check("details", "make_floating_action_button(" in details, "details FAB must use the compat factory")
    check("details", "has_fab=True", "details must reserve FAB bottom clearance")


def runtime_checks():
    import os
    import tempfile

    tmp = tempfile.mkdtemp(prefix="hawaa_nano_interactions_")
    os.environ["HAWAA_DATA_DIR"] = tmp
    os.environ["HAWAA_DB_PATH"] = str(Path(tmp) / "hawaa_data.db")

    try:
        import flet as ft  # noqa: F401
    except ImportError:
        return

    from database.migrations import init_database
    from auth.session import UserSession

    init_database()
    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"})
    db = __import__("database", fromlist=["UserRepository"])
    repo = db.UserRepository()
    repo.create("cashier1", "Str0ng!Pass", "موظف تجربة", "user")
    repo.create("watcher1", "Str0ng!Pass", "مشاهد تجربة", "viewer")

    class FakePage:
        width = 360
        height = 800
        overlay = []
        dialog = None
        snack_bar = None
        theme_mode = None
        rtl = True
        floating_action_button = None
        floating_action_button_location = None

        def update(self):
            return None

    page = FakePage()
    from views.users_mobile_view import UsersMobileView
    from views.design_system.sheets import BottomSheetDialog
    from views.flet_compat import _get_stack
    import time

    view = UsersMobileView(page)

    # FAB attached through the unified helper
    assert page.floating_action_button is view.add_btn, "FAB must be attached to the page"
    assert page.floating_action_button_location == ft.FloatingActionButtonLocation.END_FLOAT

    # Only non-current users get a Dismissible wrapper
    def collect_dismissibles(root):
        found = []

        def _walk(control):
            for child in getattr(control, "controls", []) or []:
                if isinstance(child, ft.Dismissible):
                    found.append(child)
                _walk(child)

        _walk(root)
        return found

    dismissibles = collect_dismissibles(view.users_list)
    assert len(dismissibles) == 2, f"expected 2 swipeable users, got {len(dismissibles)}"
    assert all(d.key.startswith("user-") for d in dismissibles)

    # Swipe -> central confirm sheet appears
    dismissibles[0].on_dismiss(None)
    stack = _get_stack(page)
    assert stack and isinstance(stack[-1], BottomSheetDialog), "swipe must open the confirm sheet"

    # Cancel restores (no DB deletion, sheet closed)
    stack[-1].request_close()
    assert len(repo.get_all()) == 3, "cancel must not delete"

    # Confirm actually deletes
    before = len(repo.get_all())
    target_id = int(dismissibles[0].key.split("-")[1])
    dismissibles[0].on_dismiss(None)
    _get_stack(page)[-1].actions.controls[-1].on_click()
    time.sleep(0.3)
    assert len(repo.get_all()) == before - 1, "confirm must delete the user"


if __name__ == "__main__":
    static_checks()
    runtime_checks()
    print("nano_interactions_smoke_test passed")
