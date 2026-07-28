# -*- coding: utf-8 -*-
"""Regression test for the APK red-screen: Unknown control: flet_notifications."""
from __future__ import annotations

import contextlib
import io
import os
import shutil
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

    workflow = (ROOT / ".github" / "workflows" / "build-apk.yml").read_text(encoding="utf-8")
    assert 'python -m pip install --upgrade pip "setuptools>=65" wheel' in workflow, (
        "GitHub Actions must install the PEP 517 build backend before the offline wheel test"
    )
    assert "import setuptools.build_meta" in workflow


def wheel_contract_checks() -> None:
    generated = [EXT / "build", EXT / "dist", EXT / "src" / "flet_notifications.egg-info"]
    for path in generated:
        shutil.rmtree(path, ignore_errors=True)
    try:
        try:
            from setuptools import build_meta
            import wheel  # noqa: F401 - validates the bdist_wheel provider
        except Exception as exc:
            raise AssertionError(
                "Extension wheel backend is unavailable. Install build tooling with: "
                'python -m pip install --upgrade "setuptools>=65" wheel'
            ) from exc

        with tempfile.TemporaryDirectory(prefix="hawaa-flet-notifications-wheel-") as tmp:
            previous_cwd = Path.cwd()
            build_output = io.StringIO()
            try:
                os.chdir(EXT)
                with contextlib.redirect_stdout(build_output), contextlib.redirect_stderr(build_output):
                    wheel_name = build_meta.build_wheel(tmp)
            except Exception as exc:
                raise AssertionError(
                    "Could not build extension wheel with setuptools.build_meta:\n"
                    f"{build_output.getvalue()}{exc}"
                ) from exc
            finally:
                os.chdir(previous_cwd)

            wheel_path = Path(tmp) / wheel_name
            assert wheel_path.is_file(), wheel_path
            assert wheel_path.name.startswith("flet_notifications-0.2.1-")
            with zipfile.ZipFile(wheel_path) as archive:
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
