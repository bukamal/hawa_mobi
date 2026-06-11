# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Optional, Dict


class UserSession:
    """In-memory session state.

    The APK client deliberately keeps sessions in memory only.  This avoids
    leaving reusable credentials on the device and gives a predictable boot
    flow: Splash can restore only a still-valid in-memory session after a soft
    view rebuild, otherwise it returns to Login.
    """

    _current_user: Optional[Dict] = None
    _login_at: float = 0.0
    _ttl_seconds: int = 8 * 60 * 60

    @classmethod
    def login(cls, user: Dict, ttl_seconds: int | None = None):
        cls._current_user = dict(user or {})
        cls._login_at = time.time()
        if ttl_seconds is not None:
            cls._ttl_seconds = int(ttl_seconds)

    @classmethod
    def logout(cls):
        cls._current_user = None
        cls._login_at = 0.0

    @classmethod
    def get_current(cls) -> Optional[Dict]:
        if not cls.is_authenticated():
            return None
        return cls._current_user

    @classmethod
    def is_expired(cls) -> bool:
        if not cls._current_user:
            return True
        return (time.time() - cls._login_at) > cls._ttl_seconds

    @classmethod
    def is_authenticated(cls) -> bool:
        if cls._current_user is None:
            return False
        if cls.is_expired():
            cls.logout()
            return False
        return True

    @classmethod
    def is_admin(cls) -> bool:
        user = cls.get_current()
        return bool(user and user.get('role') == 'admin')

    @classmethod
    def force_password_change(cls) -> bool:
        user = cls.get_current()
        return bool(user and user.get('force_password_change', 0) == 1)

    @classmethod
    def snapshot(cls) -> Dict:
        user = cls.get_current()
        return {
            'authenticated': user is not None,
            'username': (user or {}).get('username', ''),
            'role': (user or {}).get('role', ''),
            'expires_in_seconds': max(0, int(cls._ttl_seconds - (time.time() - cls._login_at))) if user else 0,
        }
