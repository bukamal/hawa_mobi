# -*- coding: utf-8 -*-
"""Runtime guard for searchable lookup fields inside Android dialogs.

The phase 91 lookup control overrides ``disabled``.  Flet's base Control may set
that property during ``Column.__init__`` before child controls are created.  If
our setter touches ``self.field`` too early, every dialog using the lookup field
fails during construction and Android appears to do nothing when the user taps
إضافة قيد / خدمة / سدد عني.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Control:
    def __init__(self, *args, **kwargs):
        # Simulate Flet assigning a base disabled property before subclasses
        # finish constructing their children.
        self.disabled = kwargs.get("disabled", False)
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.args = args

    def update(self):
        pass


class _Column(_Control):
    def __init__(self, controls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.controls = list(controls or [])


class _Row(_Column):
    pass


class _TextField(_Control):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = kwargs.get("value", "")
        self.label = kwargs.get("label", "")


class _Text(_Control):
    pass


class _Icon(_Control):
    pass


class _TextButton(_Control):
    pass


class _ButtonStyle(_Control):
    pass


class _Icons:
    SEARCH = "search"
    BUSINESS = "business"
    PERSON = "person"
    TRAVEL_EXPLORE = "travel_explore"


class _FontWeight:
    BOLD = "bold"


class _TextOverflow:
    ELLIPSIS = "ellipsis"


fake_flet = types.SimpleNamespace(
    Column=_Column,
    Row=_Row,
    TextField=_TextField,
    Text=_Text,
    Icon=_Icon,
    TextButton=_TextButton,
    ButtonStyle=_ButtonStyle,
    Icons=_Icons,
    FontWeight=_FontWeight,
    TextOverflow=_TextOverflow,
)

# Avoid importing the real views package/__init__.py; provide only ui_kit values
# needed by searchable_lookup_field.py.
sys.modules["flet"] = fake_flet
views_pkg = types.ModuleType("views")
views_pkg.__path__ = [str(ROOT / "views")]
sys.modules["views"] = views_pkg
ui_kit = types.ModuleType("views.ui_kit")
ui_kit.PRIMARY = "#0A3F70"
ui_kit.PRIMARY_SOFT = "#EAF4FF"
ui_kit.TEXT = "#172033"
ui_kit.MUTED = "#667085"
ui_kit.BORDER = "#D8E4EE"
sys.modules["views.ui_kit"] = ui_kit

spec = importlib.util.spec_from_file_location("lookup_under_test", ROOT / "views" / "searchable_lookup_field.py")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

field = module.SearchableLookupField(label="الشركة", value="أبو تيم", provider=lambda q, limit: [])
assert field.value == "أبو تيم"
field.disabled = True
assert field.disabled is True
assert field.field.disabled is True
field.disabled = False
assert field.disabled is False
assert field.field.disabled is False

src = (ROOT / "views" / "searchable_lookup_field.py").read_text(encoding="utf-8")
assert "self._disabled = bool(disabled)" in src
assert "getattr(self, \"field\", None)" in src
assert "super().__init__(controls=[]" in src

print("searchable_lookup_dialog_open_guard_smoke_test passed")
