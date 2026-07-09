# -*- coding: utf-8 -*-
"""Guard against direct FloatingActionButton constructor calls in app views.

Flet 0.28.x Android rejects ``margin`` on FloatingActionButton.  All FABs must
be created through views.flet_compat.make_floating_action_button so unsupported
kwargs are filtered centrally.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

violations = []
for path in ROOT.rglob("*.py"):
    if path.name == "flet_compat.py" or path == Path(__file__).resolve():
        continue
    if "__pycache__" in path.parts:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "ft.FloatingActionButton(" in text:
        violations.append(str(path.relative_to(ROOT)))

if violations:
    raise SystemExit("Direct ft.FloatingActionButton usage found: " + ", ".join(violations))

print("flet_fab_compat_smoke_test passed")
