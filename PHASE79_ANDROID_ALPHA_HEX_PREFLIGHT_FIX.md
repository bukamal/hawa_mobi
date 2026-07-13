# Phase 79 — Android alpha-hex preflight fix

Fixed APK preflight failure caused by an 8-digit alpha hex color in `views/ui_kit.py`.
Flet Android has had inconsistent behavior with alpha hex colors during APK startup, so `SHADOW` now uses a solid safe color.

This phase does not change database, API, currency, reports, or business logic.
