"""HF typography system — an upgrade over ad-hoc per-view font sizes.

Design goals:

* **One semantic scale.** Every text in the app picks a *role*
  (``display``/``title``/``subtitle``/``body``/``caption``/``mono``) instead
  of hand-picking a pixel size, so a visual pass is a one-file edit.
* **Arabic-first.** ``letter_spacing`` is pinned to 0 for Arabic runs
  (positive tracking visibly breaks Arabic character joins) and ``height``
  (line-height) is part of the token, not an afterthought.
* **Tabular numerals for identifiers.** The ``mono`` role is used for IMEI /
  serial / CID codes — a fixed-width, LTR-safe style so long digit strings
  never reflow under RTL reordering.
* **Auto custom-font.** Like the reference app, a TTF dropped into
  ``src/assets/fonts/`` (see that folder's README) activates automatically;
  until then the system font stack is used. Zero-risk self-activation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from hf_offline.core.theme import Colors, Spacing

# ---------------------------------------------------------------------------
# Custom font discovery (self-activating, zero-config when files are absent)
# ---------------------------------------------------------------------------
_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
_CUSTOM_FONTS = {
    "Plex": "fonts/IBMPlexSansArabic-Regular.ttf",
    "Plex SemiBold": "fonts/IBMPlexSansArabic-SemiBold.ttf",
}
APP_FONTS: dict[str, str] = {
    name: rel
    for name, rel in _CUSTOM_FONTS.items()
    if (_FONTS_DIR / Path(rel).name).exists()
}
APP_FONT_FAMILY: str | None = "Plex" if "Plex" in APP_FONTS else None


class Type:
    """Semantic type scale.

    ``size``/``weight`` are the visible pair; ``height`` is the line-height
    multiplier that keeps Arabic diacritics from clipping and rows breathing;
    ``color`` defaults to a neutral token so most call sites stay one line.
    """

    DISPLAY = "display"   # big numbers / hero headings (KPI values, splash)
    H1 = "h1"             # screen header (inside the shell's top bar)
    H2 = "h2"             # section headings inside cards
    H3 = "h3"             # sub-section headings / card titles
    BODY = "body"         # default reading text, form labels, list titles
    BODY_SM = "body_sm"   # dense list titles, table rows
    CAPTION = "caption"   # helper text, timestamps, secondary metadata
    MONO = "mono"         # identifiers: IMEI, serial, CID, build numbers

    _SPEC: dict[str, dict[str, Any]] = {
        "display": dict(size=26, weight=ft.FontWeight.BOLD, height=1.25, color="TEXT_PRIMARY"),
        "h1": dict(size=20, weight=ft.FontWeight.BOLD, height=1.3, color="TEXT_PRIMARY"),
        "h2": dict(size=15, weight=ft.FontWeight.W_700, height=1.35, color="TEXT_PRIMARY"),
        "h3": dict(size=13, weight=ft.FontWeight.W_600, height=1.35, color="TEXT_MUTED_DARK"),
        "body": dict(size=13, weight=ft.FontWeight.W_500, height=1.45, color="TEXT_PRIMARY"),
        "body_sm": dict(size=12, weight=ft.FontWeight.W_500, height=1.4, color="TEXT_MUTED"),
        "caption": dict(size=11, weight=ft.FontWeight.W_500, height=1.35, color="TEXT_SECONDARY"),
        "mono": dict(size=12, weight=ft.FontWeight.W_600, height=1.4, color="TEXT_MUTED_DARK"),
    }


def spec(role: str) -> dict[str, Any]:
    """The raw spec for a role — raises for unknown roles (fail fast in dev)."""
    try:
        return dict(Type._SPEC[role])
    except KeyError:
        raise KeyError(f"unknown type role: {role!r} — use one of {sorted(Type._SPEC)}") from None


def resolve_font_family(role: str, family: str | None = None) -> str | None:
    """The font family for a role: caller override > mono role > custom font.

    ``mono`` pins a monospace family so identifier columns stay aligned in
    light and dark modes alike; the Arabic custom font is preferred for all
    other roles when present.
    """
    if family:
        return family
    if role == Type.MONO:
        return "monospace"
    return APP_FONT_FAMILY


def type_text(
    value: str,
    role: str = Type.BODY,
    *,
    color: str | None = None,
    size: float | None = None,
    weight: Any = None,
    family: str | None = None,
    **kwargs,
) -> ft.Text:
    """Build a ``ft.Text`` from the semantic scale.

    Any explicit ``color``/``size``/``weight`` overrides the role defaults;
    everything else (line-height, letter-spacing, direction, font) is owned
    by the scale so call sites cannot drift.
    """
    s = spec(role)
    text_color = color if color is not None else getattr(Colors, s["color"])
    return ft.Text(
        value,
        size=size or s["size"],
        weight=weight or s["weight"],
        color=text_color,
        height=s.get("height"),
        letter_spacing=0,
        font_family=resolve_font_family(role, family),
        **kwargs,
    )


def mono_value(value: str | int | None, *, color: str | None = None, size: float | None = None) -> ft.Text:
    """Identifier display (IMEI/serial/CID): LTR, tabular-looking, safe under
    RTL reordering — the single place identifier strings get their style."""
    text = str(value or "—")
    return ft.Text(
        text,
        size=size or spec(Type.MONO)["size"],
        weight=ft.FontWeight.W_600,
        color=color or Colors.TEXT_MUTED_DARK,
        height=spec(Type.MONO).get("height"),
        letter_spacing=0.5,
        font_family="monospace",
        direction=ft.TextDirection.LTR,
    )


def section_title(title: str, *, subtitle: str | None = None) -> ft.Column:
    """Standard in-card heading block (H2 + optional caption)."""
    controls: list[ft.Control] = [type_text(title, Type.H2)]
    if subtitle:
        controls.append(type_text(subtitle, Type.CAPTION))
    return ft.Column(controls, spacing=Spacing.XS)


__all__ = [
    "Type", "spec", "resolve_font_family", "type_text", "mono_value", "section_title",
    "APP_FONTS", "APP_FONT_FAMILY",
]
