from database.repositories.base_repo import BaseRepository

class SettingsRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self._cache = {}
    def get(self, key: str, default=None):
        if key in self._cache: return self._cache[key]
        value = self.db.get_setting(key, default)
        self._cache[key] = value
        return value
    def set(self, key: str, value: str):
        self.db.set_setting(key, value)
        self._cache.pop(key, None)
    def clear_cache(self): self._cache.clear()
    def get_currency_settings(self):
        return {'symbol': self.get('currency_symbol','$'), 'decimals': int(self.get('currency_decimals','2')), 'format': self.get('number_format','western')}
    def get_language(self): return self.get('language','ar')
    def get_theme(self): return self.get('theme','light')
