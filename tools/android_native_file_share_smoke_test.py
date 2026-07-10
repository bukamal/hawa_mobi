# -*- coding: utf-8 -*-
"""Guard real Android file attachment sharing for reports.

The APK runtime may not expose ft.Share.  WhatsApp/report actions must therefore
attempt Android ACTION_SEND with EXTRA_STREAM/content URI before falling back to
manual/text flows.  This is a static guard; it does not require Android runtime.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
share = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
company = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")

required = [
    "_try_android_native_share",
    "_android_insert_file_into_downloads",
    "MediaStore.Downloads.EXTERNAL_CONTENT_URI",
    "Intent.ACTION_SEND",
    "Intent.EXTRA_STREAM",
    "FLAG_GRANT_READ_URI_PERMISSION",
    "com.whatsapp",
    "com.whatsapp.w4b",
]
missing = [term for term in required if term not in share]
assert not missing, f"missing Android native file-share terms: {missing}"
assert "whatsapp_text_manual_file" not in share, "WhatsApp file action must not auto-fallback to text-only wa.me"
assert "اختر واتساب من نافذة المشاركة لإرسال الملف" not in company, "WhatsApp button must not send old instruction text"
assert "message = f\"كشف حساب - {self.company_name}\"" in company, "WhatsApp caption must be short and file-oriented"
print("✅ android_native_file_share_smoke_test passed")
