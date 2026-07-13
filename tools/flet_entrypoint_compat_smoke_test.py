#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensure the Android entrypoint works with the pinned FilePicker-stable Flet line."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "main.py").read_text(encoding="utf-8")
assert "def run_hawaa_app" in text, (
    "main.py must use run_hawaa_app() compatibility wrapper"
)
assert 'hasattr(ft, "run")' in text, "wrapper must support newer ft.run runtimes"
assert "ft.app(target=main" in text, (
    "wrapper must fall back to ft.app(target=main, ...) for Flet 0.28.x"
)
assert (
    'ft.run(main, assets_dir="assets")\n' not in text.split("def run_hawaa_app", 1)[0]
), "do not call ft.run directly before wrapper"
print("flet_entrypoint_compat_smoke_test passed")
