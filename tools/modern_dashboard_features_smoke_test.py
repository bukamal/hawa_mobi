# -*- coding: utf-8 -*-
"""Static dashboard feature guard for Phase 92."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "views" / "dashboard_mobile_view.py").read_text(encoding="utf-8")
for needle in [
    "لوحة تحكم هوى الشام",
    "مؤشرات الذمم والخدمات والأرباح والتشغيل",
    "أرباح الخدمات",
    "ملفات خدمة مفتوحة",
    "خدمات منخفضة الربح",
    "سدد عني",
    "قيود مقفلة مترابطة",
    "عمليات مركبة",
    "ServiceCaseRepository",
    "DirectServiceRepository",
    "ThirdPartyPaymentRepository",
]:
    assert needle in text, needle
print("modern_dashboard_features_smoke_test passed")
