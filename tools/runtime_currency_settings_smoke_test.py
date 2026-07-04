# -*- coding: utf-8 -*-
"""Smoke-test runtime display-currency updates without Android restart."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp(prefix="hawaa_currency_runtime_")
os.environ["HAWAA_DATA_DIR"] = TMP

try:
    from database.migrations import ensure_db
    from database.repositories.settings_repo import SettingsRepository
    from currency import currency

    ensure_db()

    repo_a = SettingsRepository()
    repo_b = SettingsRepository()

    repo_a.set("display_currency", "USD")
    currency.invalidate_cache()
    assert currency.get_display_currency() == "USD", "initial display currency should be USD"

    # This simulates SettingsMobileView writing via its own repository instance.
    repo_a.set("display_currency", "SYP")
    assert repo_b.get("display_currency") == "SYP", "settings cache must invalidate across repository instances"
    assert currency.get_display_currency() == "SYP", "CurrencyManager must see display_currency immediately without restart"

    currency.set_display_currency("EUR")
    assert repo_a.get("display_currency") == "EUR", "CurrencyManager writes must update repository readers immediately"
    assert currency.get_display_currency() == "EUR", "set_display_currency must be immediately observable"

    currency.save_runtime_settings(display_currency="SAR", decimals=0, number_format="western", abbreviate_numbers=False)
    assert currency.get_display_currency() == "SAR", "save_runtime_settings must apply display currency immediately"
    assert currency.get_currency_decimals() == 0, "decimal setting must apply immediately"

    print("✅ runtime_currency_settings_smoke_test passed")
finally:
    try:
        shutil.rmtree(TMP)
    except Exception:
        pass
