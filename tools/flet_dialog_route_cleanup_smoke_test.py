# -*- coding: utf-8 -*-
"""Verify nested custom dialogs and global cleanup leave no overlay surface."""
import flet as ft
from views.flet_compat import open_control, close_control, close_all_dialogs

class FakePage:
    def __init__(self):
        self.overlay = []
        self.dialog = None
        self.width = 412
        self.height = 915
    def update(self):
        pass

page = FakePage()
first = ft.AlertDialog(title="الأول", content=ft.Text("1"))
second = ft.AlertDialog(title="الثاني", content=ft.Text("2"))
open_control(page, first)
open_control(page, second)
assert len(page.overlay) == 2
assert page.dialog is second
close_control(page, second)
assert len(page.overlay) == 1
assert page.dialog is first
close_all_dialogs(page)
assert page.overlay == []
assert page.dialog is None
assert first.open is False
print("flet_dialog_route_cleanup_smoke_test passed")
