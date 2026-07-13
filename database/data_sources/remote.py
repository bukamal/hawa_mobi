# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Any


class RemoteDataSource:
    """REST-backed data source for client network mode."""

    def __init__(self, rest_client):
        if rest_client is None:
            raise ValueError("RemoteDataSource requires an initialized RestClient")
        self.rest = rest_client

    def is_remote(self) -> bool:
        return True

    def execute(self, sql: str, params=(), audit_data=None):
        raise NotImplementedError("Raw SQL is not allowed in network client mode")

    def executemany(self, sql: str, params_list, audit_data=None):
        raise NotImplementedError("Raw SQL is not allowed in network client mode")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def begin(self) -> None:
        return None

    def get_expenses(self) -> List[Dict[str, Any]]:
        return self.rest.get_expenses()

    def add_expense(self, data: Dict[str, Any]) -> int:
        return int(self.rest.add_expense(data))

    def update_expense(self, expense_id: int, data: Dict[str, Any]) -> None:
        self.rest.update_expense(int(expense_id), data)

    def delete_expense(self, expense_id: int) -> None:
        self.rest.delete_expense(int(expense_id))


    def search_company_ledger(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.rest.search_company_ledger(query, limit=limit)

    def get_users(self) -> List[Dict[str, Any]]:
        return self.rest.get_users()

    def add_user(self, data: Dict[str, Any]) -> int:
        return int(self.rest.add_user(data))

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return self.rest.get_audit_log()

    def get_setting(self, key: str, default=None):
        value = self.rest.get_setting(key)
        return default if value is None else value

    def set_setting(self, key: str, value: str) -> None:
        self.rest.set_setting(key, value)

    def get_all_currencies(self) -> List[Dict[str, Any]]:
        return self.rest.get_all_currencies()

    def update_exchange_rate(self, currency_code: str, rate_to_usd: float) -> None:
        self.rest.update_exchange_rate(currency_code, float(rate_to_usd))

    def get_exchange_rate_history(self) -> List[Dict[str, Any]]:
        return self.rest.get_exchange_rate_history()
