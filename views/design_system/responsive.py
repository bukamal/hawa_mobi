# -*- coding: utf-8 -*-
"""Responsive layout helpers compatible with the pinned Flet 0.28 line."""
from __future__ import annotations

import flet as ft
from .tokens import (
    PHONE_MAX, TABLET_MAX, CONTENT_MAX_WIDTH, FORM_MAX_WIDTH,
    PHONE_GUTTER, TABLET_GUTTER, DESKTOP_GUTTER,
)


def page_width(page, fallback: float = 390.0) -> float:
    try:
        value = float(getattr(page, "width", 0) or 0)
        return value if value > 0 else fallback
    except Exception:
        return fallback


def form_factor(page) -> str:
    width = page_width(page)
    if width <= PHONE_MAX:
        return "phone"
    if width <= TABLET_MAX:
        return "tablet"
    return "desktop"


def is_phone(page) -> bool:
    return form_factor(page) == "phone"


def is_large(page) -> bool:
    return form_factor(page) in {"tablet", "desktop"}


def page_gutter(page) -> int:
    factor = form_factor(page)
    if factor == "phone":
        return PHONE_GUTTER
    if factor == "tablet":
        return TABLET_GUTTER
    return DESKTOP_GUTTER


def content_width(page, max_width: int = CONTENT_MAX_WIDTH) -> float:
    return min(max_width, max(280, page_width(page) - (page_gutter(page) * 2)))


def form_width(page, max_width: int = FORM_MAX_WIDTH) -> float:
    return min(max_width, max(280, page_width(page) - (page_gutter(page) * 2)))


def grid_columns(page) -> int:
    factor = form_factor(page)
    return 1 if factor == "phone" else (2 if factor == "tablet" else 3)


def responsive_container(content, page, *, max_width: int = CONTENT_MAX_WIDTH, padding=None, expand=True, alignment=None):
    """Center content and cap its width on tablet/desktop without breaking phone."""
    alignment = alignment or ft.alignment.top_center
    gutter = page_gutter(page)
    inner = ft.Container(
        content=content,
        width=content_width(page, max_width=max_width),
        padding=padding if padding is not None else ft.Padding(gutter, 0, gutter, 0),
    )
    return ft.Container(content=inner, alignment=alignment, expand=expand)


def responsive_grid(controls, page, *, min_item_width: int = 270, spacing: int = 12, run_spacing: int = 12):
    """Return a wrapping grid with deterministic item widths for Flet 0.28."""
    count = max(1, grid_columns(page))
    available = content_width(page)
    width = max(min_item_width, (available - spacing * (count - 1)) / count)
    items = []
    for control in controls:
        items.append(ft.Container(content=control, width=width))
    return ft.Row(items, wrap=True, spacing=spacing, run_spacing=run_spacing, alignment=ft.MainAxisAlignment.START)


def safe_top_height(page) -> int:
    # Flet 0.28 Android may still render edge-to-edge. Keep a small defensive
    # inset on phones; native desktop/tablet shells do not need the old 28px gap.
    return 24 if is_phone(page) else 8
