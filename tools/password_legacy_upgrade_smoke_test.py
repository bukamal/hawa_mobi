# -*- coding: utf-8 -*-
"""Legacy PBKDF2 users must log in and be upgraded transparently."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile


def main() -> int:
    os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_password_upgrade_")
    from auth.password import CURRENT_ITERATIONS, verify_password
    from database.connection import DatabaseConnection, get_local_db_path
    from database.migrations import init_database
    from database.repositories.user_repo import UserRepository

    init_database()
    salt = "legacy-user-salt"
    legacy = hashlib.pbkdf2_hmac(
        "sha256", b"Legacy!Pass9", salt.encode(), 100_000
    ).hex()
    conn = sqlite3.connect(get_local_db_path())
    try:
        conn.execute(
            "INSERT INTO users(username,password_hash,salt,full_name,role,created_at,force_password_change) "
            "VALUES(?,?,?,?,?,?,0)",
            ("legacy_user", legacy, salt, "مستخدم قديم", "user", "2023-01-01"),
        )
        conn.commit()
    finally:
        conn.close()
    DatabaseConnection.reset_after_restore()

    repo = UserRepository()
    user = repo.authenticate("legacy_user", "Legacy!Pass9")
    assert user is not None
    upgraded = repo.get_by_username("legacy_user")
    assert upgraded is not None
    assert upgraded["password_hash"].startswith(f"pbkdf2_sha256${CURRENT_ITERATIONS}$")
    assert upgraded["password_hash"] != legacy
    assert verify_password("Legacy!Pass9", upgraded["password_hash"], upgraded["salt"])
    assert repo.authenticate("legacy_user", "wrong-password") is None
    print("✅ password_legacy_upgrade_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
