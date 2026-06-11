# -*- coding: utf-8 -*-
import datetime
import flet as ft
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from views.flet_compat import open_control, close_control

class AddEditExpenseDialog(ft.AlertDialog):
    def __init__(self, page, on_save=None, expense=None, company_name=None):
        super().__init__()
        self._page = page
        self.on_save = on_save
        self.expense = expense or None
        # لا تعتمد على truthiness لكائن القيد. مبلغ 0 أو كائنات صفوف SQLite/REST
        # قد تسبب التباساً في مسار create/update. ثبّت المعرّف صراحة.
        self.expense_id = None
        if self.expense is not None:
            try:
                self.expense_id = int(self.expense.get('id'))
            except Exception:
                try:
                    self.expense_id = int(self.expense['id'])
                except Exception:
                    self.expense_id = None

        # معالجة آمنة لـ company_name (قد يكون كائن Event أو سلسلة)
        predefined = None
        if company_name is not None and isinstance(company_name, str):
            predefined = company_name
        self.predefined_company = predefined

        # الحصول على أبعاد آمنة للشاشة
        page_width = self._page.width or 400
        page_height = self._page.height or 600
        dialog_width = min(380, page_width - 40)
        dialog_height = min(520, page_height - 100)

        is_disabled = (self.predefined_company is not None and self.predefined_company.strip() != "") and (self.expense_id is None)

        self.company_field = ft.TextField(
            label=translate('company_name'),
            value=self.predefined_company or (expense['company_name'] if expense else ""),
            disabled=is_disabled,
            width=dialog_width - 20
        )

        self.amount_field = ft.TextField(
            label=translate('amount'),
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(expense['amount_original'] if expense else ""),
            width=dialog_width - 20
        )

        self.currency_dropdown = ft.Dropdown(
            label=translate('currency'),
            value=expense.get('currency_original', 'SAR') if expense else currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=120
        )

        self.type_dropdown = ft.Dropdown(
            label=translate('type'),
            value=translate('incoming') if (not expense or expense['type']=='incoming') else translate('outgoing'),
            options=[ft.dropdown.Option(translate('incoming')), ft.dropdown.Option(translate('outgoing'))],
            width=120
        )

        self.date_picker_field = ft.TextField(
            label=translate('date'),
            value=expense['date'] if expense else datetime.datetime.now().strftime("%Y-%m-%d"),
            hint_text="YYYY-MM-DD",
            width=150,
            read_only=True,
            suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=self._open_date_picker)
        )
        self.date_picker = ft.DatePicker(
            on_change=self._on_date_change,
            first_date=datetime.datetime(2020, 1, 1),
            last_date=datetime.datetime.now() + datetime.timedelta(days=365*10)
        )

        self.notes_field = ft.TextField(
            label=translate('notes'),
            multiline=True,
            min_lines=2,
            max_lines=4,
            value=expense['notes'] if expense else "",
            width=dialog_width - 20
        )

        default_due = expense.get('payment_due_date') if expense else datetime.datetime.now().strftime("%Y-%m-%d")
        self.payment_due_field = ft.TextField(
            label="تاريخ تنبيه الدفع",
            value=default_due or datetime.datetime.now().strftime("%Y-%m-%d"),
            hint_text="YYYY-MM-DD",
            width=150,
        )
        self.payment_note_field = ft.TextField(
            label="ملاحظة تنبيه الدفع",
            value=(expense.get('payment_reminder_note') if expense else "") or "بانتظار إدخال الدفعة الأولى",
            width=dialog_width - 20,
        )
        self.zero_amount_notice = ft.Container(
            content=ft.Text(
                "📝 عند حفظ مبلغ صفر ستُحفظ العملية بانتظار الدفع ولن تؤثر على الأرصدة حتى تسجيل مبلغ مالي.",
                size=12,
                color=ft.Colors.ORANGE_900,
            ),
            bgcolor=ft.Colors.ORANGE_50,
            border_radius=10,
            padding=10,
            visible=False,
        )

        self.exchange_rate_text = ft.Text("", size=12, color=ft.Colors.GREY_600, italic=True)
        self.converted_amount_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)

        content = ft.Column(
            controls=[
                self.company_field,
                ft.Row([self.amount_field, self.currency_dropdown], spacing=10, wrap=True),
                ft.Row([self.type_dropdown, self.date_picker_field], spacing=10, wrap=True),
                ft.Container(content=self.exchange_rate_text, margin=ft.Margin(top=5, bottom=5, left=0, right=0)),
                ft.Container(content=self.converted_amount_text, alignment=ft.Alignment.CENTER),
                self.zero_amount_notice,
                ft.Row([self.payment_due_field], spacing=10, wrap=True),
                self.payment_note_field,
                self.notes_field
            ],
            spacing=15,
            width=dialog_width - 10,
            scroll=ft.ScrollMode.AUTO,
            height=dialog_height - 100
        )

        self.title = ft.Text(
            translate('edit') if self.expense_id is not None else translate('add'),
            size=18,
            weight=ft.FontWeight.BOLD
        )
        self.content = content
        self.actions = [
            ft.TextButton(translate('cancel'), on_click=lambda e: self._close()),
            ft.FilledButton(
                translate('save'),
                on_click=self._save,
                bgcolor=ft.Colors.INDIGO,
                color=ft.Colors.WHITE
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 20
        self.shape = ft.RoundedRectangleBorder(radius=15)

        self.amount_field.on_change = self._update_conversion
        self.currency_dropdown.on_change = self._update_conversion
        self._update_conversion(None)

    def _open_date_picker(self, e):
        open_control(self._page, self.date_picker)

    def _on_date_change(self, e):
        if self.date_picker.value:
            self.date_picker_field.value = self.date_picker.value.strftime("%Y-%m-%d")
            self._page.update()

    def _close(self):
        # Close the owned DatePicker first, then the dialog itself.
        # Otherwise APK/Web builds may keep a stale overlay entry and the dialog
        # appears to remain open after Cancel/Save.
        try:
            close_control(self._page, self.date_picker)
        except Exception:
            pass
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        snack = ft.SnackBar(content=ft.Text(message, size=13), bgcolor=ft.Colors.RED if is_error else ft.Colors.GREEN, duration=3000)
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _update_conversion(self, e):
        try:
            amount = float(self.amount_field.value or 0)
            curr = self.currency_dropdown.value
            rate_to_usd = float(currency.get_rate_to_usd(curr) or 1.0)
            usd_value = amount / rate_to_usd if rate_to_usd != 0 else 0
            self.zero_amount_notice.visible = (amount == 0)
            self.exchange_rate_text.value = f"سعر الصرف: 1 {curr} = {rate_to_usd:.4f} USD"
            display_curr = currency.get_display_currency()
            if display_curr != curr:
                rate_to_display = float(currency.get_rate_to_usd(display_curr) or 1.0)
                display_value = usd_value * rate_to_display if rate_to_display != 0 else 0
                self.converted_amount_text.value = f"≈ {display_value:.2f} {display_curr}"
            else:
                self.converted_amount_text.value = f"≈ {amount:.2f} {display_curr}"
        except:
            self.exchange_rate_text.value = ""
            self.converted_amount_text.value = ""
        self._page.update()

    def _save(self, e):
        company = self.company_field.value.strip()
        if not company:
            self._show_snackbar("اسم الشركة مطلوب")
            return
        try:
            amount = float(self.amount_field.value)
            if amount < 0:
                raise ValueError
        except:
            self._show_snackbar("المبلغ غير صالح. يُسمح بالصفر فقط لحفظ العملية بانتظار الدفع.")
            return

        type_val = 'incoming' if self.type_dropdown.value == translate('incoming') else 'outgoing'
        date = self.date_picker_field.value or ""
        notes = self.notes_field.value or ""
        currency_code = self.currency_dropdown.value
        payment_due_date = (self.payment_due_field.value or '').strip() if amount == 0 else None
        payment_note = (self.payment_note_field.value or '').strip() if amount == 0 else None

        user = UserSession.get_current()
        user_id = user['id'] if user else None

        repo = ExpenseRepository()
        try:
            if self.expense_id is not None:
                repo.update(self.expense_id, company, amount, type_val, date, notes, currency_code, user_id, payment_due_date, payment_note)
            else:
                repo.add(company, amount, type_val, date, notes, currency_code, user_id, payment_due_date, payment_note)
            self._close()
            if self.on_save:
                self.on_save(None)
            self._show_snackbar("📝 تم حفظ العملية بانتظار الدفع" if amount == 0 else "تم الحفظ بنجاح", is_error=False)
        except Exception as ex:
            self._show_snackbar(f"فشل الحفظ: {str(ex)}", True)
