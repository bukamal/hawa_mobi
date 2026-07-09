# Phase 41 — Android Manual Pairing + Persistent Backup Fallback

## Summary

This phase improves Android usability when runtime Flet services are incomplete:

- Adds a short manual pairing code path so users are not forced to paste long QR JSON.
- Keeps the QR/paste workflow intact.
- Adds a persistent internal backup copy when creating backups, so Restore fallback can list backups even when Android FilePicker is unavailable.

## Android changes

- `database/connection_rest.py`
  - Added `RestClient.pair_mobile_code(pairing_code, server_url)`.

- `services/pairing_service.py`
  - Added `MobilePairingService.pair_with_code(server_url, pairing_code)`.
  - Refactored capabilities checks into a common helper used by QR and manual code pairing.

- `views/dialogs/qr_pairing_dialog.py`
  - Added manual pairing fields:
    - server URL
    - short pairing code
  - Added “ربط بالرمز اليدوي”.
  - Kept camera/paste QR fallback.

- `services/file_export_service.py`
  - Backup creation now also stores a persistent internal copy under app storage `backups/`.
  - This gives the Restore fallback dialog usable backups even if Android/FilePicker is not available.

- `tools/manual_pairing_code_smoke_test.py`
  - New smoke test for short-code pairing.

## QA

Run:

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/quality_gate.py
```

Expected:

```text
quality_gate passed
```

## Manual test

1. On Windows, generate a mobile pairing code.
2. On Android, open Settings > Network > Pair via QR.
3. Enter the server URL and short code manually.
4. Tap “ربط بالرمز اليدوي”.
5. Confirm Android switches to client mode and asks for login.
6. In local Android mode, create a backup.
7. Tap import backup. If FilePicker is unavailable, use the fallback list of backups created by the app.
