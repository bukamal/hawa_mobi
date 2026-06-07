# -*- coding: utf-8 -*-
from database.repositories.settings_repo import SettingsRepository
from database.connection import DatabaseConnection
import datetime

class CurrencyManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._settings_repo = SettingsRepository()
        return cls._instance

    def get_base_currency(self) -> str:
        return self._settings_repo.get('base_currency', 'USD')
    def get_display_currency(self) -> str:
        return self._settings_repo.get('display_currency', 'USD')
    def get_currency_symbol(self, currency_code: str = None) -> str:
        if currency_code is None:
            currency_code = self.get_display_currency()
        symbols = {'USD':'$','SAR':'﷼','SYP':'ل.س','EUR':'€','GBP':'£','AED':'د.إ','QAR':'ر.ق','KWD':'د.ك','OMR':'ر.ع.'}
        return symbols.get(currency_code, currency_code)
    def get_currency_decimals(self) -> int:
        return int(self._settings_repo.get('currency_decimals', '2'))
    def get_number_format(self) -> str:
        return self._settings_repo.get('number_format', 'western')
    def abbreviate_numbers(self) -> bool:
        return self._settings_repo.get('abbreviate_numbers', 'false').lower() == 'true'
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
    def _abbreviate_number(self, num: float) -> str:
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        else:
            return f"{num:.2f}".rstrip('0').rstrip('.') if '.' in f"{num:.2f}" else f"{num:.0f}"
    def format_amount(self, amount: float, currency_code: str = None, decimals: int = None) -> str:
        if currency_code is None:
            currency_code = self.get_display_currency()
        if decimals is None:
            decimals = self.get_currency_decimals()
        symbol = self.get_currency_symbol(currency_code)
        fmt = self.get_number_format()
        abbrev = self.abbreviate_numbers()
        if abbrev and abs(amount) >= 1000:
            formatted = self._abbreviate_number(amount)
        else:
            formatted = f"{amount:,.{decimals}f}"
        if fmt == 'arabic':
            formatted = formatted.replace('0','٠').replace('1','١').replace('2','٢').replace('3','٣').replace('4','٤')\
                                 .replace('5','٥').replace('6','٦').replace('7','٧').replace('8','٨').replace('9','٩')
        return f"{formatted} {symbol}"
    def get_all_currencies(self) -> list:
        db = DatabaseConnection()
        return db.get_all_currencies()

currency = CurrencyManager()
