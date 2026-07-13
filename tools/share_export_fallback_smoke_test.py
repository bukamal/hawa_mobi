#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
share_source = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

assert 'getattr(ft, "Share", None)' in share_source, (
    "ft.Share must be feature-detected, not assumed"
)
assert "ft.Share()" not in share_source, "Do not instantiate ft.Share directly"
assert "_android_insert_file_into_downloads" in share_source, (
    "Android MediaStore export fallback missing"
)
assert "MediaStore.Downloads.EXTERNAL_CONTENT_URI" in share_source, (
    "Scoped-storage MediaStore path missing"
)
assert "manual_internal_path" in share_source, (
    "Missing internal-path manual result mode"
)
assert "module 'flet' has no attribute 'Share'" not in share_source, (
    "Do not leak raw AttributeError text to users"
)
for permission in (
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
):
    assert permission not in pyproject, (
        f"Broad storage permission must not be requested: {permission}"
    )

print("✅ share_export_fallback_smoke_test passed")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
