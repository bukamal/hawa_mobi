# -*- coding: utf-8 -*-
"""Run the project quality gate used before producing a release ZIP."""
from __future__ import annotations

import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_py(script: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    print(f"▶ {script}", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=str(ROOT),
        env=env,
        timeout=80,
        check=True,
    )


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
        "tools/mobile_pairing_contract_smoke_test.py",
        "tools/qr_pairing_ui_smoke_test.py",
        "tools/manual_pairing_code_smoke_test.py",
        "tools/pairing_capabilities_strict_smoke_test.py",
        "tools/company_logo_print_smoke_test.py",
        "tools/apk_release_preflight.py",
        "tools/backup_restore_smoke_test.py",
        "tools/network_diagnostics_smoke_test.py",
        "tools/flet_filepicker_runtime_pin_smoke_test.py",
        "tools/flet_build_command_smoke_test.py",
        "tools/flet_entrypoint_compat_smoke_test.py",
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
    raise SystemExit(main())
