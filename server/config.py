# -*- coding: utf-8 -*-
"""Runtime configuration for the standalone Hawaa server.

The Android/APK client must not import this module. It is used only by
server/run_server.py and server/flask_server.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Invalid integer environment variable {name}={raw!r}"
        ) from exc


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    threads: int
    token_ttl_minutes: int
    expose_database_path: bool


def load_server_config() -> ServerConfig:
    return ServerConfig(
        host=os.environ.get("HAWAA_SERVER_HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=_int_env("HAWAA_SERVER_PORT", 8000),
        threads=max(1, _int_env("HAWAA_SERVER_THREADS", 4)),
        token_ttl_minutes=max(5, _int_env("HAWAA_TOKEN_TTL_MINUTES", 12 * 60)),
        expose_database_path=_bool_env("HAWAA_EXPOSE_DATABASE_PATH", False),
    )
