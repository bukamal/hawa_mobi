# Phase 74 — Mandatory password change flow fix

- Forced password change is now a full-screen navigation view, not an AlertDialog.
- Login no longer remains stuck on “جاري التحقق...” after successful authentication that requires password change.
- Cancel logs the user out and returns to the login screen; it cannot bypass into the app.
- Successful password change clears the active session force flag and continues to the main app.
- Added `tools/mandatory_password_change_flow_smoke_test.py` and wired it into quality gate.
