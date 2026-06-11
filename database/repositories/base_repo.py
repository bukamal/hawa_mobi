# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from database.connection import DatabaseConnection
from database.data_sources import get_data_source


class BaseRepository:
    """Base repository with a mode-aware data source.

    Repositories can still access ``self.db`` for compatibility, but new code
    should prefer ``self.data`` so UI/business logic no longer branches on
    SQLite-vs-REST details.
    """

    def __init__(self):
        self.db = DatabaseConnection()
        self.data = get_data_source(self.db)

    def refresh_data_source(self):
        self.db.refresh_mode()
        self.data = get_data_source(self.db)

    def _execute(self, sql: str, params=(), audit_data=None):
        return self.data.execute(sql, params, audit_data)

    def _fetch_one(self, sql: str, params=()) -> Optional[Dict]:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params=()) -> List[Dict]:
        cur = self._execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def _commit(self):
        self.data.commit()

    def _rollback(self):
        self.data.rollback()

    def begin(self):
        self.data.begin()
