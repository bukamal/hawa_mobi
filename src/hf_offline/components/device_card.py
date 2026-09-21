"""Device card — the main row in the devices list.

One card shape for every device listing (workshop board, history, quick
actions): leading status badge, brand/model title, customer + serial
metadata, IMEI as a mono identifier, status pill and quick actions.
"""

from __future__ import annotations

from typing import Callable, Mapping

import flet as ft

from hf_offline.components import buttons
from hf_offline.components.status_pill import device_status_pill
from hf_offline.core.theme import Colors, Shadow
from hf_offline.core.typography import Type, mono_value, type_text


def device_card(
    device: Mapping,
    *,
    on_tap: Callable[[ft.ControlEvent], None] | None = None,
    on_diagnose: Callable[[ft.ControlEvent], None] | None = None,
    on_edit: Callable[[ft.ControlEvent], None] | None = None,
    on_delete: Callable[[ft.ControlEvent], None] | None = None,
) -> ft.Container:
    """Build a device row card from a devices-table row.

    ``device`` is a ``sqlite3.Row``-like mapping with at least: id, brand,
    model, serial, imei, customer_name, customer_phone, status, updated_at.
    """
    brand = str(device.get("brand") or "").strip() or "علامة غير محددة"
    model = str(device.get("model") or "").strip()
    title = f"{brand} {model}".strip() or "جهاز"

    customer = str(device.get("customer_name") or "").strip()
    phone = str(device.get("customer_phone") or "").strip()
    customer_line = " · ".join(p for p in (customer, phone) if p)

    serial = str(device.get("serial") or "").strip()
    imei = str(device.get("imei") or "").strip()
    meta_bits: list[ft.Control] = []
    if serial:
        meta_bits.append(ft.Row([type_text("S/N", Type.CAPTION), mono_value(serial)], spacing=6))
    if imei:
        meta_bits.append(ft.Row([type_text("IMEI", Type.CAPTION), mono_value(imei)], spacing=6))

    actions = ft.Row(
        [
            *([buttons.inline_icon_button(ft.Icons.MONITOR_WEIGHT_OUTLINED, lambda _: on_diagnose(ft.ControlEvent()), tooltip="بدء التشخيص")] if on_diagnose else []),
            *([buttons.inline_icon_button(ft.Icons.EDIT_OUTLINED, lambda _: on_edit(ft.ControlEvent()), tooltip="تعديل")] if on_edit else []),
            *([buttons.inline_icon_button(ft.Icons.DEL_OUTLINE, lambda _: on_delete(ft.ControlEvent()), tooltip="حذف", color=Colors.DANGER)] if on_delete else []),
        ],
        spacing=2,
    )

    status = str(device.get("status") or "in_queue")
    leading = ft.Container(
        ft.Icon(
            {
                "in_queue": ft.Icons.HOURLGLASS_BOTTOM_ROUNDED,
                "in_repair": ft.Icons.BUILD_OUTLINED,
                "diagnosing": ft.Icons.INSPECT_OUTLINED,
                "done": ft.Icons.FLAG_ROUNDED,
            }.get(status, ft.Icons.PHONE_ANDROID_ROUNDED),
            color={
                "in_queue": Colors.INFO_DARK,
                "in_repair": Colors.WARNING_DARKER,
                "diagnosing": Colors.PRIMARY,
                "done": Colors.SUCCESS_DARKER,
            }.get(status, Colors.TEXT_SECONDARY),
            size=20,
        ),
        width=44, height=44, alignment=ft.alignment.center,
        bgcolor=Colors.BACKGROUND, border_radius=14,
    )

    return ft.Container(
        ft.Row(
            [
                leading,
                ft.Column(
                    [
                        ft.Row([ft.Text(title, size=13.5, weight=ft.FontWeight.W_700, color=Colors.TEXT_PRIMARY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), device_status_pill(status)], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, expand=True),
                        *([type_text(customer_line, Type.CAPTION)] if customer_line else []),
                        *([ft.Column(meta_bits, spacing=3)] if meta_bits else []),
                    ],
                    spacing=4, expand=True,
                ),
                actions,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        bgcolor=Colors.WHITE,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=16,
        shadow=Shadow.SM,
        ink=bool(on_tap),
        on_click=on_tap,
    )


__all__ = ["device_card"]
