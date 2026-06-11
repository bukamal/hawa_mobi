# -*- coding: utf-8 -*-
import requests, time
from typing import List, Dict

class RestClient:
    def __init__(self, server_url: str):
        # Accept either bare server URL (http://host:8000) or a mistakenly
        # entered API base URL (http://host:8000/api).  Internally we always
        # keep the server root so endpoint paths remain stable.
        root = (server_url or '').strip().rstrip('/')
        if root.endswith('/api'):
            root = root[:-4].rstrip('/')
        self.server_url = root
        self.token = None

    def set_token(self, token: str):
        self.token = token

    def _headers(self):
        headers = {'Content-Type': 'application/json'}
        token = self.token
        if not token:
            try:
                from auth.session import UserSession
                token = UserSession.get_auth_token()
                if token:
                    self.token = token
            except Exception:
                token = None
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def _request(self, method, endpoint, data=None, retries=3, backoff=1.0):
        if not self.server_url:
            raise Exception('عنوان الخادم غير مضبوط')
        url = f"{self.server_url}{endpoint}"
        for attempt in range(retries):
            try:
                resp = requests.request(method, url, json=data, headers=self._headers(), timeout=10)
                if resp.status_code == 429:
                    wait = min(30, backoff * (4**attempt))
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    hint = ''
                    if resp.status_code == 404 and endpoint.startswith('/api/'):
                        hint = ' — تحقق أن عنوان الخادم لا ينتهي بـ /api وأنك تشغّل server/run_server.py من النسخة الحالية.'
                    raise Exception(f"API error {resp.status_code}: {resp.text}{hint}")
                return resp.json() if resp.text else None
            except Exception:
                if attempt == retries-1:
                    raise
                time.sleep(backoff * (2**attempt))


    def health(self) -> Dict:
        try:
            return self._request('GET', '/api/health', retries=1)
        except Exception as e:
            # Compatibility with older server builds that exposed /health.
            if 'API error 404' in str(e):
                return self._request('GET', '/health', retries=1)
            raise

    def login(self, username: str, password: str) -> Dict:
        res = self._request('POST', '/api/login', {'username': username, 'password': password})
        token = res.get('token') or res.get('access_token')
        if not token:
            raise Exception('لم يرجع الخادم رمز دخول token')
        self.set_token(token)
        user = dict(res.get('user') or {})
        user['_auth_token'] = token
        if res.get('expires_in') is not None:
            user['_token_expires_in'] = res.get('expires_in')
        return user

    def logout(self):
        self._request('POST', '/api/logout')
        self.token = None

    def get_expenses(self) -> List[Dict]:
        return self._request('GET', '/api/expenses')

    def add_expense(self, data: Dict) -> int:
        return self._request('POST', '/api/expenses', data)['id']

    def update_expense(self, expense_id: int, data: Dict):
        self._request('PUT', f'/api/expenses/{expense_id}', data)

    def delete_expense(self, expense_id: int):
        self._request('DELETE', f'/api/expenses/{expense_id}')

    def get_expense_summary(self) -> Dict:
        return self._request('GET', '/api/expenses/summary')

    def get_pending_payment_reminders(self) -> List[Dict]:
        return self._request('GET', '/api/payment_reminders')

    def count_waiting_payment(self) -> int:
        return int(self._request('GET', '/api/payment_reminders/count_waiting').get('count', 0))

    def get_users(self) -> List[Dict]:
        return self._request('GET', '/api/users')

    def add_user(self, data: Dict) -> int:
        return self._request('POST', '/api/users', data)['id']

    def update_user(self, user_id: int, data: Dict):
        self._request('PUT', f'/api/users/{user_id}', data)

    def delete_user(self, user_id: int):
        self._request('DELETE', f'/api/users/{user_id}')

    def change_password(self, old_password: str, new_password: str):
        self._request('POST', '/api/users/change_password', {'old_password': old_password, 'new_password': new_password})

    def get_audit_log(self) -> List[Dict]:
        return self._request('GET', '/api/audit_log')

    def add_audit_log(self, user_id: int, username: str, action: str, table_name: str, record_id: int, details: str):
        """إرسال سجل تدقيق جديد إلى الخادم"""
        self._request('POST', '/api/audit_log', {
            'user_id': user_id,
            'username': username,
            'action': action,
            'table_name': table_name,
            'record_id': record_id,
            'details': details
        })

    def delete_old_audit_logs(self, days: int = 90):
        self._request('DELETE', '/api/audit_log/old', {'days': days})

    def get_setting(self, key: str):
        return self._request('GET', f'/api/settings/{key}').get('value')

    def set_setting(self, key: str, value: str):
        self._request('POST', f'/api/settings/{key}', {'value': value})

    def get_all_currencies(self):
        return self._request('GET', '/api/exchange_rates')

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float):
        self._request('PUT', f'/api/exchange_rates/{currency_code}', {'rate_to_usd': rate_to_usd})
