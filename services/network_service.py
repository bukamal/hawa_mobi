# -*- coding: utf-8 -*-
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from database.connection import (
    DatabaseConnection,
    _set_local_setting_direct,
    get_setting,
    set_setting,
)


@dataclass(frozen=True)
class NetworkCheckResult:
    ok: bool
    message: str
    server_url: str = ""


class NetworkService:
    """Validate network mode and transport security for the Android client."""

    @staticmethod
    def insecure_http_enabled() -> bool:
        env = str(os.environ.get("HAWAA_ALLOW_INSECURE_HTTP", "")).strip().lower()
        if env in {"1", "true", "yes", "on"}:
            return True
        saved = (
            str(get_setting("network/allow_insecure_http", "false") or "false")
            .strip()
            .lower()
        )
        return saved in {"1", "true", "yes", "on"}

    @staticmethod
    def _is_private_or_loopback(host: str) -> bool:
        normalized = (host or "").strip().lower()
        if normalized in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            address = ipaddress.ip_address(normalized)
            return bool(
                address.is_private or address.is_loopback or address.is_link_local
            )
        except ValueError:
            return False

    @staticmethod
    def normalize_server_url(
        raw_url: str, *, allow_insecure_http: bool | None = None
    ) -> str:
        url = (raw_url or "").strip().rstrip("/")
        if not url:
            raise ValueError("عنوان الخادم مطلوب")
        if "://" not in url:
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("صيغة عنوان الخادم غير صحيحة")
        if parsed.username or parsed.password:
            raise ValueError("لا تضع اسم مستخدم أو كلمة مرور داخل عنوان الخادم")
        host = (parsed.hostname or "").strip().lower()
        if host in {"0.0.0.0", "::"}:  # nosec B104 - address comparison/normalization, not socket binding
            host = "127.0.0.1"
        if not host:
            raise ValueError("اسم الخادم أو عنوان IP غير موجود")

        if parsed.scheme == "http":
            allowed = (
                NetworkService.insecure_http_enabled()
                if allow_insecure_http is None
                else bool(allow_insecure_http)
            )
            if not NetworkService._is_private_or_loopback(host):
                raise ValueError(
                    "HTTP غير المشفر مسموح فقط داخل شبكة محلية خاصة. استخدم HTTPS للخوادم العامة."
                )
            if not allowed:
                raise ValueError(
                    "الاتصال HTTP غير مشفر. فعّل خيار السماح المؤقت داخل الشبكة المحلية فقط، أو استخدم HTTPS."
                )

        netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        path = parsed.path.rstrip("/")
        if path.endswith("/api"):
            path = path[:-4].rstrip("/")
        return f"{parsed.scheme}://{netloc}{path}"

    @staticmethod
    def save_mode(
        mode: str, server_url: str = "", *, allow_insecure_http: bool | None = None
    ) -> None:
        if mode not in {"local", "client"}:
            raise ValueError("الوضع المسموح: محلي أو عميل شبكة فقط")
        old_mode = DatabaseConnection().mode
        allow_http = (
            NetworkService.insecure_http_enabled()
            if allow_insecure_http is None
            else bool(allow_insecure_http)
        )
        set_setting("network/allow_insecure_http", "true" if allow_http else "false")
        set_setting("network/mode", mode)
        if mode == "client":
            set_setting(
                "network/server_url",
                NetworkService.normalize_server_url(
                    server_url, allow_insecure_http=allow_http
                ),
            )
            _set_local_setting_direct("auth/network_token", "")
            try:
                from auth.session import UserSession

                UserSession.logout()
            except Exception:
                pass
        elif old_mode == "client":
            _set_local_setting_direct("auth/network_token", "")
            try:
                from auth.session import UserSession

                UserSession.logout()
            except Exception:
                pass
        DatabaseConnection().refresh_mode()

    @staticmethod
    def check_connection(
        server_url: str | None = None,
        *,
        allow_insecure_http: bool | None = None,
    ) -> NetworkCheckResult:
        db = DatabaseConnection()
        url = NetworkService.normalize_server_url(
            server_url or db.server_url,
            allow_insecure_http=allow_insecure_http,
        )
        from database.connection_rest import RestClient

        client = RestClient(url)
        try:
            health = client.health()
            if not (isinstance(health, dict) and health.get("ok")):
                return NetworkCheckResult(False, "استجابة الخادم غير متوقعة", url)
            try:
                caps = client.capabilities()
            except Exception:
                caps = {}
            currency_contract = str(
                caps.get("currency_contract") or health.get("currency_contract") or ""
            )
            if caps and not caps.get("supports_historic_currency_snapshot", False):
                return NetworkCheckResult(
                    False,
                    "الخادم يعمل لكنه لا يعلن دعم السعر التاريخي للعملات. حدّث خادم هوى الشام قبل ربط APK.",
                    url,
                )
            if (
                currency_contract
                and currency_contract != "historic-currency-snapshot-v1"
            ):
                return NetworkCheckResult(
                    False, f"عقد العملات في الخادم غير متوافق: {currency_contract}", url
                )
            version = (
                caps.get("api_contract_version")
                or health.get("api_contract_version")
                or "legacy"
            )
            transport = "HTTP محلي غير مشفر" if url.startswith("http://") else "HTTPS"
            return NetworkCheckResult(
                True,
                f"الاتصال بالخادم ناجح — عقد API: {version} — النقل: {transport}",
                url,
            )
        except Exception as exc:
            from services.network_diagnostics_service import classify_connection_error

            hint = classify_connection_error(url, exc)
            return NetworkCheckResult(False, f"{hint.title}: {hint.message}", url)
