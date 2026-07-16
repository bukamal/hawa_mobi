# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile

from auth.credential_store import CredentialStore, credential_scope


with tempfile.TemporaryDirectory(prefix="hawaa_credentials_") as temp_dir:
    store = CredentialStore(temp_dir)
    local_scope = credential_scope("local")
    remote_scope = credential_scope("client", "HTTP://192.168.1.10:8000/")

    assert local_scope == "local"
    assert remote_scope == "client:http://192.168.1.10:8000"
    assert credential_scope("client", "192.168.1.10:8000") == remote_scope

    username = "admin@example"
    password = "P@ssw0rd-سري"
    store.save(username, password, local_scope)

    assert store.has_saved_credentials()
    saved = store.load(local_scope)
    assert saved is not None
    assert saved.username == username
    assert saved.password == password
    assert saved.scope == local_scope
    assert saved.saved_at > 0

    # Scope separation prevents a local password from being filled into a
    # Windows-server login and vice versa.
    assert store.load(remote_scope) is None

    key_bytes = store.key_path.read_bytes()
    vault_bytes = store.vault_path.read_bytes()
    assert username.encode("utf-8") not in key_bytes + vault_bytes
    assert password.encode("utf-8") not in key_bytes + vault_bytes
    assert b'"password"' not in vault_bytes

    if os.name == "posix":
        assert stat.S_IMODE(store.secure_dir.stat().st_mode) & 0o077 == 0
        assert stat.S_IMODE(store.key_path.stat().st_mode) & 0o077 == 0
        assert stat.S_IMODE(store.vault_path.stat().st_mode) & 0o077 == 0

    # Tampering must not crash Login and must invalidate only the ciphertext.
    store.vault_path.write_bytes(vault_bytes[:-1] + bytes([vault_bytes[-1] ^ 1]))
    assert store.load(local_scope) is None
    assert not store.vault_path.exists()
    assert store.key_path.exists()

    store.save(username, password, remote_scope)
    assert store.load(remote_scope).password == password
    store.clear()
    assert store.load(remote_scope) is None
    assert not store.has_saved_credentials()

print("✅ credential_store_smoke_test passed")
