# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import flet as ft

from auth.session import UserSession
from currency import currency
from database import ThirdPartyPaymentRepository
from i18n.translator import translate
from views.flet_compat import close_control, ALIGN_CENTER
from views.dialogs.dialog_kit import (
    dialog_title,
    dialog_body,
    cancel_button,
    save_button,
    show_snackbar,
    set_button_busy,
    normalize_text,
    parse_non_negative_amount,
)


class ThirdPartyPaymentDialog(ft.AlertDialog):
    """Mobile dialog for: شركة سدّدت عني لشركة أخرى."""

    def __init__(
        self, page, on_save=None, payer_company_name=None, paid_to_company_name=None
    ):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self._saving = False

        page_width = self._page.width or 400
        page_height = self._page.height or 650
        dialog_width = min(390, page_width - 36)
        dialog_height = min(540, page_height - 90)

        self.payer_field = ft.TextField(
            label=translate("payer_company"),
            value=payer_company_name or "",
            width=dialog_width - 20,
        )
        self.paid_to_field = ft.TextField(
            label=translate("paid_to_company"),
            value=paid_to_company_name or "",
            disabled=bool(paid_to_company_name),
            width=dialog_width - 20,
        )
        self.amount_field = ft.TextField(
            label=translate("amount"),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=dialog_width - 150,
            value="",
        )
        self.currency_dropdown = ft.Dropdown(
            label=translate("currency"),
            value=currency.get_display_currency(),
            options=[
                ft.dropdown.Option(c)
                for c in ["USD", "SAR", "SYP", "EUR", "GBP", "AED", "QAR", "KWD", "OMR"]
            ],
            width=120,
        )
        self.date_field = ft.TextField(
            label=translate("date"),
            value=datetime.datetime.now().strftime("%Y-%m-%d"),
            hint_text="YYYY-MM-DD",
            width=150,
        )
        self.notes_field = ft.TextField(
            label=translate("notes"),
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=dialog_width - 20,
        )
        self.exchange_rate_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        self.preview_text = ft.Text(
            "", size=12, color=ft.Colors.INDIGO, weight=ft.FontWeight.BOLD
        )
        self.preview_box = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.SWAP_HORIZ, size=18, color=ft.Colors.INDIGO
                            ),
                            ft.Text(
                                translate("preview"), weight=ft.FontWeight.BOLD, size=13
                            ),
                        ]
                    ),
                    self.preview_text,
                    ft.Text(
                        "لا يتم لمس الصندوق أو البنك؛ يتم فقط نقل الذمة من شركة إلى شركة.",
                        size=11,
                        color=ft.Colors.GREY_600,
                    ),
                ],
                spacing=6,
            ),
            bgcolor=ft.Colors.INDIGO_50,
            border_radius=12,
            padding=10,
        )

        self.save_btn = save_button(translate("save"), self._save)
        self.title = dialog_title(translate("third_party_payment"), ft.Icons.SWAP_HORIZ)
        self.content = dialog_body(
            controls=[
                ft.Text(
                    "شركة دفعت عنك لشركة أخرى؛ التطبيق ينشئ قيدين متوازنين تلقائياً.",
                    size=12,
                    color=ft.Colors.GREY_600,
                ),
                self.payer_field,
                self.paid_to_field,
                ft.Row(
                    [self.amount_field, self.currency_dropdown], spacing=10, wrap=True
                ),
                ft.Row([self.date_field], spacing=10, wrap=True),
                ft.Container(content=self.exchange_rate_text, alignment=ALIGN_CENTER),
                self.preview_box,
                self.notes_field,
            ],
            spacing=14,
            width=dialog_width - 10,
            height=dialog_height - 105,
        )
        self.actions = [
            cancel_button(translate("cancel"), lambda e: self._close()),
            self.save_btn,
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 18
        self.shape = ft.RoundedRectangleBorder(radius=15)

        self.amount_field.on_change = self._update_preview
        self.currency_dropdown.on_change = self._update_preview
        self.payer_field.on_change = self._update_preview
        self.paid_to_field.on_change = self._update_preview
        self._update_preview(None)

    def _close(self):
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _update_preview(self, e):
        payer = normalize_text(self.payer_field.value) or "الشركة التي سدّدت عني"
        paid_to = (
            normalize_text(self.paid_to_field.value) or "الشركة التي تم السداد لها"
        )
        code = self.currency_dropdown.value or currency.get_display_currency()
        try:
            amount = float(str(self.amount_field.value or "0").replace(",", "."))
        except Exception:
            amount = 0.0
        try:
            rate = currency.get_rate_to_usd(code)
            display_curr = currency.get_display_currency()
            base_usd = amount / rate if rate else amount
            display_amount = currency.convert(base_usd, "USD", display_curr)
            self.exchange_rate_text.value = f"المخزّن محاسبياً: {base_usd:.4f} USD | المعروض: {currency.format_amount(display_amount, display_curr)}"
        except Exception:
            self.exchange_rate_text.value = ""
        amount_str = currency.format_amount(amount, code) if amount else "—"
        self.preview_text.value = f"{translate('will_decrease_paid_to')}: {paid_to} بمبلغ {amount_str}\n{translate('will_increase_payer')}: {payer} بمبلغ {amount_str}"
        try:
            self._page.update()
        except Exception:
            pass

    def _save(self, e):
        if self._saving:
            return
        payer = normalize_text(self.payer_field.value)
        paid_to = normalize_text(self.paid_to_field.value)
        if not payer:
            self._show_snackbar("الشركة التي سدّدت عني مطلوبة", True)
            return
        if not paid_to:
            self._show_snackbar("الشركة التي تم السداد لها مطلوبة", True)
            return
        if payer == paid_to:
            self._show_snackbar(translate("cannot_same_company"), True)
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
        except Exception as ex:
            self._show_snackbar(str(ex), True)
            return
        if amount <= 0:
            self._show_snackbar("المبلغ يجب أن يكون أكبر من صفر", True)
            return
        user = UserSession.get_current() or {}
        user_id = user.get("id") or 1
        self._saving = True
        set_button_busy(self.save_btn, True, translate("save"))
        try:
            repo = ThirdPartyPaymentRepository()
            result = repo.add_payment_on_behalf(
                payer_company_name=payer,
                paid_to_company_name=paid_to,
                amount=amount,
                currency_code=self.currency_dropdown.value,
                date=self.date_field.value
                or datetime.datetime.now().strftime("%Y-%m-%d"),
                notes=self.notes_field.value or "",
                user_id=user_id,
            )
            self._close()
            if self.on_save:
                self.on_save(result)
            self._show_snackbar(
                f"{translate('payment_on_behalf_saved')} | {result.get('reference', '')}",
                False,
            )
        except Exception as ex:
            self._show_snackbar(f"فشل الحفظ: {str(ex)}", True)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, translate("save"))
            try:
                self._page.update()
            except Exception:
                pass
