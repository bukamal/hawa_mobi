# Phase 45 — Android Flet Alignment Runtime Fix

## Issue

The APK could start into the Flet fatal error boundary with:

```text
'type object 'Alignment' has no attribute 'CENTER'
```

The pinned Android runtime (`flet==0.28.3`) exposes alignment values through the lower-case alignment API/constructor path, not enum-style aliases such as `ft.Alignment.CENTER`.

## Fix

- Added alignment compatibility constants in `views/flet_compat.py`:
  - `ALIGN_CENTER`
  - `ALIGN_TOP_LEFT`
  - `ALIGN_BOTTOM_RIGHT`
- Added a defensive alias patch for legacy snippets through `patch_flet_alignment_aliases()`.
- Replaced all direct project usages of `ft.Alignment.CENTER`, `ft.Alignment.TOP_LEFT`, and `ft.Alignment.BOTTOM_RIGHT`.
- Added `tools/flet_alignment_compat_smoke_test.py` and wired it into `tools/quality_gate.py`.

## Result

Startup no longer crashes before the splash/login flow because of missing `Alignment` aliases.
