#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke-test short-code mobile pairing without requiring a live Windows server."""

from __future__ import annotations

import services.pairing_service as ps


class FakeRestClient:
    def __init__(self, server_url: str):
        self.server_url = server_url

    def capabilities(self):
        return {
            "supports_historic_currency_snapshot": True,
            "currency_contract": ps.CURRENCY_CONTRACT_VERSION,
            "supports_amount_base": True,
            "supports_exchange_rate_history": True,
            "supports_expense_summary": True,
            "supports_payment_reminders": True,
            "supports_audit_post": True,
            "endpoints": [
                "/api/health",
                "/api/expenses/summary",
                "/api/payment_reminders",
                "/api/payment_reminders/count_waiting",
                "/api/audit_log",
            ],
            "api_contract_version": "2026.07.mobile-v1",
            "server_name": "هوى الشام",
        }

    def pair_mobile_code(self, pairing_code: str, server_url: str | None = None):
        assert pairing_code == "482913"
        assert server_url == "http://127.0.0.1:8000"
        return {
            "ok": True,
            "paired": True,
            "server_name": "هوى الشام",
            "server_url": server_url,
            "api_contract_version": "2026.07.mobile-v1",
            "currency_contract": ps.CURRENCY_CONTRACT_VERSION,
            "message": "تم ربط الهاتف بالخادم. سجّل الدخول بحسابك.",
        }


def main() -> int:
    original = ps.RestClient
    ps.RestClient = FakeRestClient
    try:
        result = ps.MobilePairingService.pair_with_code(
            "http://127.0.0.1:8000",
            "482-913",
            allow_insecure_http=True,
        )
        assert result.ok is True
        assert result.server_url == "http://127.0.0.1:8000"
        assert result.currency_contract == ps.CURRENCY_CONTRACT_VERSION
    finally:
        ps.RestClient = original
    print("manual_pairing_code_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
