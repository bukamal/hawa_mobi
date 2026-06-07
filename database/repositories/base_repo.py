from database.connection import DatabaseConnection
from typing import List, Dict, Optional

class BaseRepository:
    def __init__(self): self.db = DatabaseConnection()
    def _execute(self, sql: str, params=(), audit_data=None): return self.db.execute(sql, params, audit_data)
    def _fetch_one(self, sql: str, params=()) -> Optional[Dict]:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    def _fetch_all(self, sql: str, params=()) -> List[Dict]:
        cur = self._execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    def _commit(self): self.db.commit()
    def _rollback(self): self.db.rollback()
    def begin(self): self.db.begin()
