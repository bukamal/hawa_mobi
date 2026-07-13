# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from database.connection_rest import RestClient
from services.network_service import NetworkService

PAIRING_CONTRACT_VERSION = "hawaa-mobile-pairing-v1"
CURRENCY_CONTRACT_VERSION = "historic-currency-snapshot-v1"


@dataclass(frozen=True)
class PairingResult:
    ok: bool
    message: str
    server_url: str = ""
    server_name: str = ""
    api_contract_version: str = ""
    currency_contract: str = ""


class MobilePairingService:
    """Parse and apply Windows-to-Android QR pairing payloads.

    Pairing only stores the server URL and proves that the phone saw a short
    lived QR token. It never logs the user in and never stores a password.
    """

    @staticmethod
    def parse_qr_text(qr_text: str) -> Dict[str, Any]:
        raw = (qr_text or "").strip()
        if not raw:
            raise ValueError("رمز QR فارغ")
        if raw.startswith("{"):
            data = json.loads(raw)
        else:
            parsed = urlparse(raw)
            if parsed.scheme not in {"hawaa", "hawaa-sham", "http", "https"}:
                raise ValueError("صيغة رمز الربط غير مدعومة")
            query = parse_qs(parsed.query)
            data = {k: v[-1] for k, v in query.items() if v}
            if not data.get("server_url") and parsed.scheme in {"http", "https"}:
                data["server_url"] = f"{parsed.scheme}://{parsed.netloc}"
        return data

    @staticmethod
    def _parse_expiry(value: str | None) -> datetime.datetime | None:
        if not value:
            return None
        try:
            normalized = str(value).replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            return None

    @staticmethod
    def validate_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        if str(data.get("app") or "") != "hawaa-sham":
            raise ValueError("هذا الرمز لا يخص تطبيق هوى الشام")
        if str(data.get("kind") or "") not in {"mobile_pairing", "pairing", ""}:
            raise ValueError("نوع رمز الربط غير مدعوم")
        pairing_contract = str(data.get("pairing_contract") or PAIRING_CONTRACT_VERSION)
        if pairing_contract != PAIRING_CONTRACT_VERSION:
            raise ValueError(f"عقد الربط غير متوافق: {pairing_contract}")
        currency_contract = str(data.get("currency_contract") or "")
        if currency_contract and currency_contract != CURRENCY_CONTRACT_VERSION:
            raise ValueError(f"عقد العملات غير متوافق: {currency_contract}")
        server_url = NetworkService.normalize_server_url(str(data.get("server_url") or ""))
        token = str(data.get("pairing_token") or "").strip()
        if not token:
            raise ValueError("رمز الربط المؤقت غير موجود داخل QR")
        expiry = MobilePairingService._parse_expiry(data.get("expires_at"))
        if expiry and datetime.datetime.now(datetime.timezone.utc) > expiry:
            raise ValueError("انتهت صلاحية رمز QR. أنشئ رمزاً جديداً من Windows")
        validated = dict(data)
        validated["server_url"] = server_url
        validated["pairing_token"] = token
        return validated

    @staticmethod
    def _verify_capabilities(server_url: str) -> tuple[RestClient, Dict[str, Any], list[str]]:
        client = RestClient(server_url)
        caps = client.capabilities()
        missing: list[str] = []
        if not caps.get("supports_historic_currency_snapshot"):
            missing.append("الخادم لا يدعم السعر التاريخي للعملات")
        if str(caps.get("currency_contract") or "") != CURRENCY_CONTRACT_VERSION:
            missing.append(f"عقد العملات غير متوافق: {caps.get('currency_contract')}")
        required_flags = {
            "supports_amount_base": "الخادم لا يدعم amount_base",
            "supports_exchange_rate_history": "الخادم لا يدعم تاريخ أسعار الصرف",
            "supports_expense_summary": "الخادم لا يدعم ملخص القيود المطلوب لتطبيق Android",
            "supports_payment_reminders": "الخادم لا يدعم تنبيهات الدفع المطلوبة لتطبيق Android",
            "supports_audit_post": "الخادم لا يدعم إرسال سجل التدقيق من Android",
        }
        missing.extend(message for key, message in required_flags.items() if not caps.get(key))
        endpoints = set(caps.get("endpoints") or [])
        required_endpoints = {
            "/api/health",
            "/api/expenses/summary",
            "/api/payment_reminders",
            "/api/payment_reminders/count_waiting",
            "/api/audit_log",
        }
        if endpoints:
            missing.extend(f"الخادم لا يعلن endpoint المطلوب: {ep}" for ep in sorted(required_endpoints - endpoints))
        return client, caps, missing

    @staticmethod
    def pair_from_qr_text(qr_text: str) -> PairingResult:
        payload = MobilePairingService.validate_payload(MobilePairingService.parse_qr_text(qr_text))
        server_url = payload["server_url"]
        client, caps, missing = MobilePairingService._verify_capabilities(server_url)
        if missing:
            return PairingResult(False, "الخادم قديم أو غير متوافق مع APK الحالي: " + "؛ ".join(missing), server_url)
        pair_response = client.pair_mobile(payload["pairing_token"])
        if not pair_response.get("ok"):
            return PairingResult(False, str(pair_response.get("error") or "رفض الخادم عملية الربط"), server_url)
        NetworkService.save_mode("client", server_url)
        return PairingResult(
            True,
            str(pair_response.get("message") or "تم ربط الهاتف بالخادم. سجّل الدخول بحسابك."),
            server_url=server_url,
            server_name=str(pair_response.get("server_name") or payload.get("server_name") or "هوى الشام"),
            api_contract_version=str(pair_response.get("api_contract_version") or caps.get("api_contract_version") or ""),
            currency_contract=str(pair_response.get("currency_contract") or caps.get("currency_contract") or ""),
        )

    @staticmethod
    def pair_with_code(server_url: str, pairing_code: str) -> PairingResult:
        server_url = NetworkService.normalize_server_url(str(server_url or ""))
        code = "".join(ch for ch in str(pairing_code or "") if ch.isdigit())
        if not code:
            return PairingResult(False, "أدخل رمز الربط اليدوي الذي يظهر في Windows", server_url)
        client, caps, missing = MobilePairingService._verify_capabilities(server_url)
        if missing:
            return PairingResult(False, "الخادم قديم أو غير متوافق مع APK الحالي: " + "؛ ".join(missing), server_url)
        pair_response = client.pair_mobile_code(code, server_url)
        if not pair_response.get("ok"):
            return PairingResult(False, str(pair_response.get("error") or "رفض الخادم رمز الربط اليدوي"), server_url)
        NetworkService.save_mode("client", server_url)
        return PairingResult(
            True,
            str(pair_response.get("message") or "تم ربط الهاتف بالخادم. سجّل الدخول بحسابك."),
            server_url=server_url,
            server_name=str(pair_response.get("server_name") or caps.get("server_name") or "هوى الشام"),
            api_contract_version=str(pair_response.get("api_contract_version") or caps.get("api_contract_version") or ""),
            currency_contract=str(pair_response.get("currency_contract") or caps.get("currency_contract") or ""),
        )
