# -*- coding: utf-8 -*-
"""Application-wide Material 3 theme setup."""
from __future__ import annotations

import flet as ft
from .tokens import (
    BRAND_PRIMARY, BRAND_ACCENT,
    LIGHT_BACKGROUND, LIGHT_SURFACE, LIGHT_TEXT_PRIMARY, LIGHT_TEXT_SECONDARY, LIGHT_BORDER,
    DARK_BACKGROUND, DARK_SURFACE, DARK_TEXT_PRIMARY, DARK_TEXT_SECONDARY, DARK_BORDER,
    RADIUS_BUTTON, RADIUS_FIELD,
)


def build_app_theme(*, dark: bool = False):
    """Build a conservative Flet 0.28-compatible Theme.

    Only constructor fields available on the pinned runtime are used. Component
    styling is completed by the shared controls in ``components.py``.
    """
    return ft.Theme(
        color_scheme_seed=BRAND_PRIMARY,
        use_material3=True,
    )


def apply_app_theme(page, mode: str = "light"):
    dark = str(mode or "light").lower() == "dark"
    page.theme = build_app_theme(dark=False)
    try:
        page.dark_theme = build_app_theme(dark=True)
    except Exception:
        pass
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.bgcolor = DARK_BACKGROUND if dark else LIGHT_BACKGROUND
    # Expose semantic runtime values for controls rebuilt after a theme change.
    page._hawaa_design_mode = "dark" if dark else "light"
    page._hawaa_colors = {
        "background": DARK_BACKGROUND if dark else LIGHT_BACKGROUND,
        "surface": DARK_SURFACE if dark else LIGHT_SURFACE,
        "text": DARK_TEXT_PRIMARY if dark else LIGHT_TEXT_PRIMARY,
        "muted": DARK_TEXT_SECONDARY if dark else LIGHT_TEXT_SECONDARY,
        "border": DARK_BORDER if dark else LIGHT_BORDER,
        "primary": BRAND_PRIMARY,
        "accent": BRAND_ACCENT,
    }
    return page._hawaa_colors
