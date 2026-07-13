# -*- coding: utf-8 -*-
"""Tokens from legacy APKs are scrubbed; only the active memory session is used."""

from __future__ import annotations

import os
import sqlite3
import tempfile

os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_auth_token_")

from auth.session import UserSession
from database.connection import (
    DatabaseConnection,
    _set_local_setting_direct,
    get_local_db_path,
)
from database.connection_rest import RestClient
from database.migrations import ensure_db

ensure_db()
_set_local_setting_direct("auth/network_token", "persisted-token")
client = RestClient("https://server.example")
assert "Authorization" not in client._headers(), client._headers()

UserSession.login(
    {"id": 1, "username": "admin", "role": "admin", "_auth_token": "session-token"}
)
client2 = RestClient("https://server.example")
assert client2._headers().get("Authorization") == "Bearer session-token"

conn = sqlite3.connect(get_local_db_path())
try:
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM settings WHERE key='auth/network_token' AND value<>''"
        ).fetchone()[0]
        == 0
    )
finally:
    conn.close()

_set_local_setting_direct("network/mode", "client")
_set_local_setting_direct("network/server_url", "https://server.example")
db = DatabaseConnection()
db.refresh_mode()
assert db.get_rest_client()._headers().get("Authorization") == "Bearer session-token"

UserSession.logout()
assert "Authorization" not in RestClient("https://server.example")._headers()
print("✅ auth_persistent_token_smoke_test passed")
