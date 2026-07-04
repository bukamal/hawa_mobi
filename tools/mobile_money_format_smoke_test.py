# -*- coding: utf-8 -*-
"""Smoke tests for mobile money formatting.

The Android UI has narrow cards.  Large monetary values must respect the
"اختصار الأعداد الكبيرة" setting consistently, otherwise dashboard/company
cards wrap into unreadable fragments.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="hawaa_money_format_")
os.environ["HAWAA_DATA_DIR"] = TMP

try:
    from database.migrations import ensure_db
    from currency import currency

    ensure_db()

    currency.save_runtime_settings(display_currency="SYP", decimals=2, number_format="western", abbreviate_numbers=True)
    assert currency.abbreviate_numbers() is True
    assert currency.format_amount(200_000, "SYP") == "200K ل.س"
    assert currency.format_amount(3_000_000, "SYP") == "3M ل.س"
    assert currency.format_amount(1_600_000, "SYP") == "1.6M ل.س"
    assert currency.format_amount(-1_400_000, "SYP") == "-1.4M ل.س"
    assert "1,600,000" not in currency.format_amount(1_600_000, "SYP")

    currency.save_runtime_settings(display_currency="SYP", decimals=2, number_format="western", abbreviate_numbers=False)
    assert currency.abbreviate_numbers() is False
    assert currency.format_amount(1_600_000, "SYP") == "1,600,000.00 ل.س"
    assert currency.format_amount_compact(1_600_000, "SYP") == "1.6M ل.س"
    assert currency.format_amount_full(1_600_000, "SYP") == "1,600,000.00 ل.س"

    print("✅ mobile_money_format_smoke_test passed")
finally:
    try:
        shutil.rmtree(TMP)
    except Exception:
        pass
