"""Key-value settings repository (the open-ended ``settings`` table).

Holds app preferences that don't warrant a dedicated table: theme mode,
accent choice, shop/technician names used on printed reports, and the
diagnosis plan (which categories are run by default).
"""

from __future__ import annotations

from hf_offline.core.database import Database

DEFAULTS: dict[str, str] = {
    "theme_mode": "system",
    "accent": "default",
    "shop_name": "ورشة إتش-إف",
    "technician_name": "المهندس",
}


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: str | None = None) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is not None:
            return str(row["value"])
        return DEFAULTS.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def set(self, key: str, value: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()

    def all(self) -> dict[str, str]:
        with self.db.connect() as conn:
            return {str(r["key"]): str(r["value"]) for r in conn.execute("SELECT key,value FROM settings").fetchall()}


__all__ = ["SettingsRepository", "DEFAULTS"]
