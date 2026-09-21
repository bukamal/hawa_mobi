"""Design tokens for the HF UI — light *and* dark aware.

Every color/size used across the app must come from this module instead of
being repeated as a raw literal, so a rebrand or a dark-mode tweak is a
one-file edit instead of a grep-and-replace across every view.

Usage:
    from hf_offline.core.theme import Colors

    ft.Text("...", color=Colors.TEXT_PRIMARY)

Dark mode
---------
``Colors`` and ``Shadow`` are resolved *at access time* against whichever
mode is active (``set_mode``/``get_mode``), via a metaclass ``__getattr__``
that only fires when normal lookup fails. Views build their controls fresh
on every navigation, so a mode switch just needs a full-screen rebuild
(see ``bootstrap.apply_theme`` + the shell's theme-change hook).
"""

from __future__ import annotations

import flet as ft

# --- Mode state ----------------------------------------------------------#
_state: dict[str, str] = {"mode": "light"}


def get_mode() -> str:
    """The currently active resolved mode: ``"light"`` or ``"dark"``."""
    return _state["mode"]


def is_dark() -> bool:
    return _state["mode"] == "dark"


def set_mode(mode: str) -> None:
    """Set the active mode. Anything other than the literal ``"dark"`` is light.

    Deliberately permissive instead of raising on an unexpected value —
    a stray typo'd or legacy-stored value degrades to the safe default
    (light) rather than crashing the whole app.
    """
    _state["mode"] = "dark" if mode == "dark" else "light"


class _LightTokens:
    """Reference copy of every light-mode value — exists so the actual values
    are readable/greppable in one place and ``_LIGHT`` can be built from it."""

    # Brand / primary — modern indigo. Reads as "tech/engineering" without
    # colliding with the success-green, danger-red or warning-amber semantic
    # colors below, and pairs cleanly with the cyan accent.
    PRIMARY = "#4F46E5"
    PRIMARY_DARK = "#3730A3"
    PRIMARY_BG = "#EEF2FF"
    PRIMARY_BORDER = "#C7D2FE"

    # Accent — cyan used for gradients, highlights and the central FAB blend.
    ACCENT = "#06B6D4"
    ACCENT_DARK = "#0891B2"
    ACCENT_BG = "#ECFEFF"

    # Neutral surfaces
    WHITE = "#FFFFFF"
    BACKGROUND = "#F6F7FB"
    BACKGROUND_ALT = "#EEF1F6"

    # Borders
    BORDER = "#E3E8F0"
    BORDER_ALT = "#E5E7EB"
    BORDER_STRONG = "#CBD5E1"

    # Text
    TEXT_PRIMARY = "#0F172A"
    TEXT_SECONDARY = "#64748B"
    TEXT_MUTED = "#475569"
    TEXT_MUTED_DARK = "#334155"
    TEXT_FAINT = "#94A3B8"

    # Success / green
    SUCCESS = "#16A34A"
    SUCCESS_DARK = "#15803D"
    SUCCESS_ALT = "#059669"
    SUCCESS_DARKER = "#166534"
    SUCCESS_BG = "#ECFDF5"

    # Danger / red
    DANGER = "#EF4444"
    DANGER_DARK = "#DC2626"
    DANGER_DARKER = "#B91C1C"
    DANGER_BG = "#FEF2F2"
    DANGER_BORDER = "#FECACA"

    # Warning / amber
    WARNING = "#F59E0B"
    WARNING_DARK = "#D97706"
    WARNING_DARKER = "#B45309"
    WARNING_BG = "#FFFBEB"
    WARNING_BG_ALT = "#FFF7ED"

    # Info / sky — used for neutral-attention items (pending, info notes)
    INFO = "#0EA5E9"
    INFO_DARK = "#0369A1"
    INFO_BG = "#F0F9FF"

    # Purple — distinct accent for reports/advanced analytics
    PURPLE = "#7C3AED"
    PURPLE_LIGHT = "#8B5CF6"
    PURPLE_BG = "#F5F3FF"


_LIGHT: dict[str, str] = {k: v for k, v in vars(_LightTokens).items() if k.isupper()}

# Dark-mode counterpart: same token names, surfaces *darker*, text/accents
# *lighter and slightly desaturated* so nothing glows on an OLED at night,
# and semantic colors keep their identity while backing off enough to stay
# legible on a dark surface.
_DARK: dict[str, str] = {
    "PRIMARY": "#818CF8",
    "PRIMARY_DARK": "#A5B4FC",
    "PRIMARY_BG": "#1E1B4B",
    "PRIMARY_BORDER": "#312E81",
    "ACCENT": "#22D3EE",
    "ACCENT_DARK": "#67E8F9",
    "ACCENT_BG": "#083344",
    "WHITE": "#1E293B",  # "card surface" — token role, not literal color
    "BACKGROUND": "#0B1120",
    "BACKGROUND_ALT": "#1E293B",
    "BORDER": "#334155",
    "BORDER_ALT": "#334155",
    "BORDER_STRONG": "#475569",
    "TEXT_PRIMARY": "#F1F5F9",
    "TEXT_SECONDARY": "#94A3B8",
    "TEXT_MUTED": "#CBD5E1",
    "TEXT_MUTED_DARK": "#E2E8F0",
    "TEXT_FAINT": "#64748B",
    "SUCCESS": "#4ADE80",
    "SUCCESS_DARK": "#22C55E",
    "SUCCESS_ALT": "#34D399",
    "SUCCESS_DARKER": "#86EFAC",
    "SUCCESS_BG": "#0F2E1A",
    "DANGER": "#F87171",
    "DANGER_DARK": "#EF4444",
    "DANGER_DARKER": "#FCA5A5",
    "DANGER_BG": "#3A1214",
    "DANGER_BORDER": "#7F1D1D",
    "WARNING": "#FBBF24",
    "WARNING_DARK": "#F59E0B",
    "WARNING_DARKER": "#FDE68A",
    "WARNING_BG": "#3A2A0A",
    "WARNING_BG_ALT": "#3A230A",
    "INFO": "#38BDF8",
    "INFO_DARK": "#7DD3FC",
    "INFO_BG": "#0C2A3D",
    "PURPLE": "#A78BFA",
    "PURPLE_LIGHT": "#C4B5FD",
    "PURPLE_BG": "#241A3A",
}

assert set(_DARK) == set(_LIGHT), "dark/light token tables drifted out of sync"


class _ColorsMeta(type):
    def __getattr__(cls, name: str):
        table = _DARK if _state["mode"] == "dark" else _LIGHT
        try:
            return table[name]
        except KeyError:
            raise AttributeError(name) from None


class Colors(metaclass=_ColorsMeta):
    """Mode-aware color tokens — every ``Colors.X`` access resolves fresh."""


class Spacing:
    """Common spacing scale (px) used for padding/margins/gaps."""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


class Radius:
    """Corner-radius scale (px). HF leans slightly rounder than default
    Material for the "modern workshop tool" feel."""

    SM = 12
    MD = 16
    LG = 20
    XL = 24


class IconSize:
    """Icon-only button sizes, keyed by the *role* the icon plays — not by
    screen, so the same kind of action reads identically everywhere it
    appears (inline row actions vs. header actions vs. one hero action)."""

    INLINE = 18
    HEADER = 20
    HERO = 34


_SHADOW_RECIPES: dict[str, tuple[int, int, tuple[int, int], str]] = {
    "SM": (10, 0, (0, 2), "BORDER"),
    "SOFT": (14, 0, (0, 3), "BORDER"),
    "MD": (18, 0, (0, 5), "BORDER"),
    "LG": (26, 0, (0, 9), "BORDER_STRONG"),
}


class _ShadowMeta(type):
    def __getattr__(cls, name: str):
        try:
            blur, spread, (dx, dy), border_token = _SHADOW_RECIPES[name]
        except KeyError:
            raise AttributeError(name) from None
        return ft.BoxShadow(
            blur_radius=blur,
            spread_radius=spread,
            color=getattr(Colors, border_token),
            offset=ft.Offset(dx, dy),
        )


class Shadow(metaclass=_ShadowMeta):
    """Mode-aware elevation tokens — same pattern as ``Colors``."""


class _SeverityStyles:
    """Lazily-resolved (color, bg, icon) triples for alerts, keyed by
    severity ("info" | "warning" | "urgent"). Keeps every screen that
    renders an alert recoloring identically."""

    _RECIPES = {
        "urgent": ("DANGER", "DANGER_BG", ft.Icons.PRIORITY_HIGH_ROUNDED),
        "warning": ("WARNING_DARK", "WARNING_BG", ft.Icons.WARNING_AMBER_ROUNDED),
        "info": ("PRIMARY", "PRIMARY_BG", ft.Icons.INFO_OUTLINE_ROUNDED),
    }

    def __getitem__(self, key: str):
        color_token, bg_token, icon = self._RECIPES[key]
        return (getattr(Colors, color_token), getattr(Colors, bg_token), icon)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


class _StatusStyles:
    """Lazily-resolved (icon, fg, bg, border) triples for small status pills
    used across the app (device state, test results, report state)."""

    _RECIPES = {
        "info": (ft.Icons.INFO_OUTLINE_ROUNDED, "TEXT_SECONDARY", "BACKGROUND_ALT", "BORDER"),
        "success": (ft.Icons.CHECK_CIRCLE_ROUNDED, "SUCCESS_DARKER", "SUCCESS_BG", "SUCCESS"),
        "error": (ft.Icons.ERROR_ROUNDED, "DANGER_DARKER", "DANGER_BG", "DANGER_BORDER"),
    }

    def __getitem__(self, key: str):
        icon, color_token, bg_token, border_token = self._RECIPES[key]
        return (icon, getattr(Colors, color_token), getattr(Colors, bg_token), getattr(Colors, border_token))

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


SEVERITY_STYLE = _SeverityStyles()
STATUS_STYLES = _StatusStyles()


class LazyPalette:
    """A ``list``-like sequence of ``Colors`` tokens resolved on access —
    for views that cycle through accent colors by index. A plain list would
    bake in the light-mode hex the moment the module imports."""

    def __init__(self, *tokens: str):
        self._tokens = tokens

    def __len__(self) -> int:
        return len(self._tokens)

    def __getitem__(self, index: int) -> str:
        return getattr(Colors, self._tokens[index])

    def __iter__(self):
        return (getattr(Colors, t) for t in self._tokens)


__all__ = [
    "Colors", "Spacing", "Radius", "IconSize", "Shadow", "SEVERITY_STYLE", "STATUS_STYLES", "LazyPalette",
    "get_mode", "set_mode", "is_dark",
]
