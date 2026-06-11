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
    print("✅ quality_gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
