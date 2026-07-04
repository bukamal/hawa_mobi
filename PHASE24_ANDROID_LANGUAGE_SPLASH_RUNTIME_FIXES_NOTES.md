# Phase 24 — Android Language & Splash Runtime Fixes

## Problem observed on device

The Android APK reached the branded splash screen, but the splash card appeared as a very bright yellow panel and the white text had poor contrast. The language setting also did not update visible labels until restarting the app.

## Root causes

1. Several startup controls used 8-digit alpha hex colors such as `#FFFFFF18`, `#FFFFFF33`, and `#FFFFFFB3`. Some Flet Android runtimes render these inconsistently during early startup, producing the neon-yellow card seen on-device.
2. The settings language action persisted `settings.language` and called `set_language()`, but the already-built Flet controls were not rebuilt, so navigation labels and screen texts remained in the old language until the next app launch.
3. Login language selection updated only a small subset of controls and did not persist the selected language setting.

## Fixes

- Reworked `views/splash_view.py` to use an opaque high-contrast white card over the existing brand gradient.
- Removed alpha-hex startup colors from `views/splash_view.py` and `views/ui_kit.py`.
- Added language helpers in `i18n/translator.py`: `get_language`, `is_rtl`, `language_label`, and `language_code_from_label`.
- Updated `main.py` to expose a page-scoped `_hawaa_rebuild_main` hook.
- Updated `SettingsMobileView._save_language()` to apply the language immediately and rebuild the active shell.
- Updated `LoginView` so language changes are saved and visible login labels update immediately.
- Updated `tools/apk_release_preflight.py` to block regressions:
  - no alpha hex colors in splash/ui_kit startup paths,
  - no restart-only language message in settings.

## Validation

Executed successfully:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/apk_release_preflight.py
PYTHONPATH=. python3 tools/ui_brand_smoke_test.py
PYTHONPATH=. python3 tools/quality_gate.py
```

Result:

```text
apk_release_preflight passed
ui_brand_smoke_test passed
quality_gate passed
```

## Manual APK checks

After rebuilding the APK, verify:

1. Splash card is no longer neon yellow.
2. Splash text is readable with dark text on a light card.
3. Changing language in Login updates labels immediately.
4. Changing language in Settings immediately rebuilds the current shell without app restart.
5. RTL/LTR direction changes according to the selected language.
