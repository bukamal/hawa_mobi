# -*- coding: utf-8 -*-
"""Ensure Android builds use a FilePicker-stable Flet runtime.

The project needs true external-file import for backups and logos.  The Flet
0.80+ line has shown an Android/web runtime regression where FilePicker can be
exposed in Python but rejected by the Flutter client as "Unknown control:
FilePicker".  This test prevents silently building that broken APK line.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
COMPAT = ROOT / "views" / "flet_compat.py"


def _read_flet_pin() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'"flet==([^"\n]+)"', text)
    assert m, "pyproject.toml must pin flet with flet==<version>; loose ranges are not allowed for APK builds"
    return m.group(1)


def _version_tuple(v: str):
    parts = []
    for chunk in re.split(r"[.\-]", v):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def main():
    pin = _read_flet_pin()
    assert _version_tuple(pin) < (0, 80, 0), (
        f"Android FilePicker import requires the FilePicker-stable Flet line; got flet=={pin}. "
        "Use flet==0.28.3 unless the FilePicker runtime regression is verified fixed on real APK."
    )
    compat = COMPAT.read_text(encoding="utf-8")
    assert "_allow_legacy_filepicker_overlay" in compat, "flet_compat.py must allow legacy overlay FilePicker for the pinned runtime"
    assert "Unknown control: FilePicker" in compat, "flet_compat.py must document/guard the Android FilePicker regression"
    print("flet_filepicker_runtime_pin_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
