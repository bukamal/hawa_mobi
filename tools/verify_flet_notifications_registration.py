# -*- coding: utf-8 -*-
"""Fail a release build when the custom Flutter notification control was not registered."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


PACKAGE = "flet_notifications"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def verify(flutter_root: Path) -> dict[str, str]:
    flutter_root = flutter_root.resolve()
    if not flutter_root.is_dir():
        raise RuntimeError(f"Generated Flutter project does not exist: {flutter_root}")

    packages_root = flutter_root.parent / "flutter-packages"
    extension_root = packages_root / PACKAGE
    required = [
        extension_root / "pubspec.yaml",
        extension_root / "lib" / "flet_notifications.dart",
        extension_root / "lib" / "src" / "create_control.dart",
        extension_root / "lib" / "src" / "flet_notifications.dart",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        discovered = sorted(str(p) for p in packages_root.glob("*/pubspec.yaml")) if packages_root.exists() else []
        raise RuntimeError(
            "Flet did not copy/register the flet_notifications Flutter payload.\n"
            f"Missing: {missing}\n"
            f"Discovered Flutter extension manifests: {discovered}\n"
            "Check the extension wheel: it must contain flutter/flet_notifications/** and the app must use "
            "[tool.flet.dev_packages]."
        )

    ext_pubspec = _read(extension_root / "pubspec.yaml")
    if not re.search(r"(?m)^name:\s*flet_notifications\s*$", ext_pubspec):
        raise RuntimeError(f"Invalid extension pubspec name in {extension_root / 'pubspec.yaml'}")

    app_pubspec_path = flutter_root / "pubspec.yaml"
    if not app_pubspec_path.is_file():
        raise RuntimeError(f"Generated app pubspec is missing: {app_pubspec_path}")
    app_pubspec = _read(app_pubspec_path)
    if not re.search(r"(?m)^\s+flet_notifications\s*:", app_pubspec):
        raise RuntimeError(
            f"{app_pubspec_path} has no flet_notifications dependency; the custom control will render as Unknown control."
        )

    dart_files = list((flutter_root / "lib").rglob("*.dart"))
    dart_text = "\n".join(_read(path) for path in dart_files)
    import_markers = (
        "package:flet_notifications/flet_notifications.dart",
        "flet_notifications.createControl",
        "flet_notifications.ensureInitialized",
    )
    if not any(marker in dart_text for marker in import_markers):
        raise RuntimeError(
            "Generated Dart bootstrap does not import/register flet_notifications. "
            "An APK built from this project would show 'Unknown control: flet_notifications'."
        )

    return {
        "flutter_root": str(flutter_root),
        "extension_root": str(extension_root),
        "app_pubspec": str(app_pubspec_path),
        "dart_files_scanned": str(len(dart_files)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("flutter_root", nargs="?", default="build/flutter")
    args = parser.parse_args()
    result = verify(Path(args.flutter_root))
    print("flet_notifications registration verified:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
