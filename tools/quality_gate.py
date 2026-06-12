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
    subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT), env=env, check=True)


def main() -> int:
    ok = compileall.compile_dir(str(ROOT), quiet=1, force=True)
    if not ok:
        raise SystemExit("compileall failed")
    run_py("tools/architecture_smoke_test.py")
    run_py("tools/local_crud_smoke_test.py")
    run_py("tools/network_contract_test.py")
    run_py("tools/server_import_smoke_test.py")
    run_py("tools/ui_smoke_test.py")
    run_py("tools/ui_admin_smoke_test.py")
    run_py("tools/ui_dialog_smoke_test.py")
    run_py("tools/ui_navigation_smoke_test.py")
    run_py("tools/ui_auth_smoke_test.py")
    run_py("tools/ui_brand_smoke_test.py")
    run_py("tools/report_smoke_test.py")
    run_py("tools/report_share_smoke_test.py")
    run_py("tools/auth_token_smoke_test.py")
    run_py("tools/auth_persistent_token_smoke_test.py")
    run_py("tools/network_mode_bootstrap_smoke_test.py")
    run_py("tools/network_mode_logout_flow_smoke_test.py")
    run_py("tools/dashboard_currency_totals_smoke_test.py")
    run_py("tools/apk_file_export_smoke_test.py")
    print("✅ quality_gate passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
