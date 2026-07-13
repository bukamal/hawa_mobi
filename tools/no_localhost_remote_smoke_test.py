# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in [
    "database/connection.py",
    "database/connection_rest.py",
    "database/migrations.py",
    "main.py",
]:
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "http://localhost:8000" not in text, (
        f"{rel} must not default to localhost:8000"
    )

rest = (ROOT / "database/connection_rest.py").read_text(encoding="utf-8")
assert "_resolve_server_url" in rest
assert "if not root:" in rest and "عنوان الخادم غير مضبوط" in rest
assert "_is_localhost_url(root) or not root" in rest
print("no localhost remote smoke test ok")
