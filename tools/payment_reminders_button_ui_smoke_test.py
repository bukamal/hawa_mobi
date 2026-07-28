#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI callback regression for the payment-reminders 'Register payment' button."""
from __future__ import annotations

import views.payment_reminders_mobile_view as screen


class FakePage:
    pass


class Receiver:
    def __init__(self):
        self._page = FakePage()

    def _after_payment(self):
        return None


def main():
    receiver = Receiver()
    captured = {}

    class FakePaymentDialog:
        def __init__(self, page, record, on_save=None):
            captured["page"] = page
            captured["record"] = dict(record)
            captured["on_save"] = on_save

    original_dialog = screen.PaymentDialog
    original_open = screen.open_control
    original_snackbar = screen.show_snackbar
    try:
        screen.PaymentDialog = FakePaymentDialog
        screen.open_control = lambda page, dialog: captured.update(opened=True, dialog=dialog)
        screen.show_snackbar = lambda *args, **kwargs: captured.update(snackbar=(args, kwargs))

        screen.PaymentRemindersMobileView._open_payment(
            receiver,
            {"id": 1, "expense_id": 44, "company_name": "شركة الاختبار", "type": "incoming"},
        )
        assert captured.get("opened") is True
        assert captured["record"]["id"] == 44
        assert captured["record"]["expense_id"] == 44
        assert captured["record"]["reminder_id"] == 1
        assert "snackbar" not in captured

        class BrokenPaymentDialog:
            def __init__(self, *args, **kwargs):
                raise ValueError("اختبار فشل البناء")

        captured.clear()
        screen.PaymentDialog = BrokenPaymentDialog
        screen.PaymentRemindersMobileView._open_payment(
            receiver,
            {"id": 2, "expense_id": 45, "company_name": "شركة الاختبار"},
        )
        assert "snackbar" in captured
        args, kwargs = captured["snackbar"]
        assert "تعذر فتح نافذة تسجيل الدفعة" in args[1]
        assert kwargs.get("is_error") is True
    finally:
        screen.PaymentDialog = original_dialog
        screen.open_control = original_open
        screen.show_snackbar = original_snackbar

    print("payment_reminders_button_ui_smoke_test passed")


if __name__ == "__main__":
    main()
