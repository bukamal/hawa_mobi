# -*- coding: utf-8 -*-
"""Ensure the Android build workflow uses arguments supported by flet-cli 0.28.x."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKED = [
    ROOT / ".github" / "workflows" / "build-apk.yml",
    ROOT / "README.md",
    ROOT / "PHASE42_ANDROID_REAL_FILEPICKER_RESTORE_NOTES.md",
]


def main() -> int:
    offenders: list[str] = []
    for path in CHECKED:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "flet build apk --yes" in text or " --yes" in text and "flet build apk" in text:
            offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        raise SystemExit("Unsupported flet build flag --yes found in: " + ", ".join(offenders))
    print("flet_build_command_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
