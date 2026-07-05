# Phase 38 — Pairing UX + Local QA Fixes

## Android changes

- Improved `views/dialogs/qr_pairing_dialog.py` so pasted QR payloads are summarized in a small readable card instead of relying only on huge raw JSON.
- Added friendly diagnostics for failed QR pairing. The dialog now converts network errors such as `HTTPConnectionPool`, timeouts, and unreachable networks into user-facing Arabic messages via `services/network_diagnostics_service.py`.
- Reduced the raw QR text area height and size to avoid it dominating the dialog on phones.
- Updated `tools/qr_pairing_ui_smoke_test.py` to require payload summary and friendly diagnostics.

## Windows changes

- Allowed localhost/127.0.0.1/0.0.0.0 pairing generation for same-device or emulator QA.
- The Windows settings page still warns that real phones must use a LAN IP address such as `192.168.x.x`.
- QR generation no longer blocks localhost if the user explicitly selected it for testing.

## QA

Windows:

```bash
python3 scripts/check_project_readiness.py
python3 -m compileall -q .
PYTHONPATH=. pytest -q
```

Result: `61 passed`.

Android:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/quality_gate.py
```

Result: `quality_gate passed`.
