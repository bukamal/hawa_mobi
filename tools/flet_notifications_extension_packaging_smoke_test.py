# -*- coding: utf-8 -*-
"""Regression test for the APK red-screen: Unknown control: flet_notifications."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import shutil
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "flet_notifications"
EXPECTED_FILES = {
    "flutter/flet_notifications/pubspec.yaml",
    "flutter/flet_notifications/lib/flet_notifications.dart",
    "flutter/flet_notifications/lib/src/create_control.dart",
    "flutter/flet_notifications/lib/src/flet_notifications.dart",
}


def source_contract_checks() -> None:
    app = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ext = tomllib.loads((EXT / "pyproject.toml").read_text(encoding="utf-8"))

    dependencies = app["project"]["dependencies"]
    assert "flet-notifications==0.2.1" in dependencies
    assert app["tool"]["flet"]["dev_packages"]["flet-notifications"] == "extensions/flet_notifications"

    includes = ext["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "flet_notifications*" in includes
    assert "flutter*" in includes, "Flutter namespace excluded from the extension wheel"
    package_data = ext["tool"]["setuptools"]["package-data"]
    assert package_data.get("flutter.flet_notifications") == ["**/*"]

    for relative in EXPECTED_FILES:
        assert (EXT / "src" / relative).is_file(), relative


def _build_backend_available() -> bool:
    try:
        return importlib.util.find_spec("setuptools.build_meta") is not None
    except ModuleNotFoundError:
        return False


def wheel_contract_checks() -> None:
    # The source checks above are deterministic and catch the original missing
    # Flutter payload regression. Building a real wheel adds a stronger check,
    # but some minimal Python runtimes (including a fresh actions/setup-python
    # installation) do not bundle setuptools. Do not fail with pip's opaque
    # BackendUnavailable traceback in that case; CI installs the backend
    # explicitly before the quality gate and therefore still runs this check.
    if not _build_backend_available():
        print(
            "flet_notifications wheel build skipped: setuptools.build_meta is "
            "not installed; static extension packaging contract passed"
        )
        return

    generated = [EXT / "build", EXT / "dist", EXT / "src" / "flet_notifications.egg-info"]
    for path in generated:
        shutil.rmtree(path, ignore_errors=True)
    try:
        with tempfile.TemporaryDirectory(prefix="hawaa-flet-notifications-wheel-") as tmp:
            env = os.environ.copy()
            env["PIP_NO_INDEX"] = "1"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    str(EXT),
                    "--no-deps",
                    "--no-build-isolation",
                    "--disable-pip-version-check",
                    "-w",
                    tmp,
                ],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise AssertionError(f"Could not build extension wheel:\n{proc.stdout}")
            wheels = list(Path(tmp).glob("flet_notifications-0.2.1-*.whl"))
            assert len(wheels) == 1, (wheels, proc.stdout)
            with zipfile.ZipFile(wheels[0]) as archive:
                names = set(archive.namelist())
            missing = EXPECTED_FILES - names
            assert not missing, f"Flutter payload missing from wheel: {sorted(missing)}"
    finally:
        for path in generated:
            shutil.rmtree(path, ignore_errors=True)


def generated_registration_fixture_checks() -> None:
    import importlib.util

    path = ROOT / "tools" / "verify_flet_notifications_registration.py"
    spec = importlib.util.spec_from_file_location("verify_notifications_registration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="hawaa-flet-registration-") as tmp:
        build = Path(tmp) / "build"
        flutter = build / "flutter"
        ext = build / "flutter-packages" / "flet_notifications"
        (flutter / "lib").mkdir(parents=True)
        (ext / "lib" / "src").mkdir(parents=True)
        (flutter / "pubspec.yaml").write_text(
            "dependencies:\n  flet_notifications:\n    path: ../flutter-packages/flet_notifications\n",
            encoding="utf-8",
        )
        (flutter / "lib" / "main.dart").write_text(
            "import 'package:flet_notifications/flet_notifications.dart' as flet_notifications;\n"
            "final controls = [flet_notifications.createControl];\n",
            encoding="utf-8",
        )
        (ext / "pubspec.yaml").write_text("name: flet_notifications\nversion: 0.2.1\n", encoding="utf-8")
        (ext / "lib" / "flet_notifications.dart").write_text("library flet_notifications;\n", encoding="utf-8")
        (ext / "lib" / "src" / "create_control.dart").write_text("// create control\n", encoding="utf-8")
        (ext / "lib" / "src" / "flet_notifications.dart").write_text("// implementation\n", encoding="utf-8")
        result = module.verify(flutter)
        assert result["extension_root"] == str(ext.resolve())

        (flutter / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
        try:
            module.verify(flutter)
        except RuntimeError as ex:
            assert "Unknown control" in str(ex)
        else:
            raise AssertionError("Verifier accepted an unregistered extension")


if __name__ == "__main__":
    source_contract_checks()
    wheel_contract_checks()
    generated_registration_fixture_checks()
    print("flet_notifications_extension_packaging_smoke_test passed")
