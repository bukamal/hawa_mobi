# -*- coding: utf-8 -*-
import requests, time
from typing import List, Dict

class RestClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self.token = None
    def set_token(self, token: str): self.token = token
    def _headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.token: headers['Authorization'] = f'Bearer {self.token}'
        return headers
    def _request(self, method, endpoint, data=None, retries=3, backoff=1.0):
        url = f"{self.server_url}{endpoint}"
        for attempt in range(retries):
            try:
                resp = requests.request(method, url, json=data, headers=self._headers(), timeout=10)
                if resp.status_code == 429:
                    wait = min(30, backoff * (4**attempt))
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    raise Exception(f"API error {resp.status_code}: {resp.text}")
                return resp.json() if resp.text else None
            except Exception as e:
                if attempt == retries-1: raise
                time.sleep(backoff * (2**attempt))
    def login(self, username: str, password: str) -> Dict:
        res = self._request('POST', '/api/login', {'username': username, 'password': password})
        self.set_token(res['token'])
        return res['user']
    def logout(self): self._request('POST', '/api/logout'); self.token = None
    def get_expenses(self) -> List[Dict]: return self._request('GET', '/api/expenses')
    def add_expense(self, data: Dict) -> int: return self._request('POST', '/api/expenses', data)['id']
    def update_expense(self, expense_id: int, data: Dict): self._request('PUT', f'/api/expenses/{expense_id}', data)
    def delete_expense(self, expense_id: int): self._request('DELETE', f'/api/expenses/{expense_id}')
    def get_users(self) -> List[Dict]: return self._request('GET', '/api/users')
    def add_user(self, data: Dict) -> int: return self._request('POST', '/api/users', data)['id']
    def update_user(self, user_id: int, data: Dict): self._request('PUT', f'/api/users/{user_id}', data)
    def delete_user(self, user_id: int): self._request('DELETE', f'/api/users/{user_id}')
    def change_password(self, old_password: str, new_password: str): self._request('POST', '/api/users/change_password', {'old_password': old_password, 'new_password': new_password})
    def get_audit_log(self) -> List[Dict]: return self._request('GET', '/api/audit_log')
    def delete_old_audit_logs(self, days: int=90): self._request('DELETE', '/api/audit_log/old', {'days': days})
    def get_setting(self, key: str): return self._request('GET', f'/api/settings/{key}').get('value')
    def set_setting(self, key: str, value: str): self._request('POST', f'/api/settings/{key}', {'value': value})
    def get_all_currencies(self): return self._request('GET', '/api/exchange_rates')
    def update_exchange_rate(self, currency_code: str, rate_to_usd: float): self._request('PUT', f'/api/exchange_rates/{currency_code}', {'rate_to_usd': rate_to_usd})
