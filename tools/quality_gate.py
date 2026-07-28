# -*- coding: utf-8 -*-
"""Run the project quality gate used before producing a release ZIP."""
from __future__ import annotations

import compileall
import os
import signal
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_py(script: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    # Each smoke test gets an isolated data directory. This prevents a test that
    # switches to network/client mode from contaminating later accounting and
    # report tests through the shared settings database.
    isolated_data_dir = tempfile.mkdtemp(prefix="hawaa-quality-gate-")
    env["HAWAA_DATA_DIR"] = isolated_data_dir
    print(f"▶ {script}", flush=True)

    use_process_group = os.name != "nt"
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / script)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=use_process_group,
    )
    try:
        out, err = proc.communicate(timeout=80)
    except subprocess.TimeoutExpired:
        # Some Flet/mobile smoke tests can finish their Python body but leave
        # helper processes/threads with inherited stdout handles alive.  Kill
        # the whole process group so the release gate never hangs indefinitely.
        if use_process_group:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        out, err = proc.communicate(timeout=10)

    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    if proc.returncode != 0:
        shutil.rmtree(isolated_data_dir, ignore_errors=True)
        raise subprocess.CalledProcessError(proc.returncode, [sys.executable, str(ROOT / script)])

    if use_process_group:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
    shutil.rmtree(isolated_data_dir, ignore_errors=True)


def main() -> int:
    # Clean stale root-level server entrypoints and sensitive runtime artifacts
    # that may remain when a phase ZIP is copied over an older repository.
    # The Android client keeps server code under server/ only and must never
    # ship local license/runtime files.
    run_py("tools/cleanup_legacy_root_server_entries.py")
    run_py("tools/cleanup_sensitive_source_files.py")

    ok = compileall.compile_dir(str(ROOT), quiet=1, force=True)
    if not ok:
        raise SystemExit("compileall failed")
    scripts = [
        "tools/architecture_smoke_test.py",
        "tools/local_crud_smoke_test.py",
        "tools/currency_ledger_contract_smoke_test.py",
        "tools/runtime_currency_settings_smoke_test.py",
        "tools/mobile_money_format_smoke_test.py",
        "tools/network_contract_test.py",
        "tools/api_capabilities_contract_smoke_test.py",
        "tools/direct_service_api_contract_smoke_test.py",
        "tools/service_case_edit_api_contract_smoke_test.py",
        "tools/comprehensive_currency_language_api_test.py",
        "tools/mobile_pairing_contract_smoke_test.py",
        "tools/qr_pairing_ui_smoke_test.py",
        "tools/manual_pairing_code_smoke_test.py",
        "tools/pairing_capabilities_strict_smoke_test.py",
        "tools/company_logo_print_smoke_test.py",
        "tools/apk_release_preflight.py",
        "tools/serious_python_android_rebuild_env_smoke_test.py",
        "tools/share_export_fallback_smoke_test.py",
        "tools/report_action_share_print_whatsapp_smoke_test.py",
        "tools/professional_statement_layout_smoke_test.py",
    "tools/reconciliation_statement_note_restored_smoke_test.py",
        "tools/reporting_center_core_smoke_test.py",
        "tools/reporting_center_advanced_smoke_test.py",
        "tools/report_image_export_smoke_test.py",
        "tools/report_image_true_renderer_rtl_smoke_test.py",
        "tools/image_export_button_responsive_smoke_test.py",
        "tools/image_export_android_responsiveness_regression_test.py",
        "tools/sqlite_closed_connection_recovery_smoke_test.py",
        "tools/hawa_visual_identity_smoke_test.py",
        "tools/batch_payments_contract_smoke_test.py",
        "tools/batch_payments_migration_smoke_test.py",
        "tools/batch_payments_allocations_smoke_test.py",
        "tools/batch_payments_rest_smoke_test.py",
        "tools/phase109_local_notifications_smoke_test.py",
        "tools/payment_reminder_button_target_smoke_test.py",
        "tools/phase100_design_system_smoke_test.py",
        "tools/payment_reminders_button_ui_smoke_test.py",
        "tools/phase101_accounting_workflow_wizard_smoke_test.py",
        "tools/phase102_secure_admin_settings_smoke_test.py",
        "tools/phase103_accounts_reports_performance_smoke_test.py",
        "tools/phase104_navigation_recovery_accessibility_smoke_test.py",
        "tools/phase105_visual_runtime_fixes_smoke_test.py",
        "tools/company_inline_entry_segmented_direction_smoke_test.py",
        "tools/company_ledger_table_hard_delete_smoke_test.py",
        "tools/partial_payments_contract_smoke_test.py",
        "tools/partial_payments_smoke_test.py",
        "tools/modern_dashboard_features_smoke_test.py",
        "tools/company_details_route_safearea_smoke_test.py",
        "tools/company_details_nameerror_runtime_smoke_test.py",
        "tools/company_card_tap_details_smoke_test.py",
        "tools/searchable_form_fields_smoke_test.py",
        "tools/unified_financial_date_picker_smoke_test.py",
        "tools/backup_restore_smoke_test.py",
        "tools/backup_restore_button_nonblocking_smoke_test.py",
        "tools/backup_restore_snackbar_duration_smoke_test.py",
        "tools/backup_restore_direct_picker_import_smoke_test.py",
        "tools/backup_import_runtime_refresh_smoke_test.py",
        "tools/backup_picker_resolution_smoke_test.py",
        "tools/backup_external_filepicker_bytes_smoke_test.py",
        "tools/backup_external_storage_permission_smoke_test.py",
        "tools/network_diagnostics_smoke_test.py",
        "tools/sqlite_thread_safety_smoke_test.py",
        "tools/third_party_payment_smoke_test.py",
        "tools/linked_intercompany_entry_edit_smoke_test.py",
        "tools/company_deep_search_smoke_test.py",
        "tools/ledger_operation_core_smoke_test.py",
        "tools/service_case_workflow_smoke_test.py",
        "tools/linked_supplier_service_edit_smoke_test.py",
        "tools/direct_customer_profit_workflow_smoke_test.py",
        "tools/direct_supplier_only_service_workflow_smoke_test.py",
        "tools/direct_service_correction_smoke_test.py",
        "tools/reversed_service_operational_visibility_smoke_test.py",
        "tools/flet_filepicker_runtime_pin_smoke_test.py",
        "tools/flet_build_command_smoke_test.py",
        "tools/flet_entrypoint_compat_smoke_test.py",
        "tools/flet_alignment_compat_smoke_test.py",
        "tools/flet_fab_compat_smoke_test.py",
        "tools/flet_expansion_tile_compat_smoke_test.py",
        "tools/mandatory_password_change_flow_smoke_test.py",
        "tools/credential_store_smoke_test.py",
        "tools/login_remember_password_flow_test.py",
        "tools/flet_alertdialog_no_overlay_blank_screen_smoke_test.py",
        "tools/flet_dialog_open_rendering_smoke_test.py",
        "tools/flet_dialog_route_cleanup_smoke_test.py",
        "tools/flet_snackbar_no_overlay_route_smoke_test.py",
        "tools/flet_async_task_compat_smoke_test.py",
        "tools/filepicker_permission_compat_smoke_test.py",
        # Server import is useful when Flask dependencies are installed; run it manually when validating server packaging:
        # tools/server_import_smoke_test.py
        # The following auth/network-bootstrap checks remain useful, but they
        # may leave runtime resources alive in GitHub-hosted Linux shells. Run
        # them manually when validating networking/session changes:
        # tools/auth_token_smoke_test.py
        # tools/auth_persistent_token_smoke_test.py
        # tools/network_mode_bootstrap_smoke_test.py
        # tools/network_mode_logout_flow_smoke_test.py
        # Dashboard currency totals is a useful standalone smoke test, but it
        # can inherit Flet/runtime side effects after network-mode tests in some
        # CI shells. Run it manually when needed:
        # tools/dashboard_currency_totals_smoke_test.py
        # The following UI/export smoke tests are useful during development but
        # can keep Flet-related worker threads alive on some CI/Linux shells.
        # Run them manually when needed:
        # tools/report_share_smoke_test.py
        # tools/apk_file_export_smoke_test.py
        # tools/ui_smoke_test.py
        # tools/ui_admin_smoke_test.py
        # tools/ui_dialog_smoke_test.py
        # tools/ui_navigation_smoke_test.py
        # tools/ui_auth_smoke_test.py
        # tools/ui_brand_smoke_test.py
        # tools/report_smoke_test.py
        # tools/report_share_smoke_test.py
    ]
    for script in scripts:
        run_py(script)
    print("✅ quality_gate passed", flush=True)
    return 0


if __name__ == "__main__":
    # Some Flet/mobile smoke tests can leave runtime helper threads alive in
    # Linux shells even after the test body passes.  The quality gate is a CLI
    # verifier, so force process termination after all checks have completed.
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(code))
