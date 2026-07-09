#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
share_source = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

assert "getattr(ft, \"Share\", None)" in share_source, "ft.Share must be feature-detected, not assumed"
assert "ft.Share()" not in share_source, "Do not instantiate ft.Share directly"
assert "copy_to_public_downloads" in share_source, "Missing public Downloads fallback"
assert "manual_public_downloads" in share_source, "Missing public Downloads result mode"
assert "manual_internal_path" in share_source, "Missing internal-path manual result mode"
assert "module 'flet' has no attribute 'Share'" not in share_source, "Do not leak raw AttributeError text to users"
assert "android.permission.WRITE_EXTERNAL_STORAGE" in pyproject, "Missing Android 10 Downloads fallback permission"
assert "android.permission.READ_EXTERNAL_STORAGE" in pyproject, "Missing read external storage permission"

print("✅ share_export_fallback_smoke_test passed")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
