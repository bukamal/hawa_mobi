# -*- coding: utf-8 -*-
"""Static checks for QR pairing UX: camera-first with paste fallback."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dialog = (ROOT / "views" / "dialogs" / "qr_pairing_dialog.py").read_text(encoding="utf-8")
    settings = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
    login = (ROOT / "views" / "login_view.py").read_text(encoding="utf-8")

    assert "android.permission.CAMERA" in pyproject, "QR camera scanning requires CAMERA permission"
    assert "مسح بالكاميرا" in dialog and "CAMERA_ALT" in dialog, "dialog must expose camera scan button"
    assert "لصق من الحافظة" in dialog and "CONTENT_PASTE" in dialog, "dialog must keep paste fallback"
    assert "BarcodeScanner" in dialog or "QRScanner" in dialog or "QrScanner" in dialog, "dialog must be camera-scanner ready"
    assert "open_qr_pairing_dialog" in settings and "views.dialogs.qr_pairing_dialog" in settings, "settings must use reusable QR dialog"
    assert "open_qr_pairing_dialog" in login and "views.dialogs.qr_pairing_dialog" in login, "login must use reusable QR dialog"
    print("✅ qr_pairing_ui_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
