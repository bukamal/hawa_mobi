# -*- coding: utf-8 -*-
"""Guard ExpansionTile constructor compatibility for Android Flet runtime."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
violations = []
for path in ROOT.rglob("*.py"):
    if "__pycache__" in str(path) or path.name in {
        "flet_compat.py",
        "flet_expansion_tile_compat_smoke_test.py",
    }:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "ft.ExpansionTile(" in text:
        violations.append(str(path.relative_to(ROOT)))
if violations:
    raise SystemExit(
        "استخدم make_expansion_tile بدلاً من ft.ExpansionTile مباشرة: "
        + ", ".join(violations)
    )
print("flet_expansion_tile_compat_smoke_test passed")
