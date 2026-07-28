# -*- coding: utf-8 -*-
import datetime
import flet as ft
from views.ui_kit import PRIMARY, PRIMARY_SOFT
from database import ExpenseRepository
from auth.session import UserSession
from i18n.translator import translate
from currency import currency
from views.flet_compat import close_control, ALIGN_CENTER
from views.dialogs.dialog_kit import dialog_title, dialog_body, cancel_button, save_button, show_snackbar, set_button_busy, normalize_text, parse_non_negative_amount
from services.ledger_operation_service import SERVICE_TYPES, OPERATION_LABELS, SERVICE_TO_OPERATION
from views.financial_date_field import FinancialDateField
from views.searchable_field import SearchableTextField
from services.form_suggestions_service import list_company_names, list_person_names

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

        self.company_field = SearchableTextField(
            label=translate('company_name'),
            value=self.predefined_company or (expense['company_name'] if expense else ""),
            disabled=is_disabled,
            width=dialog_width - 20,
            hint_text="ابحث باسم الشركة أو اكتب اسمًا جديدًا",
            suggestions_provider=list_company_names,
        )

        self.amount_field = ft.TextField(
            label=translate('amount'),
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(expense['amount_original'] if expense else ""),
            width=dialog_width - 20
        )

        existing_paid = float((expense or {}).get('paid_amount_original') or 0)
        self.initial_paid_field = ft.TextField(
            label="المدفوع الآن",
            keyboard_type=ft.KeyboardType.NUMBER,
            value="" if self.expense_id is not None else "0",
            width=160,
            disabled=self.expense_id is not None,
            hint_text=(f"مسجل سابقاً: {existing_paid:.2f}" if self.expense_id is not None else "دفعة أولى اختيارية"),
        )
        self.payment_method_dropdown = ft.Dropdown(
            label="طريقة الدفع",
            value="cash",
            options=[
                ft.dropdown.Option("cash", "نقدي"),
                ft.dropdown.Option("bank_transfer", "تحويل بنكي"),
                ft.dropdown.Option("card", "بطاقة"),
                ft.dropdown.Option("cheque", "شيك"),
                ft.dropdown.Option("other", "أخرى"),
            ],
            width=170,
            disabled=self.expense_id is not None,
        )
        self.initial_payer_dropdown = ft.Dropdown(
            label="الدافع الفعلي للدفعة الأولى",
            value="traveler" if (expense or {}).get("person_name") else "company",
            options=[],
            width=dialog_width - 20,
            disabled=self.expense_id is not None,
            filled=True,
            on_change=self._update_initial_payer_visibility,
        )
        self.initial_payer_name_field = ft.TextField(
            label="اسم الدافع الفعلي",
            width=dialog_width - 20,
            visible=False,
            disabled=self.expense_id is not None,
            hint_text="يظهر في كشف الشركة كدافع بالنيابة",
        )
        self.initial_payer_hint = ft.Text(
            "صاحب الحساب يبقى الشركة؛ اسم الدافع يوضح فقط من سلّم المبلغ.",
            size=11, color=ft.Colors.GREY_600, visible=self.expense_id is None,
        )

        self.currency_dropdown = ft.Dropdown(
            label=translate('currency'),
            value=expense.get('currency_original', 'SAR') if expense else currency.get_display_currency(),
            options=[ft.dropdown.Option(c) for c in ["USD","SAR","SYP","EUR","GBP","AED","QAR","KWD","OMR"]],
            width=120
        )

        current_type = "incoming" if (not expense or expense['type'] == 'incoming') else "outgoing"
        self.type_selector = ft.SegmentedButton(
            selected={current_type},
            allow_empty_selection=False,
            allow_multiple_selection=False,
            segments=[
                ft.Segment(
                    value="incoming",
                    icon=ft.Icon(ft.Icons.ARROW_DOWNWARD),
                    label=ft.Text("لنا"),
                ),
                ft.Segment(
                    value="outgoing",
                    icon=ft.Icon(ft.Icons.ARROW_UPWARD),
                    label=ft.Text("له"),
                ),
            ],
            width=dialog_width - 20,
        )
        # Name-only compatibility alias for extensions that inspect the dialog.
        # Selection is intentionally read from SegmentedButton.selected.
        self.type_dropdown = self.type_selector

        self.operation_date = FinancialDateField(
            self._page,
            label=translate('date'),
            value=expense['date'] if expense else None,
            width=dialog_width - 20,
        )
        # Backward-compatible aliases for older tests/plugins that inspect the dialog.
        self.date_picker_field = self.operation_date.field
        self.date_picker = self.operation_date.date_picker

        self.person_field = SearchableTextField(
            label="اسم الزبون / المسافر (اختياري)",
            value=(expense.get('person_name') if expense else "") or "",
            hint_text="ابحث باسم زبون سابق أو اكتب اسمًا جديدًا",
            width=dialog_width - 20,
            suggestions_provider=lambda: list_person_names(self.company_field.value),
        )

        current_service = (expense.get('service_type') if expense else "غير محدد") or "غير محدد"
        if current_service not in SERVICE_TYPES:
            current_service = "غير محدد"
        self.service_dropdown = ft.Dropdown(
            label="نوع الخدمة",
            value=current_service,
            options=[ft.dropdown.Option(s) for s in SERVICE_TYPES],
            width=dialog_width - 20
        )

        current_operation = (expense.get('operation_type') if expense else "") or SERVICE_TO_OPERATION.get(current_service, 'normal')
        self.operation_text = ft.Text(
            f"نوع العملية: {OPERATION_LABELS.get(current_operation, 'قيد عادي')}",
            size=12,
            color=ft.Colors.GREY_600,
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
                "أدخل إجمالي المطالبة والمدفوع الآن. سيحسب النظام المتبقي ويغلق التذكير تلقائياً عند اكتمال السداد.",
                size=12,
                color=ft.Colors.ORANGE_900,
            ),
            bgcolor=ft.Colors.ORANGE_50,
            border_radius=10,
            padding=10,
            visible=False,
        )

        self.exchange_rate_text = ft.Text("", size=12, color=ft.Colors.GREY_600, italic=True)
        self.converted_amount_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=PRIMARY)

        content = dialog_body(
            controls=[
                self.company_field,
                ft.Row([self.amount_field, self.currency_dropdown], spacing=10, wrap=True),
                ft.Row([self.initial_paid_field, self.payment_method_dropdown], spacing=10, wrap=True),
                self.initial_payer_dropdown,
                self.initial_payer_name_field,
                self.initial_payer_hint,
                ft.Text("اتجاه القيد", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                self.type_selector,
                ft.Text("لنا: مبلغ مستحق للشركة · له: مبلغ مستحق على الشركة", size=11, color=ft.Colors.GREY_600),
                self.operation_date,
                self.person_field,
                self.service_dropdown,
                self.operation_text,
                ft.Container(content=self.exchange_rate_text, margin=ft.Margin(top=5, bottom=5, left=0, right=0)),
                ft.Container(content=self.converted_amount_text, alignment=ALIGN_CENTER),
                self.zero_amount_notice,
                ft.Row([self.payment_due_field], spacing=10, wrap=True),
                self.payment_note_field,
                self.notes_field
            ],
            spacing=15,
            width=dialog_width - 10,
            height=dialog_height - 100
        )

        self._saving = False
        self.save_btn = save_button(translate('save'), self._save)
        self.title = dialog_title(
            "تعديل قيد" if self.expense_id is not None else "إضافة قيد",
            ft.Icons.EDIT_NOTE
        )
        self.content = content
        self.actions = [
            cancel_button(translate('cancel'), lambda e: self._close()),
            self.save_btn
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.inset_padding = 20
        self.shape = ft.RoundedRectangleBorder(radius=15)

        self.amount_field.on_change = self._update_conversion
        self.initial_paid_field.on_change = self._on_initial_paid_change
        self.currency_dropdown.on_change = self._update_conversion
        self.service_dropdown.on_change = self._update_operation_label
        self.type_selector.on_change = self._on_entry_type_change
        self.person_field.on_change = self._on_person_change
        self._update_operation_label(None)
        self._update_initial_payer_options()
        self._on_initial_paid_change(None)

    def _on_entry_type_change(self, e=None):
        self._update_initial_payer_options()
        self._update_conversion(e)

    def _on_person_change(self, e=None):
        self._update_initial_payer_options()

    def _on_initial_paid_change(self, e=None):
        self._update_conversion(e)
        try:
            paid = float(self.initial_paid_field.value or 0)
        except Exception:
            paid = 0.0
        visible = self.expense_id is None and paid > 0.005
        self.initial_payer_dropdown.visible = visible
        self.initial_payer_hint.visible = visible
        self.initial_payer_name_field.visible = visible and self.initial_payer_dropdown.value == "other"
        try:
            self._page.update()
        except Exception:
            pass

    def _update_initial_payer_options(self):
        if self.expense_id is not None:
            return
        entry_type = self._selected_entry_type() or "incoming"
        person = normalize_text(self.person_field.value)
        if entry_type == "outgoing":
            options = [
                ft.dropdown.Option("office", "المكتب"),
                ft.dropdown.Option("other", "دافع آخر"),
            ]
            allowed = {"office", "other"}
            default = "office"
        else:
            options = [ft.dropdown.Option("company", f"الشركة نفسها — {normalize_text(self.company_field.value) or 'الحساب'}")]
            if person:
                options.append(ft.dropdown.Option("traveler", f"المسافر / الزبون — {person}"))
            options.append(ft.dropdown.Option("other", "شخص آخر يدفع نيابة عن الشركة"))
            allowed = {"company", "other"} | ({"traveler"} if person else set())
            default = "traveler" if person else "company"
        self.initial_payer_dropdown.options = options
        if self.initial_payer_dropdown.value not in allowed:
            self.initial_payer_dropdown.value = default
        self._update_initial_payer_visibility()

    def _update_initial_payer_visibility(self, e=None):
        self.initial_payer_name_field.visible = (
            self.expense_id is None
            and self.initial_payer_dropdown.visible
            and self.initial_payer_dropdown.value == "other"
        )
        try:
            self._page.update()
        except Exception:
            pass

    def _resolved_initial_payer(self, entry_type, person_name):
        if entry_type == "outgoing":
            payer_type = str(self.initial_payer_dropdown.value or "office")
            if payer_type == "office":
                return "office", "المكتب"
        else:
            payer_type = str(self.initial_payer_dropdown.value or ("traveler" if person_name else "company"))
            if payer_type == "company":
                return "company", normalize_text(self.company_field.value)
            if payer_type == "traveler":
                if not person_name:
                    raise ValueError("حدد اسم المسافر الذي دفع")
                return "traveler", person_name
        name = normalize_text(self.initial_payer_name_field.value)
        if not name:
            raise ValueError("اسم الدافع الفعلي مطلوب")
        return "other", name

    def _update_operation_label(self, e):
        try:
            service = self.service_dropdown.value or "غير محدد"
            operation = SERVICE_TO_OPERATION.get(service, 'normal')
            self.operation_text.value = f"نوع العملية: {OPERATION_LABELS.get(operation, 'قيد عادي')}"
            self._page.update()
        except Exception:
            pass

    def _open_date_picker(self, e):
        self.operation_date._open_picker(e)

    def _on_date_change(self, e):
        self.operation_date._on_picker_change(e)

    def _close(self):
        # Close the owned DatePicker first, then the dialog itself.
        # Otherwise APK/Web builds may keep a stale overlay entry and the dialog
        # appears to remain open after Cancel/Save.
        try:
            self.operation_date.close()
        except Exception:
            pass
        close_control(self._page, self)

    def _show_snackbar(self, message, is_error=False):
        show_snackbar(self._page, message, is_error)

    def _update_conversion(self, e):
        try:
            amount = float(self.amount_field.value or 0)
            initial_paid = float(self.initial_paid_field.value or 0) if self.expense_id is None else float((self.expense or {}).get('paid_amount_original') or 0)
            curr = self.currency_dropdown.value
            rate_to_usd = float(currency.get_rate_to_usd(curr) or 1.0)
            usd_value = amount / rate_to_usd if rate_to_usd != 0 else 0
            self.zero_amount_notice.visible = amount > 0 and initial_paid < amount
            self.exchange_rate_text.value = f"سعر الصرف: 1 {curr} = {rate_to_usd:.4f} USD"
            display_curr = currency.get_display_currency()
            if display_curr != curr:
                rate_to_display = float(currency.get_rate_to_usd(display_curr) or 1.0)
                display_value = usd_value * rate_to_display if rate_to_display != 0 else 0
                self.converted_amount_text.value = f"الإجمالي ≈ {display_value:.2f} {display_curr} · المتبقي {max(amount-initial_paid,0):.2f} {curr}"
            else:
                self.converted_amount_text.value = f"الإجمالي {amount:.2f} {display_curr} · المدفوع {initial_paid:.2f} · المتبقي {max(amount-initial_paid,0):.2f}"
        except:
            self.exchange_rate_text.value = ""
            self.converted_amount_text.value = ""
        self._page.update()

    def _selected_entry_type(self):
        """Return the accounting direction selected by the user.

        SegmentedButton.selected is a set in the pinned Flet runtime. Keep the
        normalization defensive for tests or future runtimes that may expose a
        list/tuple/string instead.
        """
        selected = getattr(self.type_selector, "selected", None)
        if isinstance(selected, str):
            values = {selected}
        else:
            try:
                values = set(selected or [])
            except Exception:
                values = set()
        if "incoming" in values:
            return "incoming"
        if "outgoing" in values:
            return "outgoing"
        return None

    def _save(self, e):
        if self._saving:
            return
        company = normalize_text(self.company_field.value)
        if not company:
            self._show_snackbar("اسم الشركة مطلوب")
            return
        try:
            amount = parse_non_negative_amount(self.amount_field.value)
        except Exception as ex:
            self._show_snackbar(f"{str(ex)}. يُسمح بالصفر فقط لحفظ العملية بانتظار الدفع.", True)
            return

        type_val = self._selected_entry_type()
        if type_val not in {"incoming", "outgoing"}:
            self._show_snackbar("اختر اتجاه القيد: لنا أو له", True)
            return
        try:
            date = self.operation_date.require_value("تاريخ العملية")
        except Exception as ex:
            self._show_snackbar(str(ex), True)
            return
        notes = self.notes_field.value or ""
        try:
            initial_paid = 0.0 if self.expense_id is not None else parse_non_negative_amount(self.initial_paid_field.value or 0)
            existing_paid = float((self.expense or {}).get('paid_amount_original') or 0)
            effective_paid = existing_paid if self.expense_id is not None else initial_paid
            if effective_paid > amount + 0.005:
                raise ValueError("المدفوع لا يمكن أن يتجاوز إجمالي القيد")
        except Exception as ex:
            self._show_snackbar(str(ex), True)
            return
        currency_code = self.currency_dropdown.value
        person_name = normalize_text(self.person_field.value)
        service_type = self.service_dropdown.value or "غير محدد"
        operation_type = SERVICE_TO_OPERATION.get(service_type, 'normal')
        payment_due_date = (self.payment_due_field.value or '').strip() if amount > effective_paid + 0.005 else None
        payment_note = (self.payment_note_field.value or '').strip() if payment_due_date else None
        initial_payer_type = None
        initial_payer_name = ""
        if self.expense_id is None and initial_paid > 0.005:
            try:
                initial_payer_type, initial_payer_name = self._resolved_initial_payer(type_val, person_name)
            except Exception as ex:
                self._show_snackbar(str(ex), True)
                return

        user = UserSession.get_current()
        user_id = user['id'] if user else None

        repo = ExpenseRepository()
        self._saving = True
        set_button_busy(self.save_btn, True, translate('save'))
        try:
            self._page.update()
        except Exception:
            pass
        try:
            if self.expense_id is not None:
                repo.update(self.expense_id, company, amount, type_val, date, notes, currency_code, user_id, payment_due_date, payment_note, person_name=person_name, service_type=service_type, operation_type=operation_type)
            else:
                repo.add(
                    company, amount, type_val, date, notes, currency_code, user_id,
                    payment_due_date, payment_note, person_name=person_name,
                    service_type=service_type, operation_type=operation_type,
                    initial_paid_amount=initial_paid,
                    payment_method=self.payment_method_dropdown.value or "cash",
                    initial_payer_type=initial_payer_type,
                    initial_payer_name=initial_payer_name,
                )
            self.operation_date.remember()
            self._close()
            if self.on_save:
                self.on_save(None)
            remaining = max(amount - effective_paid, 0)
            self._show_snackbar("تم الحفظ · يوجد مبلغ متبقٍ" if remaining > 0.005 else "تم الحفظ والسداد مكتمل", is_error=False)
        except Exception as ex:
            self._show_snackbar(f"فشل الحفظ: {str(ex)}", True)
        finally:
            self._saving = False
            set_button_busy(self.save_btn, False, translate('save'))
            try:
                self._page.update()
            except Exception:
                pass
