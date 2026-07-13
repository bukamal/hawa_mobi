# -*- coding: utf-8 -*-
"""Guard against company details route failing with NameError for UI constants.

The Android screenshot showed: name 'TEXT' is not defined when tapping
company details.  The route header uses TEXT/MUTED/BORDER, so these must be
imported in app_layout.py.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")
tree = ast.parse(source)
imports = set()
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "views.ui_kit":
        imports.update(alias.name for alias in node.names)
required = {"TEXT", "MUTED", "BORDER", "CARD_BG", "PRIMARY"}
missing = sorted(required - imports)
assert not missing, f"missing app_layout ui_kit imports: {missing}"
open_block = source.split("def open_company_details", 1)[1].split("def _change_password", 1)[0]
for name in required:
    assert name in open_block or name in {"CARD_BG", "PRIMARY"}, f"{name} should be covered by route smoke test"
print("✅ company_details_nameerror_runtime_smoke_test passed")
