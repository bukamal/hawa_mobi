# -*- coding: utf-8 -*-
"""Historical-currency ledger helpers shared by the Android/Flet client and server.

Contract compatible with Hawaa Windows Phase 17:
- amount_original: user-entered amount in the original transaction currency.
- currency_original: original transaction currency.
- exchange_rate_to_usd: immutable rate snapshot for the transaction.
- amount_base: accounting value in USD.
- amount: legacy mirror of amount_base for older mobile views.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


class CurrencyLedgerService:
    BASE_CURRENCY = "USD"

    def __init__(self, rate_getter=None):
        # rate_getter(currency_code) -> rate_to_usd where 1 USD = rate units.
        if rate_getter is None:
            from currency import currency

            rate_getter = currency.get_rate_to_usd
        self.rate_getter = rate_getter

    def get_rate_to_usd(self, currency_code: str) -> float:
        code = (currency_code or self.BASE_CURRENCY).upper()
        if code == self.BASE_CURRENCY:
            return 1.0
        rate = _to_float(self.rate_getter(code), 1.0)
        return rate if rate > 0 else 1.0

    def to_base(
        self, amount_original: float, currency_code: str, rate_to_usd: float
    ) -> float:
        amount_original = _to_float(amount_original, 0.0)
        code = (currency_code or self.BASE_CURRENCY).upper()
        rate = _to_float(rate_to_usd, 1.0)
        if code == self.BASE_CURRENCY:
            return amount_original
        if rate <= 0:
            raise ValueError("سعر الصرف يجب أن يكون أكبر من صفر")
        return amount_original / rate

    def from_base(self, amount_base: float, display_currency: str) -> float:
        amount_base = _to_float(amount_base, 0.0)
        code = (display_currency or self.BASE_CURRENCY).upper()
        if code == self.BASE_CURRENCY:
            return amount_base
        return amount_base * self.get_rate_to_usd(code)

    def snapshot(
        self,
        amount_original: float,
        currency_code: str,
        *,
        existing: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a historical snapshot.

        When editing an existing transaction and the original currency did not
        change, the previous exchange_rate_to_usd is preserved. If the currency
        changes, a fresh rate snapshot is captured.
        """
        code = (currency_code or self.BASE_CURRENCY).upper()
        amount_original = _to_float(amount_original, 0.0)
        existing_currency = (
            (existing or {}).get("currency_original")
            or (existing or {}).get("currency")
            or ""
        ).upper()
        if existing and existing_currency == code:
            rate = _to_float(
                (existing or {}).get("exchange_rate_to_usd"), self.get_rate_to_usd(code)
            )
            if rate <= 0:
                rate = self.get_rate_to_usd(code)
        else:
            rate = self.get_rate_to_usd(code)
        amount_base = self.to_base(amount_original, code, rate)
        return {
            "amount_original": amount_original,
            "currency_original": code,
            "exchange_rate_to_usd": rate,
            "amount_base": amount_base,
            # Legacy mirror: existing APK views still read `amount` as USD base.
            "amount": amount_base,
            "currency": code,
        }

    def normalize_expense_payload(
        self, data: Mapping[str, Any], *, existing: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        code = (
            data.get("currency_original") or data.get("currency") or self.BASE_CURRENCY
        ).upper()
        amount_original = data.get("amount_original")
        if amount_original in (None, ""):
            # Client UIs usually send amount as the original user input. Older
            # remote payloads may send only amount; treat it as original input
            # and recompute amount_base server-side.
            amount_original = data.get("amount", 0)
        snap = self.snapshot(amount_original, code, existing=existing)
        status = data.get("status") or (
            "waiting_payment" if snap["amount_original"] == 0 else "approved"
        )
        normalized = dict(data)
        normalized.update(snap)
        normalized["status"] = status
        normalized["payment_due_date"] = data.get("payment_due_date")
        normalized["payment_reminder_note"] = data.get("payment_reminder_note")
        return normalized
