# -*- coding: utf-8 -*-
"""Semantic design tokens.

Views must use semantic tokens rather than raw colors and arbitrary dimensions.
The legacy aliases are intentionally kept in ``views.ui_kit`` for backwards
compatibility with older screens while Phase 100 migrates the complete project.

Palette follows the Nano visual language: deep teal brand, slate neutrals,
semantic success/danger/warning states.
"""
from __future__ import annotations

# Brand — deep teal identity (Nano style).
BRAND_PRIMARY = "#0F766E"
BRAND_PRIMARY_DARK = "#115E59"
BRAND_PRIMARY_LIGHT = "#CCFBF1"
BRAND_PRIMARY_TINT = "#F0FDFA"
BRAND_PRIMARY_BORDER = "#99F6E4"
BRAND_ACCENT = "#14B8A6"
BRAND_GOLD = "#D9A441"

# Light semantic surfaces.
LIGHT_BACKGROUND = "#F8FAFC"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_SURFACE_ALT = "#F1F5F9"
LIGHT_SURFACE_RAISED = "#FFFFFF"
LIGHT_TEXT_PRIMARY = "#0F172A"
LIGHT_TEXT_SECONDARY = "#64748B"
LIGHT_TEXT_MUTED = "#475569"
LIGHT_TEXT_FAINT = "#94A3B8"
LIGHT_BORDER = "#E2E8F0"
LIGHT_DIVIDER = "#E5E7EB"

# Dark semantic surfaces.
DARK_BACKGROUND = "#0F172A"
DARK_SURFACE = "#1E293B"
DARK_SURFACE_ALT = "#243244"
DARK_SURFACE_RAISED = "#334155"
DARK_TEXT_PRIMARY = "#F1F5F9"
DARK_TEXT_SECONDARY = "#94A3B8"
DARK_TEXT_MUTED = "#CBD5E1"
DARK_TEXT_FAINT = "#64748B"
DARK_BORDER = "#334155"
DARK_DIVIDER = "#475569"

# Financial and state colors.
FINANCIAL_RECEIVABLE = "#2563EB"   # لنا
FINANCIAL_PAYABLE = "#EA580C"      # له
STATE_SUCCESS = "#16A34A"
STATE_SUCCESS_SOFT = "#ECFDF5"
STATE_DANGER = "#EF4444"
STATE_DANGER_SOFT = "#FEF2F2"
STATE_WARNING = "#D97706"
STATE_WARNING_SOFT = "#FFFBEB"
STATE_INFO = "#0D9488"
STATE_INFO_SOFT = "#F0FDFA"
STATE_DISABLED = "#94A3B8"

# Elevation tint (soft, low-opacity shadows resolve against the border).
SHADOW_LIGHT = "#E2E8F0"
SHADOW_DARK = "#475569"

# Type scale.
TEXT_CAPTION = 11
TEXT_SECONDARY = 12
TEXT_BODY = 14
TEXT_BUTTON = 14
TEXT_CARD_TITLE = 16
TEXT_SECTION_TITLE = 18
TEXT_PAGE_TITLE = 22
TEXT_MONEY_HERO = 26

# Spacing scale (4pt grid).
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

# Shape and touch.
RADIUS_FIELD = 10
RADIUS_BUTTON = 10
RADIUS_CARD = 16
RADIUS_DIALOG = 20
RADIUS_SHEET = 24
TOUCH_TARGET = 48

# Responsive dimensions.
PHONE_MAX = 599
TABLET_MAX = 1023
DESKTOP_MIN = 1024
CONTENT_MAX_WIDTH = 1360
FORM_MAX_WIDTH = 720
DIALOG_MAX_WIDTH = 560
PHONE_GUTTER = 16
TABLET_GUTTER = 24
DESKTOP_GUTTER = 32
