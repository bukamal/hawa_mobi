# Phase 25 — Android Runtime Display Currency Fix

## Problem
Changing the display currency from Android settings was persisted, but visible totals and formatted amounts continued to use the previous currency until the APK process restarted.

## Root cause
`SettingsRepository` used an instance-local cache. `SettingsMobileView` wrote the new `display_currency` through its own repository instance, while the global `currency` manager kept another repository instance with stale cached settings.

## Fixes
- `database/repositories/settings_repo.py`
  - Replaced per-instance settings cache with a process-wide shared cache.
  - Added `SettingsRepository.invalidate_cache()`.
  - Any settings write invalidates the key for all repository instances.

- `currency.py`
  - Added `CurrencyManager.invalidate_cache()`.
  - Added `set_base_currency()`, `set_display_currency()`, and `save_runtime_settings()`.
  - Currency settings now become observable immediately without restarting Android.

- `views/settings_mobile_view.py`
  - Currency settings now save through `currency.save_runtime_settings()`.
  - Display currency changes immediately refresh the current page via `_hawaa_refresh_current_page`.
  - Exchange-rate changes also invalidate currency cache and refresh the current view.

- `views/app_layout.py`
  - Added runtime hooks:
    - `_hawaa_app_layout`
    - `_hawaa_refresh_current_page`
    - `_hawaa_open_page`
  - The current page can now be rebuilt after runtime settings changes without restarting the APK.

- `tools/runtime_currency_settings_smoke_test.py`
  - Verifies that display currency changes are immediately visible through all repository and currency-manager instances.

- `tools/apk_release_preflight.py`
  - Blocks regressions where display-currency changes require restart.

## Validation

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/runtime_currency_settings_smoke_test.py
PYTHONPATH=. python3 tools/apk_release_preflight.py
PYTHONPATH=. python3 tools/quality_gate.py
```

Result:

```text
runtime_currency_settings_smoke_test passed
apk_release_preflight passed
quality_gate passed
```

## Manual APK test
1. Open Android APK.
2. Go to Settings → Currency.
3. Change display currency from USD to SYP/EUR/SAR.
4. Save.
5. Navigate to Accounts/Dashboard without restarting.
6. Amounts must use the new display currency immediately.
7. Change exchange rate for the display currency and save all rates.
8. Dashboard/Accounts should refresh using the updated rate without restart.

## Accounting rule preserved
This fix does not reprice old transactions. It only changes runtime display conversion. Historical transaction snapshots remain unchanged:

- `amount_original`
- `currency_original`
- `exchange_rate_to_usd`
- `amount_base`
