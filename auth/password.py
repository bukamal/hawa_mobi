# -*- coding: utf-8 -*-
"""Password hashing with transparent support for legacy Hawaa databases."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Tuple

ALGORITHM = "pbkdf2_sha256"
CURRENT_ITERATIONS = 600_000
LEGACY_ITERATIONS = 100_000


def _derive(password: str, salt: str, iterations: int) -> str:
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()


def hash_password(
    password: str,
    salt: str | None = None,
    iterations: int = CURRENT_ITERATIONS,
) -> Tuple[str, str]:
    """Hash a password using the current versioned PBKDF2 format.

    Existing databases store the salt in a separate column, so this function
    keeps that schema and versions the algorithm/iteration count in the hash.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    iterations = max(LEGACY_ITERATIONS, int(iterations))
    digest = _derive(password, salt, iterations)
    return f"{ALGORITHM}${iterations}${digest}", salt


def _parse_hash(stored_hash: str) -> tuple[int, str]:
    value = str(stored_hash or "")
    parts = value.split("$", 2)
    if len(parts) == 3 and parts[0] == ALGORITHM:
        try:
            return int(parts[1]), parts[2]
        except (TypeError, ValueError):
            return 0, ""
    # Legacy Hawaa databases used a bare PBKDF2-SHA256 hex digest at 100k.
    return LEGACY_ITERATIONS, value


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    iterations, expected = _parse_hash(stored_hash)
    if iterations <= 0 or not expected or not salt:
        return False
    actual = _derive(password, str(salt), iterations)
    return hmac.compare_digest(actual, expected)


def password_needs_rehash(stored_hash: str) -> bool:
    iterations, digest = _parse_hash(stored_hash)
    return (
        not digest
        or iterations < CURRENT_ITERATIONS
        or not str(stored_hash or "").startswith(f"{ALGORITHM}$")
    )


def upgraded_hash(password: str, stored_hash: str, salt: str) -> tuple[str, str] | None:
    """Return a current hash after successful legacy verification, if needed."""
    if not verify_password(password, stored_hash, salt):
        return None
    if not password_needs_rehash(stored_hash):
        return None
    return hash_password(password)
