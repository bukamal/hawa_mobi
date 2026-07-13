from database.repositories.base_repo import BaseRepository


class SettingsRepository(BaseRepository):
    """Repository for app settings with process-wide cache invalidation.

    Several runtime services keep their own SettingsRepository instance (for
    example the currency manager).  A per-instance cache made settings look
    stale until Android restarted the process.  The cache is now shared and any
    write invalidates the relevant key for every repository instance.
    """

    _shared_cache = {}

    def __init__(self):
        super().__init__()
        self._cache = SettingsRepository._shared_cache

    @classmethod
    def invalidate_cache(cls, key: str | None = None):
        if key is None:
            cls._shared_cache.clear()
        else:
            cls._shared_cache.pop(key, None)

    def get(self, key: str, default=None):
        if key in self._cache:
            return self._cache[key]
        value = self.data.get_setting(key, default)
        self._cache[key] = value
        return value

    def set(self, key: str, value: str):
        self.data.set_setting(key, value)
        SettingsRepository.invalidate_cache(key)

    def clear_cache(self):
        SettingsRepository.invalidate_cache()

    def get_currency_settings(self):
        return {
            "symbol": self.get("currency_symbol", "$"),
            "decimals": int(self.get("currency_decimals", "2")),
            "format": self.get("number_format", "western"),
        }

    def get_language(self):
        return self.get("language", "ar")

    def get_theme(self):
        return self.get("theme", "light")
