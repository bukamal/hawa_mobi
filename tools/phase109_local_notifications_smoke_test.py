#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_phase109_")

from database.migrations import ensure_db
from database.connection import get_local_db_path
from database.repositories.expense_repo import ExpenseRepository
from database.repositories.local_notification_repo import LocalNotificationRepository
from services.local_notification_planner import build_notification_plan
from services.local_notification_manager import LocalNotificationCoordinator


def load_patcher():
    path = ROOT / "tools" / "patch_android_local_notifications.py"
    spec = importlib.util.spec_from_file_location("phase109_patcher", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def migration_and_planner_checks():
    ensure_db()
    db_path = get_local_db_path()
    with sqlite3.connect(db_path) as conn:
        version = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
        assert version == "26", version
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"local_notification_schedule", "notification_state"} <= tables
        triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert len([name for name in triggers if name.startswith("trg_notifications_")]) == 9
        now = dt.datetime.now().isoformat(timespec="seconds")
        due = "2026-08-10"
        cur = conn.execute(
            """INSERT INTO expenses(
                 company_name, amount, amount_base, type, date, notes, currency,
                 amount_original, currency_original, exchange_rate_to_usd, status,
                 payment_due_date, source_type, person_name, service_type,
                 operation_type, is_settleable, payment_status, created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "شركة الاختبار", 1000, 1000, "incoming", "2026-08-01", "اختبار",
                "USD", 1000, "USD", 1, "approved", due, "normal", "أحمد",
                "قيد عادي", "normal", 1, "unpaid", now,
            ),
        )
        expense_id = cur.lastrowid
        reminder_id = conn.execute(
            "INSERT INTO payment_reminders(expense_id, reminder_date, note, is_done, created_at) VALUES(?,?,?,?,?)",
            (expense_id, due, "متابعة", 0, now),
        ).lastrowid

    rows = ExpenseRepository().get_pending_payment_reminders()
    assert len(rows) == 1
    plan = build_notification_plan(
        rows,
        now=dt.datetime(2026, 8, 9, 10, 0),
        notification_time="09:00",
        pre_due_days="3",
        overdue_days="3,7",
        privacy="private",
    )
    assert [item.kind for item in plan] == ["due_soon", "due_today", "overdue_3", "overdue_7"]
    assert len({item.notification_id for item in plan}) == 4
    assert all("whatsapp" not in item.payload.lower() for item in plan)
    assert all(item.expense_id == expense_id and item.reminder_id == reminder_id for item in plan)
    assert "المتبقي 1,000 USD" in plan[0].body

    # A long-overdue claim emits only the latest elapsed milestone, not four at once.
    long_overdue = build_notification_plan(
        rows,
        now=dt.datetime(2026, 9, 1, 10, 0),
        notification_time="09:00",
        pre_due_days="3",
        overdue_days="3,7",
    )
    assert len(long_overdue) == 1 and long_overdue[0].kind == "overdue_7"

    schedule_repo = LocalNotificationRepository()
    schedule_repo.upsert(plan[0], status="scheduled")
    assert schedule_repo.get_by_key(plan[0].key)["notification_id"] == plan[0].notification_id
    schedule_repo.set_dirty(False)
    assert schedule_repo.is_dirty() is False
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO payments(reference,target_expense_id,company_name,amount_original,
                 currency_original,amount_base,direction,date,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            ("PAY-109", expense_id, "شركة الاختبار", 1000, "USD", 1000, "received", "2026-08-09", now),
        )
    assert schedule_repo.is_dirty() is True, "payments trigger did not mark notifications dirty"
    assert ExpenseRepository().get_pending_payment_reminders() == []



def coordinator_reconciliation_checks():
    db_path = get_local_db_path()
    now = dt.datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO expenses(company_name,amount,amount_base,type,date,currency,amount_original,
                 currency_original,exchange_rate_to_usd,status,payment_due_date,source_type,person_name,
                 service_type,operation_type,is_settleable,payment_status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("شركة ثانية", 500, 500, "incoming", "2026-07-28", "USD", 500, "USD", 1,
             "approved", "2026-08-10", "normal", "سارة", "قيد عادي", "normal", 1, "unpaid", now),
        )
        expense_id = cur.lastrowid
        conn.execute(
            "INSERT INTO payment_reminders(expense_id,reminder_date,note,is_done,created_at) VALUES(?,?,?,?,?)",
            (expense_id, "2026-08-10", "متابعة", 0, now),
        )

    class FakeNative:
        def __init__(self):
            self.scheduled = []
            self.shown = []
            self.cancelled = []
        async def schedule_notification(self, notification_id, title, body, scheduled_date, **kwargs):
            self.scheduled.append(notification_id)
            return True
        async def show_notification(self, notification_id, title, body, **kwargs):
            self.shown.append(notification_id)
            return True
        async def cancel(self, notification_id):
            self.cancelled.append(notification_id)
            return True

    class DummyPage:
        overlay = []

    native = FakeNative()
    manager = LocalNotificationCoordinator(DummyPage())
    manager.available = True
    manager.native = native
    manager.permission_granted = True
    import asyncio
    stats = asyncio.run(manager.resync(force=True))
    assert stats["scheduled"] == 4, stats
    assert len(LocalNotificationRepository().list_all()) == 4

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO payments(reference,target_expense_id,company_name,amount_original,
                 currency_original,amount_base,direction,date,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("PAY-109-SECOND", expense_id, "شركة ثانية", 500, "USD", 500, "received", "2026-07-28", now),
        )
    stats = asyncio.run(manager.resync(force=True))
    assert stats["cancelled"] == 4, stats
    assert LocalNotificationRepository().list_all() == []
    assert len(native.cancelled) >= 4

def patcher_checks():
    module = load_patcher()
    with tempfile.TemporaryDirectory(prefix="hawaa_android_patch_") as temp:
        root = Path(temp)
        manifest = root / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            '<application android:label="Hawaa"></application></manifest>',
            encoding="utf-8",
        )
        # Flutter debug/profile manifests are overlays and may omit <application>.
        # They must never be selected as the patch target.
        debug_manifest = root / "android" / "app" / "src" / "debug" / "AndroidManifest.xml"
        debug_manifest.parent.mkdir(parents=True)
        debug_manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            '<uses-permission android:name="android.permission.INTERNET" />'
            '</manifest>',
            encoding="utf-8",
        )
        profile_manifest = root / "android" / "app" / "src" / "profile" / "AndroidManifest.xml"
        profile_manifest.parent.mkdir(parents=True)
        profile_manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" />',
            encoding="utf-8",
        )
        gradle = root / "android" / "app" / "build.gradle"
        gradle.parent.mkdir(parents=True, exist_ok=True)
        gradle.write_text(
            "android {\n  defaultConfig {\n  }\n  compileOptions {\n  }\n}\n"
            "dependencies {\n}\n",
            encoding="utf-8",
        )
        first = module.patch(root)
        second = module.patch(root)
        assert Path(first["manifest"]) == manifest
        assert first["manifest_changed"] and first["gradle_changed"]
        assert not second["manifest_changed"] and not second["gradle_changed"]
        manifest_text = manifest.read_text(encoding="utf-8")
        gradle_text = gradle.read_text(encoding="utf-8")
        assert "ScheduledNotificationBootReceiver" in manifest_text
        assert "ScheduledNotificationReceiver" in manifest_text
        assert "ActionBroadcastReceiver" in manifest_text
        assert "POST_NOTIFICATIONS" in manifest_text and "RECEIVE_BOOT_COMPLETED" in manifest_text
        assert "coreLibraryDesugaringEnabled true" in gradle_text
        assert "desugar_jdk_libs:2.1.4" in gradle_text


def static_contract_checks():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build-apk.yml").read_text(encoding="utf-8")
    dart = (ROOT / "extensions" / "flet_notifications" / "src" / "flutter" / "flet_notifications" / "lib" / "src" / "flet_notifications.dart").read_text(encoding="utf-8")
    manager = (ROOT / "services" / "local_notification_manager.py").read_text(encoding="utf-8")
    center = (ROOT / "views" / "notification_center_mobile_view.py").read_text(encoding="utf-8")
    app_layout = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")
    assert '"flet-notifications==0.2.0"' in pyproject
    assert "android.permission.POST_NOTIFICATIONS" in pyproject
    assert "android.permission.RECEIVE_BOOT_COMPLETED" in pyproject
    assert "patch_android_local_notifications.py" in workflow
    assert "SERIOUS_PYTHON_SITE_PACKAGES" in workflow
    assert "${{ github.workspace }}/build/site-packages" in workflow
    assert "./gradlew --stop" in workflow
    assert 'test -d "$SERIOUS_PYTHON_SITE_PACKAGES"' in workflow or '[ ! -d "$SERIOUS_PYTHON_SITE_PACKAGES" ]' in workflow
    assert "inexactAllowWhileIdle" in dart
    assert "AndroidScheduleMode.exactAllowWhileIdle" not in dart
    assert "فتح المطالبة" in manager and "تسجيل دفعة" in manager
    assert "واتساب" not in center and "whatsapp" not in manager.lower()
    assert 'page_id == "notification_center"' in app_layout


if __name__ == "__main__":
    migration_and_planner_checks()
    coordinator_reconciliation_checks()
    patcher_checks()
    static_contract_checks()
    print("phase109_local_notifications_smoke_test passed")
