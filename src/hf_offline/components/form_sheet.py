"""Standard bottom sheet with a title bar + close button + scrollable body.

Every form/selector sheet in the app uses this so headers (title, close
button position, hairline) never drift between screens.
"""

from __future__ import annotations

from typing import Callable, Sequence

import flet as ft

from hf_offline.components.buttons import header_close_button
from hf_offline.core.theme import Colors, Radius
from hf_offline.core.typography import Type, type_text


def form_sheet(
    page: ft.Page,
    title: str,
    *,
    subtitle: str | None = None,
    body: ft.Control | Sequence[ft.Control] | None = None,
    actions: ft.Control | Sequence[ft.Control] | None = None,
    on_dismiss: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.BottomSheet:
    """Open a titled bottom sheet.

    Args:
        title: Sheet headline (H2 style).
        subtitle: Optional caption under the title.
        body: Scrollable middle content (single control or a list).
        actions: Sticky bottom action row (single control or list).
        on_dismiss: Called when the user closes via the X or taps outside.
    """
    body_controls = [body] if isinstance(body, ft.Control) else (list(body or []))
    action_controls = [actions] if isinstance(actions, ft.Control) else (list(actions or []))

    content: list[ft.Control] = [
        ft.Container(
            ft.Row(
                [
                    ft.Column(
                        [
                            type_text(title, Type.H2),
                            *([type_text(subtitle, Type.CAPTION)] if subtitle else []),
                        ],
                        spacing=2, expand=True,
                    ),
                    header_close_button(lambda _: close()),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=16, right=8, top=14, bottom=12),
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        )
    ]
    if body_controls:
        content.append(
            ft.Container(
                ft.Column(body_controls, spacing=12),
                scroll=ft.ScrollMode.AUTO,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                expand=True,
            )
        )
    if action_controls:
        content.append(
            ft.Container(
                ft.Row(action_controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=16, right=16, top=10, bottom=16),
                border=ft.border.only(top=ft.BorderSide(1, Colors.BORDER)),
            )
        )

    sheet = ft.BottomSheet(
        ft.Container(
            ft.Column(content, expand=True, spacing=0),
            bgcolor=Colors.WHITE,
            border_radius=ft.border_radius.only(top_left=Radius.XL, top_right=Radius.XL),
            expand=False,
        ),
        open=True,
        on_dismiss=on_dismiss,
    )

    def close() -> None:
        try:
            page.close(sheet)
        except Exception:
            pass

    page.open(sheet)
    return sheet


__all__ = ["form_sheet"]
