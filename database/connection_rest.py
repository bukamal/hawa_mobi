# -*- coding: utf-8 -*-
import requests
import time
from typing import List, Dict
from urllib.parse import urlparse


def _clean_server_root(server_url: str) -> str:
    root = (server_url or "").strip().rstrip("/")
    if root.endswith("/api"):
        root = root[:-4].rstrip("/")
    try:
        parsed = urlparse(root if "://" in root else "http://" + root)
        host = (parsed.hostname or "").lower()
        if host in {"0.0.0.0", "::"}:  # nosec B104 - address comparison/normalization, not socket binding
            port = f":{parsed.port}" if parsed.port else ""
            root = f"{parsed.scheme or 'http'}://127.0.0.1{port}"
    except Exception:
        pass
    return root


def _is_localhost_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}  # nosec B104 - address comparison/normalization, not socket binding


class RestClient:
    def __init__(self, server_url: str):
        # Accept either bare server URL (http://host:8000) or a mistakenly
        # entered API base URL (http://host:8000/api).  Internally we always
        # keep the server root so endpoint paths remain stable.
        self.server_url = _clean_server_root(server_url)
        self.token = None

    def set_token(self, token: str):
        self.token = (token or "").strip()

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        token = (self.token or "").strip()
        if not token:
            try:
                from auth.session import UserSession

                token = (UserSession.get_auth_token() or "").strip()
            except Exception:
                token = ""
        if token:
            self.token = token
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _requires_auth(self, endpoint: str) -> bool:
        return not (
            endpoint
            in {
                "/api/login",
                "/api/health",
                "/health",
                "/api/capabilities",
                "/api/mobile/pair",
            }
            or endpoint.startswith("/api/health")
        )

    def _resolve_server_url(self) -> str:
        root = _clean_server_root(self.server_url)
        # The app may be installed over an older build where DatabaseConnection
        # was initialized before the user saved the real server IP. Refresh the
        # persisted bootstrap setting at request time so no protected endpoint
        # silently falls back to localhost.
        try:
            from database.connection import _get_local_setting_direct

            saved = _clean_server_root(
                _get_local_setting_direct("network/server_url", "") or ""
            )
            if saved and saved != root:
                # Prefer a non-localhost saved server over an old localhost
                # instance value. This fixes audit/users screens after mode
                # changes without restarting the APK.
                if _is_localhost_url(root) or not root:
                    root = saved
        except Exception:
            pass
        if not root:
            raise Exception(
                "عنوان الخادم غير مضبوط. افتح الإعدادات > الشبكة وأدخل IP جهاز الخادم."
            )
        # Localhost is allowed for same-device desktop/emulator QA. Real phones
        # should still use the Windows LAN IP, but blocking localhost here made
        # automated pairing tests impossible when both clients run on one host.
        self.server_url = root
        return root

    def _request(self, method, endpoint, data=None, retries=3, backoff=1.0):
        root = self._resolve_server_url()
        url = f"{root}{endpoint}"
        headers = self._headers()
        if self._requires_auth(endpoint) and "Authorization" not in headers:
            raise Exception(
                "انتهت جلسة الشبكة أو لم يتم تسجيل الدخول على الخادم. سجّل الخروج ثم ادخل من جديد في وضع عميل الشبكة."
            )
        for attempt in range(retries):
            try:
                resp = requests.request(
                    method, url, json=data, headers=headers, timeout=10
                )
                if resp.status_code == 429:
                    wait = min(30, backoff * (4**attempt))
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    hint = ""
                    if resp.status_code == 404 and endpoint.startswith("/api/"):
                        hint = " — تحقق أن عنوان الخادم لا ينتهي بـ /api وأنك تشغّل server/run_server.py من النسخة الحالية."
                    raise Exception(f"API error {resp.status_code}: {resp.text}{hint}")
                return resp.json() if resp.text else None
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(backoff * (2**attempt))

    def health(self) -> Dict:
        try:
            return self._request("GET", "/api/health", retries=1)
        except Exception as e:
            # Compatibility with older server builds that exposed /health.
            if "API error 404" in str(e):
                return self._request("GET", "/health", retries=1)
            raise

    def capabilities(self) -> Dict:
        """Return public server capabilities for APK/Windows pairing checks."""
        try:
            return self._request("GET", "/api/capabilities", retries=1)
        except Exception as e:
            # Older Phase-18 compatible servers may not expose /api/capabilities.
            # In that case use /api/health as a weak compatibility signal.
            if "API error 404" in str(e):
                health = self.health() or {}
                return {
                    "ok": bool(health.get("ok")),
                    "service": health.get("service", "hawaa-server"),
                    "api_contract_version": health.get(
                        "api_contract_version", "legacy"
                    ),
                    "currency_contract": health.get("currency_contract", ""),
                    "supports_historic_currency_snapshot": bool(
                        health.get("supports_historic_currency_snapshot")
                    ),
                }
            raise

    def pair_mobile(self, pairing_token: str) -> Dict:
        return self._request(
            "POST", "/api/mobile/pair", {"pairing_token": pairing_token}, retries=1
        )

    def pair_mobile_code(
        self, pairing_code: str, server_url: str | None = None
    ) -> Dict:
        data = {"pairing_code": pairing_code}
        if server_url:
            data["server_url"] = server_url
        return self._request("POST", "/api/mobile/pair", data, retries=1)

    def login(self, username: str, password: str) -> Dict:
        res = self._request(
            "POST", "/api/login", {"username": username, "password": password}
        )
        token = res.get("token") or res.get("access_token")
        if not token:
            raise Exception("لم يرجع الخادم رمز دخول token")
        self.set_token(token)
        user = dict(res.get("user") or {})
        user["_auth_token"] = token
        if res.get("expires_in") is not None:
            user["_token_expires_in"] = res.get("expires_in")
        return user

    def logout(self):
        self._request("POST", "/api/logout")
        self.token = None
        try:
            from auth.session import UserSession

            UserSession.logout()
        except Exception:
            pass

    def get_expenses(self) -> List[Dict]:
        return self._request("GET", "/api/expenses")

    def add_expense(self, data: Dict) -> int:
        return self._request("POST", "/api/expenses", data)["id"]

    def update_expense(self, expense_id: int, data: Dict):
        self._request("PUT", f"/api/expenses/{expense_id}", data)

    def delete_expense(self, expense_id: int):
        self._request("DELETE", f"/api/expenses/{expense_id}")

    def get_expense_summary(self) -> Dict:
        return self._request("GET", "/api/expenses/summary")

    def add_service_case(self, data: Dict) -> Dict:
        try:
            return self._request("POST", "/api/service_cases", data)
        except Exception as exc:
            if "API error 404" in str(exc):
                raise Exception(
                    "خادم ويندوز لا يدعم ملفات الخدمات الوسيطة بعد. حدّث الخادم إلى النسخة الحالية."
                ) from exc
            raise

    def get_service_cases(self) -> List[Dict]:
        return self._request("GET", "/api/service_cases")

    def reverse_service_case(self, reference: str) -> Dict:
        return self._request("POST", f"/api/service_cases/{reference}/reverse")

    def add_third_party_payment(self, data: Dict) -> Dict:
        try:
            return self._request("POST", "/api/third_party_payments", data)
        except Exception as exc:
            if "API error 404" in str(exc):
                raise Exception(
                    "خادم ويندوز لا يدعم سداد بالنيابة بعد. حدّث مشروع الويندوز إلى Phase 50 أو شغّل server/run_server.py من النسخة الجديدة."
                ) from exc
            raise

    def reverse_third_party_payment(self, reference: str) -> Dict:
        return self._request("POST", f"/api/third_party_payments/{reference}/reverse")

    def get_pending_payment_reminders(self) -> List[Dict]:
        return self._request("GET", "/api/payment_reminders")

    def count_waiting_payment(self) -> int:
        return int(
            self._request("GET", "/api/payment_reminders/count_waiting").get("count", 0)
        )

    def search_company_ledger(self, query: str, limit: int = 100) -> List[Dict]:
        from urllib.parse import quote

        q = quote(str(query or "").strip())
        try:
            return self._request(
                "GET", f"/api/search/company-ledger?q={q}&limit={int(limit or 100)}"
            )
        except Exception as exc:
            if "API error 404" in str(exc):
                # Older Windows servers do not expose the deep-search endpoint.
                # Fallback keeps Android usable, but without username/full-name matching.
                from services.company_search_service import search_expense_rows

                return search_expense_rows(self.get_expenses(), query, limit=limit)
            raise

    def get_users(self) -> List[Dict]:
        return self._request("GET", "/api/users")

    def add_user(self, data: Dict) -> int:
        return self._request("POST", "/api/users", data)["id"]

    def update_user(self, user_id: int, data: Dict):
        self._request("PUT", f"/api/users/{user_id}", data)

    def delete_user(self, user_id: int):
        self._request("DELETE", f"/api/users/{user_id}")

    def change_password(self, old_password: str, new_password: str):
        self._request(
            "POST",
            "/api/users/change_password",
            {"old_password": old_password, "new_password": new_password},
        )

    def get_audit_log(self) -> List[Dict]:
        return self._request("GET", "/api/audit_log")

    def add_audit_log(
        self,
        user_id: int,
        username: str,
        action: str,
        table_name: str,
        record_id: int,
        details: str,
    ):
        """إرسال سجل تدقيق جديد إلى الخادم"""
        self._request(
            "POST",
            "/api/audit_log",
            {
                "user_id": user_id,
                "username": username,
                "action": action,
                "table_name": table_name,
                "record_id": record_id,
                "details": details,
            },
        )

    def delete_old_audit_logs(self, days: int = 90):
        self._request("DELETE", "/api/audit_log/old", {"days": days})

    def get_setting(self, key: str):
        return self._request("GET", f"/api/settings/{key}").get("value")

    def set_setting(self, key: str, value: str):
        self._request("POST", f"/api/settings/{key}", {"value": value})

    def get_all_currencies(self):
        return self._request("GET", "/api/exchange_rates")

    def get_exchange_rate_history(self):
        return self._request("GET", "/api/exchange_rate_history")

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float):
        self._request(
            "PUT", f"/api/exchange_rates/{currency_code}", {"rate_to_usd": rate_to_usd}
        )
