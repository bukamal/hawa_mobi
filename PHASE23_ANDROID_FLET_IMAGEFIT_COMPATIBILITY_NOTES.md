# Phase 23 — Android Flet ImageFit Compatibility Fix

## Problem

A real Android run failed at startup with:

```text
module 'flet' has no attribute 'ImageFit'
```

The crash was caused by `views/ui_kit.py` using `ft.ImageFit.CONTAIN`. Some Flet runtimes used in APK builds do not expose this enum, while the `Image` control still accepts lower-case string fit values.

## Fix

- Added `image_fit()` helper in `views/ui_kit.py`.
- Replaced `fit=ft.ImageFit.CONTAIN` with `fit=image_fit("contain")`.
- Updated `ui_brand_smoke_test.py` and `apk_release_preflight.py` to forbid `ft.ImageFit` in Android UI code.

## Expected Result

The APK should pass the splash/login startup phase without crashing on `ImageFit`.
