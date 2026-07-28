#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression contract for the second Flutter/Gradle Android build pass."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-apk.yml"


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SERIOUS_PYTHON_SITE_PACKAGES: ${{ github.workspace }}/build/site-packages" in text
    assert 'if [ ! -d "$SERIOUS_PYTHON_SITE_PACKAGES" ]; then' in text
    assert 'SERIOUS_PYTHON_SITE_PACKAGES="$SERIOUS_PYTHON_SITE_PACKAGES"' in text
    assert '(cd build/flutter/android && ./gradlew --stop) || true' in text

    # The environment must be defined at job scope, before both the initial
    # Flet pass and the direct Flutter rebuild. A step-only definition after
    # the first build would be more fragile and can revive this failure.
    job_pos = text.index("  build:\n")
    env_pos = text.index("    env:\n", job_pos)
    first_build_pos = text.index("flet build apk", job_pos)
    direct_build_pos = text.index('"$FLUTTER_BIN" build apk --release', job_pos)
    assert job_pos < env_pos < first_build_pos < direct_build_pos
    print("serious_python_android_rebuild_env_smoke_test passed")


if __name__ == "__main__":
    main()
