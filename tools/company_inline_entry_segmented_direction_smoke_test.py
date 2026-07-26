# -*- coding: utf-8 -*-
"""Acceptance checks for company-inline entry creation and direction UI."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dialog = (ROOT / "views" / "dialogs" / "add_edit_expense_dialog.py").read_text(encoding="utf-8")
company = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")

assert "self.type_selector = ft.SegmentedButton(" in dialog
assert 'value="incoming"' in dialog
assert 'value="outgoing"' in dialog
assert 'label=ft.Text("لنا")' in dialog
assert 'label=ft.Text("له")' in dialog
assert "لنا: مبلغ مستحق للشركة · له: مبلغ مستحق على الشركة" in dialog
assert "allow_empty_selection=False" in dialog
assert "allow_multiple_selection=False" in dialog
assert "def _selected_entry_type(self):" in dialog
assert 'if type_val not in {"incoming", "outgoing"}:' in dialog
assert "self.type_dropdown = ft.Dropdown(" not in dialog

assert 'ft.Text("إضافة قيد")' in company
assert "on_click=self._add_record" in company
assert "def _add_record(self, e=None):" in company
assert "company_name=self.company_name" in company
assert 'self._show_snackbar("ليس لديك صلاحية لإضافة قيود", True)' in company
assert "on_save=lambda _: self._reload()" in company
assert "disabled=is_disabled" in dialog

# Exercise the direction normalization without importing Flet. This verifies
# that create/update receives only stable internal values and that an invalid
# or missing UI selection cannot silently become an outgoing entry.
tree = ast.parse(dialog)
dialog_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AddEditExpenseDialog")
method_node = next(node for node in dialog_class.body if isinstance(node, ast.FunctionDef) and node.name == "_selected_entry_type")
namespace = {}
exec(compile(ast.Module(body=[method_node], type_ignores=[]), "<direction-method>", "exec"), namespace)
resolve_type = namespace["_selected_entry_type"]

class Selector:
    def __init__(self, selected):
        self.selected = selected

class DialogProbe:
    def __init__(self, selected):
        self.type_selector = Selector(selected)

assert resolve_type(DialogProbe({"incoming"})) == "incoming"
assert resolve_type(DialogProbe(["outgoing"])) == "outgoing"
assert resolve_type(DialogProbe("incoming")) == "incoming"
assert resolve_type(DialogProbe(set())) is None
assert resolve_type(DialogProbe({"unexpected"})) is None

compile(dialog, str(ROOT / "views" / "dialogs" / "add_edit_expense_dialog.py"), "exec")
compile(company, str(ROOT / "views" / "company_details_mobile_view.py"), "exec")
print("company_inline_entry_segmented_direction_smoke_test passed")
