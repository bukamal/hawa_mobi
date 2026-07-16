# -*- coding: utf-8 -*-
"""Encrypted, app-private storage for optional remembered login credentials.

The current Android application is pinned to Flet 0.28.3, which predates the
native ``flet-secure-storage`` service.  This module therefore keeps the secret
inside the application's private data directory and encrypts the credential
payload with Fernet (AES128-CBC + HMAC-SHA256).  The encryption key and vault
are created with restrictive filesystem permissions and the Android package
also disables OS backup of app data.

This protects credentials from accidental disclosure in SQLite/settings,
exports, logs, and ordinary file browsing.  It is not a substitute for Android
Keystore on a rooted/fully-compromised device; a future Flet upgrade can replace
this backend with the native secure-storage extension without changing the
LoginView contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet, InvalidToken

from database.connection import get_data_dir


_VAULT_VERSION = 1
_SECURE_DIR_NAME = "secure"
_KEY_FILE_NAME = "login_credentials.key"
_VAULT_FILE_NAME = "login_credentials.vault"


class CredentialStoreError(RuntimeError):
    """Raised when credentials cannot be persisted securely."""


@dataclass(frozen=True)
class SavedCredentials:
    username: str
    password: str
    scope: str
    saved_at: int


def credential_scope(mode: str, server_url: str = "") -> str:
    """Return a stable scope so local/server credentials never cross-fill."""
    if (mode or "local").strip().lower() != "client":
        return "local"

    raw = (server_url or "").strip().rstrip("/")
    if not raw:
        return "client:unconfigured"
    try:
        parsed = urlparse(raw if "://" in raw else "http://" + raw)
        host = (parsed.hostname or "").lower()
        scheme = (parsed.scheme or "http").lower()
        port = f":{parsed.port}" if parsed.port else ""
        path = (parsed.path or "").rstrip("/")
        normalized = urlunparse((scheme, host + port, path, "", "", ""))
    except Exception:
        normalized = raw.lower()
    return f"client:{normalized}"


class CredentialStore:
    def __init__(self, data_dir: str | os.PathLike[str] | None = None):
        root = Path(data_dir or get_data_dir())
        self.secure_dir = root / _SECURE_DIR_NAME
        self.key_path = self.secure_dir / _KEY_FILE_NAME
        self.vault_path = self.secure_dir / _VAULT_FILE_NAME

    def _ensure_secure_dir(self) -> None:
        self.secure_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.secure_dir, 0o700)
        except OSError:
            pass

    @staticmethod
    def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            try:
                os.fchmod(fd, mode)
            except OSError:
                pass
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            try:
                os.chmod(path, mode)
            except OSError:
                pass
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _load_or_create_key(self) -> bytes:
        self._ensure_secure_dir()
        if self.key_path.exists():
            key = self.key_path.read_bytes().strip()
            try:
                Fernet(key)
            except Exception as exc:
                raise CredentialStoreError("ملف تشفير بيانات الدخول غير صالح") from exc
            return key

        key = Fernet.generate_key()
        try:
            # O_EXCL prevents two concurrent first-start callbacks from replacing
            # each other's key and making the newly written vault unreadable.
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return self._load_or_create_key()
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                self.key_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return key

    def save(self, username: str, password: str, scope: str) -> None:
        username = (username or "").strip()
        password = password or ""
        scope = (scope or "").strip()
        if not username or not password or not scope:
            raise CredentialStoreError("بيانات الدخول المطلوب حفظها غير مكتملة")

        payload = {
            "version": _VAULT_VERSION,
            "username": username,
            "password": password,
            "scope": scope,
            "saved_at": int(time.time()),
        }
        try:
            token = Fernet(self._load_or_create_key()).encrypt(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            self._atomic_write(self.vault_path, token, 0o600)
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("تعذر حفظ بيانات الدخول المشفرة") from exc

    def load(self, scope: str) -> Optional[SavedCredentials]:
        scope = (scope or "").strip()
        if not scope or not self.vault_path.exists() or not self.key_path.exists():
            return None
        try:
            plaintext = Fernet(self._load_or_create_key()).decrypt(self.vault_path.read_bytes())
            data = json.loads(plaintext.decode("utf-8"))
            if int(data.get("version", 0)) != _VAULT_VERSION:
                return None
            if str(data.get("scope") or "") != scope:
                return None
            username = str(data.get("username") or "").strip()
            password = str(data.get("password") or "")
            if not username or not password:
                return None
            return SavedCredentials(
                username=username,
                password=password,
                scope=scope,
                saved_at=int(data.get("saved_at") or 0),
            )
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
            # A corrupt/tampered vault must never crash Login. Delete only the
            # unreadable ciphertext; keeping the valid key is harmless.
            self.clear()
            return None
        except CredentialStoreError:
            return None
        except Exception:
            return None

    def clear(self) -> None:
        try:
            self.vault_path.unlink(missing_ok=True)
        except OSError:
            pass

    def has_saved_credentials(self) -> bool:
        return self.vault_path.exists() and self.key_path.exists()
