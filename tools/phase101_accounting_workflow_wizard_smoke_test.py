# -*- coding: utf-8 -*-
"""Runtime and static guard for Phase 101 adaptive accounting workflows."""
from __future__ import annotations

import ast
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakePage:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.overlay = []
        self.dialog = None
        self.snack_bar = None
        self.update_count = 0

    def update(self):
        self.update_count += 1


def reset_database():
    from database.connection import DatabaseConnection
    try:
        DatabaseConnection().close()
    except Exception:
        pass
    DatabaseConnection._instance = None
    DatabaseConnection._local_conn = None


def main() -> int:
    workflow_path = ROOT / "views" / "design_system" / "workflow.py"
    direct_path = ROOT / "views" / "dialogs" / "direct_service_dialog.py"
    service_path = ROOT / "views" / "dialogs" / "service_case_dialog.py"
    for path in (workflow_path, direct_path, service_path):
        assert path.exists(), path
        ast.parse(path.read_text(encoding="utf-8"))

    workflow_source = workflow_path.read_text(encoding="utf-8")
    assert "class WorkflowController" in workflow_source
    assert "class WorkflowStep" in workflow_source
    assert "adaptive_dialog_metrics" in workflow_source
    assert "financial_summary" in workflow_source

    direct_source = direct_path.read_text(encoding="utf-8")
    service_source = service_path.read_text(encoding="utf-8")
    assert "WorkflowController" in direct_source
    assert "WorkflowController" in service_source
    assert '"العميل والخدمة"' in direct_source
    assert '"بيانات العميل"' in service_source

    try:
        import flet  # noqa: F401
    except Exception:
        print("Phase 101 runtime instantiation skipped: flet is not installed")
        print("phase101_accounting_workflow_wizard_smoke_test passed")
        return 0

    temp_dir = tempfile.mkdtemp(prefix="hawaa_phase101_workflow_")
    old_data_dir = os.environ.get("HAWAA_DATA_DIR")
    old_server_flag = os.environ.get("HAWAA_SERVER_PROCESS")
    os.environ["HAWAA_DATA_DIR"] = temp_dir
    os.environ.pop("HAWAA_SERVER_PROCESS", None)

    try:
        reset_database()
        from database.migrations import init_database
        from views.dialogs.direct_service_dialog import DirectServiceDialog
        from views.dialogs.service_case_dialog import ServiceCaseDialog

        init_database()
        for width, height in ((320, 568), (360, 800), (412, 915), (800, 1100)):
            page = FakePage(width, height)

            direct = DirectServiceDialog(page, company_name="شركة اختبار")
            assert len(direct.workflow.steps) == 3
            assert direct.workflow.step_index == 0
            assert direct.content.width <= width
            assert direct.content.height <= height
            direct.company_field.value = "شركة اختبار"
            direct.person_field.value = "مسافر تجريبي"
            direct.workflow._go_next()
            assert direct.workflow.step_index == 1
            direct.sale_field.value = "100"
            direct.cost_field.value = "70"
            direct.workflow._go_next()
            assert direct.workflow.step_index == 2
            assert direct.review_host.controls, "direct-service review must be rendered"
            assert direct.save_btn.visible is True

            service = ServiceCaseDialog(page, client_company_name="شركة عميلة")
            assert len(service.workflow.steps) == 4
            assert service.workflow.step_index == 0
            assert service.content.width <= width
            assert service.content.height <= height
            service.client_field.value = "شركة عميلة"
            service.person_field.value = "مسافر ملف خدمة"
            service.workflow._go_next()
            assert service.workflow.step_index == 1
            service.supplier_field.value = "شركة موردة"
            service.sale_field.value = "150"
            service.cost_field.value = "100"
            service.workflow._go_next()
            assert service.workflow.step_index == 2
            service.workflow._go_next()
            assert service.workflow.step_index == 3
            assert service.review_host.controls, "service-case review must be rendered"
            assert service.save_btn.visible is True

        print("phase101_accounting_workflow_wizard_smoke_test passed")
        return 0
    finally:
        reset_database()
        if old_data_dir is None:
            os.environ.pop("HAWAA_DATA_DIR", None)
        else:
            os.environ["HAWAA_DATA_DIR"] = old_data_dir
        if old_server_flag is None:
            os.environ.pop("HAWAA_SERVER_PROCESS", None)
        else:
            os.environ["HAWAA_SERVER_PROCESS"] = old_server_flag
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
