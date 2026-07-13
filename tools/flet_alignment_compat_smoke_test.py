# -*- coding: utf-8 -*-
"""Prevent Android startup crashes caused by ft.Alignment enum-style aliases."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BAD = re.compile(r"ft\.Alignment\.(CENTER|TOP_LEFT|BOTTOM_RIGHT|TOP_RIGHT|BOTTOM_LEFT)")

for path in ROOT.rglob("*.py"):
    if "__pycache__" in path.parts or path.name == "flet_compat.py":
        continue
    text = path.read_text(encoding="utf-8")
    assert not BAD.search(text), (
        f"Use views.flet_compat alignment constants instead of enum-style ft.Alignment aliases: {path.relative_to(ROOT)}"
    )

compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
for token in (
    "ALIGN_CENTER",
    "ALIGN_TOP_LEFT",
    "ALIGN_BOTTOM_RIGHT",
    "patch_flet_alignment_aliases",
):
    assert token in compat, f"missing alignment compatibility token: {token}"

print("flet_alignment_compat_smoke_test passed")
