# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
share = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
company = (ROOT / "views" / "company_details_mobile_view.py").read_text(
    encoding="utf-8"
)

assert "_android_cache_uri_for_whatsapp" in share
assert "_android_copy_to_cache_for_share" in share
assert "hawaa_whatsapp_share" in share
assert "android_cache_whatsapp" in share
assert "if text and not open_whatsapp" in share, (
    "WhatsApp file share must not send EXTRA_TEXT"
)
assert "intent.setClipData" in share, "Intent should include ClipData read grant"
assert "grantUriPermission" in share, "WhatsApp package should receive read grant"
assert "open_whatsapp=True" in company
print("android_whatsapp_cache_share_smoke_test passed")
