# -*- coding: utf-8 -*-
from database.repositories.settings_repo import SettingsRepository
from database.connection import DatabaseConnection
import datetime

class CurrencyManager:
    _instance = None
    SUPPORTED_CURRENCIES = ['USD','SAR','SYP','EUR','GBP','AED','QAR','KWD','OMR']
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._settings_repo = SettingsRepository()
        return cls._instance

    def invalidate_cache(self):
        try:
            self._settings_repo.clear_cache()
        except Exception:
            pass

    def _normalize_currency(self, code: str | None, default: str = 'USD') -> str:
        code = (code or default).upper().strip()
        return code if code in self.SUPPORTED_CURRENCIES else default

    def get_base_currency(self) -> str:
        return self._normalize_currency(self._settings_repo.get('base_currency', 'USD'), 'USD')

    def get_display_currency(self) -> str:
        return self._normalize_currency(self._settings_repo.get('display_currency', 'USD'), 'USD')

    def set_base_currency(self, currency_code: str):
        self._settings_repo.set('base_currency', self._normalize_currency(currency_code, 'USD'))
        self.invalidate_cache()

    def set_display_currency(self, currency_code: str):
        self._settings_repo.set('display_currency', self._normalize_currency(currency_code, 'USD'))
        self.invalidate_cache()

    def save_runtime_settings(self, base_currency=None, display_currency=None, decimals=None, number_format=None, abbreviate_numbers=None):
        if base_currency is not None:
            self._settings_repo.set('base_currency', self._normalize_currency(base_currency, 'USD'))
        if display_currency is not None:
            self._settings_repo.set('display_currency', self._normalize_currency(display_currency, 'USD'))
        if decimals is not None:
            self._settings_repo.set('currency_decimals', str(int(decimals)))
        if number_format is not None:
            self._settings_repo.set('number_format', str(number_format))
        if abbreviate_numbers is not None:
            self._settings_repo.set('abbreviate_numbers', 'true' if bool(abbreviate_numbers) else 'false')
        self.invalidate_cache()

    def get_currency_symbol(self, currency_code: str = None) -> str:
        if currency_code is None:
            currency_code = self.get_display_currency()
        symbols = {'USD':'$','SAR':'﷼','SYP':'ل.س','EUR':'€','GBP':'£','AED':'د.إ','QAR':'ر.ق','KWD':'د.ك','OMR':'ر.ع.'}
        return symbols.get(currency_code, currency_code)

    def get_currency_decimals(self) -> int:
        try:
            return int(self._settings_repo.get('currency_decimals', '2'))
        except Exception:
            return 2

    def get_number_format(self) -> str:
        return self._settings_repo.get('number_format', 'western')

    def abbreviate_numbers(self) -> bool:
        # Android has limited horizontal space.  The mobile default is therefore
        # enabled unless the user explicitly turns it off in settings.
        return self._settings_repo.get('abbreviate_numbers', 'true').lower() == 'true'

    def get_rate_to_usd(self, currency_code: str) -> float:
        if currency_code == 'USD':
            return 1.0
        db = DatabaseConnection()
        if db.is_remote():
            rates = db.get_all_currencies()
            for r in rates:
                if r['currency_code'] == currency_code:
                    return r['rate_to_usd']
            return 1.0
        else:
            conn = db.get_connection()
            cursor = conn.execute("SELECT rate_to_usd FROM exchange_rates WHERE currency_code=?", (currency_code,))
            row = cursor.fetchone()
            return row[0] if row else 1.0

    def update_rate(self, currency_code: str, rate_to_usd: float):
        db = DatabaseConnection()
        db.update_exchange_rate(currency_code, rate_to_usd)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return amount
        rate_from = self.get_rate_to_usd(from_currency)
        rate_to = self.get_rate_to_usd(to_currency)
        if rate_from == 0 or rate_to == 0:
            return amount
        amount_usd = amount / rate_from
        return amount_usd * rate_to

    def _compact_number(self, num: float, decimals: int = 1) -> str:
        """Compact value for constrained mobile cards, preserving the sign."""
        try:
            value = float(num or 0)
        except Exception:
            value = 0.0
        sign = '-' if value < 0 else ''
        value = abs(value)
        units = [
            (1_000_000_000_000, 'T'),
            (1_000_000_000, 'B'),
            (1_000_000, 'M'),
            (1_000, 'K'),
        ]
        for threshold, suffix in units:
            if value >= threshold:
                scaled = value / threshold
                # 200K is cleaner than 200.0K; 1.6M keeps one useful decimal.
                if scaled >= 100 or abs(scaled - round(scaled)) < 1e-9:
                    body = f"{scaled:.0f}"
                else:
                    body = f"{scaled:.{decimals}f}".rstrip('0').rstrip('.')
                return f"{sign}{body}{suffix}"
        if value == 0:
            return "0"
        if value >= 100:
            return f"{sign}{value:.0f}"
        return f"{sign}{value:.2f}".rstrip('0').rstrip('.')

    def _apply_number_format(self, formatted: str) -> str:
        if self.get_number_format() == 'arabic':
            trans = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')
            return formatted.translate(trans)
        return formatted

    def format_amount(self, amount: float, currency_code: str = None, decimals: int = None, compact: bool | None = None) -> str:
        """Format money consistently for all Android views.

        compact=None follows the user setting "اختصار الأعداد الكبيرة".
        compact=True is for constrained mobile cards where full numbers would wrap.
        Reports/CSV can pass compact=False to keep full precision.
        """
        if currency_code is None:
            currency_code = self.get_display_currency()
        if decimals is None:
            decimals = self.get_currency_decimals()
        symbol = self.get_currency_symbol(currency_code)
        try:
            value = float(amount or 0)
        except Exception:
            value = 0.0
        use_compact = self.abbreviate_numbers() if compact is None else bool(compact)
        if use_compact and abs(value) >= 1000:
            formatted = self._compact_number(value)
        else:
            formatted = f"{value:,.{decimals}f}"
        formatted = self._apply_number_format(formatted)
        return f"{formatted} {symbol}"

    def format_amount_full(self, amount: float, currency_code: str = None, decimals: int = None) -> str:
        return self.format_amount(amount, currency_code, decimals, compact=False)

    def format_amount_compact(self, amount: float, currency_code: str = None) -> str:
        return self.format_amount(amount, currency_code, compact=True)

    def get_all_currencies(self) -> list:
        db = DatabaseConnection()
        return db.get_all_currencies()

currency = CurrencyManager()
