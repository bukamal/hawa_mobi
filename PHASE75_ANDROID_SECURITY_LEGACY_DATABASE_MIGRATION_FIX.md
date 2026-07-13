# Phase 75 — Android security hardening and legacy database migration

Release: 1.1.0  
Date: 2026-07-13

## Scope

This release modifies the Android/Flet project only. The Windows project in the original combined archive was not changed.

## Main corrections

- Added lossless migration for legacy Hawaa SQLite databases to schema version 23.
- Accepts a direct `.db`, `.sqlite`, `.sqlite3`, a normal ZIP, or a nested ZIP containing the database.
- Validates SQLite integrity and required accounting columns before touching the active database.
- Migrates a temporary copy first; the active database is replaced only after successful migration.
- Creates an automatic safety backup before every restore.
- Rolls back both the database and `config.json` if any post-replace verification fails.
- Ignores malformed optional `config.json` files while still recovering a valid accounting database.
- Preserves current device network address preferences, forces restored mode to local, and removes legacy bearer tokens.
- Keeps old PBKDF2-SHA256 100,000-iteration passwords valid and transparently upgrades them to the current versioned 600,000-iteration format after successful login.
- Fixed the restore-latest dialog callback that referenced `dlg` before assignment.
- Session bearer tokens are now memory-only and are removed from backup snapshots.
- HTTP is rejected by default; unencrypted HTTP requires explicit opt-in and is limited to private/loopback addresses.
- Removed broad Android storage/media permissions; retained only Internet and Camera permissions.
- Added an explicit warning that backup files contain accounting data and password hashes and must be stored securely.
- Added export table allow-listing to prevent dynamic SQL table injection.
- Normalized code formatting and resolved all Ruff findings.

## Verification

- 67/67 project tests passed in isolated data directories.
- Ruff: all checks passed.
- Bandit: 0 High, 0 Medium; remaining Low findings are defensive/fallback exception paths.
- `python -m compileall`: passed.
- `pip check`: passed.
- Python wheel and source distribution: built successfully.
- APK source preflight: passed.

## APK build limitation in this environment

The final APK binary could not be produced here because Flet attempted to download Flutter 3.29.2 and the execution environment had DNS/network resolution disabled. The failure occurred before Android compilation and is not an application-code failure. Build the APK on a machine with Flutter/Flet download access, then perform device tests on Android 11, 13, 14, and 15.

## Backup confidentiality

The backup is sanitized but not cryptographically encrypted. It excludes reusable network session tokens and server mode, but it still contains accounting records, user records, salts, and password hashes. Store it only in a trusted location and avoid sending it through untrusted channels.
