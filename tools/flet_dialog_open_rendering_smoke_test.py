# -*- coding: utf-8 -*-
"""Runtime proof that the custom modal host opens and disappears completely."""
import flet as ft
from views.flet_compat import open_control, close_control

class FakePage:
    def __init__(self):
        self.overlay = []
        self.dialog = None
        self.width = 390
        self.height = 800
        self.updates = 0
    def update(self):
        self.updates += 1

page = FakePage()
dialog = ft.AlertDialog(
    modal=True,
    title=ft.Text("تأكيد"),
    content=ft.Text("محتوى"),
    actions=[ft.TextButton("إلغاء")],
)
open_control(page, dialog)
assert dialog.open is True
assert page.dialog is dialog
assert len(page.overlay) == 1
assert isinstance(page.overlay[0], ft.Stack)
assert page.overlay[0] is not dialog
close_control(page, dialog)
assert dialog.open is False
assert page.dialog is None
assert page.overlay == []
print("flet_dialog_open_rendering_smoke_test passed")
