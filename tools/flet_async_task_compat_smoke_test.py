#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prevent Android crashes from scheduling coroutines without Flet's loop.

On the pinned Flet 0.28.x Android runtime, synchronous constructors and click
handlers may run without a public asyncio loop.  Raw ``asyncio.create_task`` then
raises ``RuntimeError: no running event loop`` before the app reaches login.
"""
from pathlib import Path
import os
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
BAD_CREATE_TASK = re.compile(r"asyncio\.create_task\s*\(")

for path in ROOT.rglob("*.py"):
    if "__pycache__" in path.parts or path.name in {"flet_compat.py", "flet_async_task_compat_smoke_test.py"}:
        continue
    text = path.read_text(encoding="utf-8")
    assert not BAD_CREATE_TASK.search(text), (
        "Use views.flet_compat.run_async_task(...) instead of raw "
        f"asyncio.create_task(...): {path.relative_to(ROOT)}"
    )

compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
for token in ("def run_async_task", "page.run_task", "asyncio.get_running_loop", "hawaa-async-fallback"):
    assert token in compat, f"missing async scheduling compatibility token: {token}"

for rel in ("main.py", "views/splash_view.py", "views/activation_view.py", "views/settings_mobile_view.py"):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "run_async_task" in text, f"{rel} must use run_async_task for delayed/background async work"

print("flet_async_task_compat_smoke_test passed")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
