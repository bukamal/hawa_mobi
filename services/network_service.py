# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from database.connection import DatabaseConnection, set_setting, _set_local_setting_direct


@dataclass(frozen=True)
class NetworkCheckResult:
    ok: bool
    message: str
    server_url: str = ""


class NetworkService:
    """Network-mode validation and health checks.

    This keeps settings screens from knowing REST endpoint details or Android
    safety rules such as rejecting localhost in client mode.
    """

    @staticmethod
    def normalize_server_url(raw_url: str) -> str:
        url = (raw_url or "").strip().rstrip("/")
        if not url:
            raise ValueError("عنوان الخادم مطلوب")
        if "://" not in url:
            url = "http://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("صيغة عنوان الخادم غير صحيحة")
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            raise ValueError("في وضع العميل استخدم IP جهاز الخادم، وليس localhost")
        return url

    @staticmethod
    def save_mode(mode: str, server_url: str = "") -> None:
        if mode not in {"local", "client"}:
            raise ValueError("الوضع المسموح: محلي أو عميل شبكة فقط")

        # Network mode is a bootstrap/local setting, not a remote setting.
        # Changing local -> client invalidates the current local session; keeping
        # the user inside the app produces protected API calls without a token.
        old_mode = DatabaseConnection().mode
        set_setting("network/mode", mode)
        if mode == "client":
            set_setting("network/server_url", NetworkService.normalize_server_url(server_url))
            _set_local_setting_direct('auth/network_token', '')
            try:
                from auth.session import UserSession
                UserSession.logout()
            except Exception:
                pass
        elif old_mode == "client":
            _set_local_setting_direct('auth/network_token', '')
            try:
                from auth.session import UserSession
                UserSession.logout()
            except Exception:
                pass
        DatabaseConnection().refresh_mode()

    @staticmethod
    def check_connection(server_url: str | None = None) -> NetworkCheckResult:
        db = DatabaseConnection()
        url = NetworkService.normalize_server_url(server_url or db.server_url)
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
            currency_contract = str(caps.get("currency_contract") or health.get("currency_contract") or "")
            if caps and not caps.get("supports_historic_currency_snapshot", False):
                return NetworkCheckResult(
                    False,
                    "الخادم يعمل لكنه لا يعلن دعم السعر التاريخي للعملات. حدّث خادم هوى الشام قبل ربط APK.",
                    url,
                )
            if currency_contract and currency_contract != "historic-currency-snapshot-v1":
                return NetworkCheckResult(
                    False,
                    f"عقد العملات في الخادم غير متوافق: {currency_contract}",
                    url,
                )
            version = caps.get("api_contract_version") or health.get("api_contract_version") or "legacy"
            return NetworkCheckResult(True, f"الاتصال بالخادم ناجح — عقد API: {version}", url)
        except Exception as exc:
            return NetworkCheckResult(False, f"فشل الاتصال بالخادم: {exc}", url)
