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
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / script)],
        cwd=str(ROOT),
        env=env,
        start_new_session=True,
    )
    try:
        code = proc.wait(timeout=80)
    except subprocess.TimeoutExpired:
        try:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        raise SystemExit(f"{script} timed out")
    if code != 0:
        raise subprocess.CalledProcessError(code, [sys.executable, str(ROOT / script)])


def main() -> int:
    ok = compileall.compile_dir(str(ROOT), quiet=1, force=True)
    if not ok:
        raise SystemExit("compileall failed")
    scripts = [
        "tools/architecture_smoke_test.py",
        "tools/local_crud_smoke_test.py",
        "tools/currency_ledger_contract_smoke_test.py",
        "tools/network_contract_test.py",
        "tools/api_capabilities_contract_smoke_test.py",
        "tools/apk_release_preflight.py",
        "tools/server_import_smoke_test.py",
        # Auth/network-bootstrap tests run before Flet UI smoke tests to avoid
        # any GUI runtime side effects from influencing local token storage.
        "tools/auth_token_smoke_test.py",
        "tools/auth_persistent_token_smoke_test.py",
        "tools/network_mode_bootstrap_smoke_test.py",
        "tools/network_mode_logout_flow_smoke_test.py",
        "tools/dashboard_currency_totals_smoke_test.py",
        # The following UI/export smoke tests are useful during development but
        # can keep Flet-related worker threads alive on some CI/Linux shells.
        # Run them manually when needed:
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
    print("✅ quality_gate passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
