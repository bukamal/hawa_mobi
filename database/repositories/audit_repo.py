from database.repositories.base_repo import BaseRepository
import datetime
from typing import List, Dict, Optional


class AuditRepository(BaseRepository):
    def log(
        self,
        user_id: Optional[int],
        username: str,
        action: str,
        table_name: str,
        record_id: int,
        details: str,
        ip: str = "",
    ):
        if self.data.is_remote():
            return
        now = datetime.datetime.now().isoformat()
        self._execute(
            "INSERT INTO audit_log (user_id, username, action, table_name, record_id, details, ip_address, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, username, action, table_name, record_id, details, ip, now),
        )
        self._commit()

    def get_all(
        self,
        limit: int = 1000,
        user_id: int = None,
        action: str = None,
        table_name: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict]:
        if self.data.is_remote():
            logs = self.db.get_rest_client().get_audit_log()
            filtered = logs[:limit]
            if user_id:
                filtered = [log for log in filtered if log.get("user_id") == user_id]
            if action and action != "الكل":
                filtered = [log for log in filtered if log.get("action") == action]
            if table_name and table_name != "الكل":
                filtered = [
                    log for log in filtered if log.get("table_name") == table_name
                ]
            if start_date:
                filtered = [
                    log
                    for log in filtered
                    if log.get("timestamp", "")[:10] >= start_date
                ]
            if end_date:
                filtered = [
                    log for log in filtered if log.get("timestamp", "")[:10] <= end_date
                ]
            return filtered
        sql = "SELECT id, user_id, username, action, table_name, record_id, details, ip_address, timestamp FROM audit_log WHERE 1=1"
        params = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if action and action != "الكل":
            sql += " AND action = ?"
            params.append(action)
        if table_name and table_name != "الكل":
            sql += " AND table_name = ?"
            params.append(table_name)
        if start_date:
            sql += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND timestamp <= ?"
            params.append(end_date + " 23:59:59")
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._fetch_all(sql, tuple(params))

    def get_stats(self) -> Dict:
        if self.data.is_remote():
            logs = self.db.get_rest_client().get_audit_log()
            from collections import defaultdict

            by_user = defaultdict(int)
            by_action = defaultdict(int)
            by_table = defaultdict(int)
            daily = defaultdict(int)
            for log in logs:
                by_user[log.get("username", "unknown")] += 1
                by_action[log.get("action", "unknown")] += 1
                by_table[log.get("table_name", "unknown")] += 1
                if log.get("timestamp"):
                    daily[log["timestamp"][:10]] += 1
            today = datetime.datetime.now().date()
            return {
                "by_user": [
                    {"username": k, "count": v}
                    for k, v in sorted(by_user.items(), key=lambda x: -x[1])[:10]
                ],
                "by_action": [{"action": k, "count": v} for k, v in by_action.items()],
                "by_table": [
                    {"table_name": k, "count": v} for k, v in by_table.items()
                ],
                "daily": [
                    {"day": d, "count": c}
                    for d, c in sorted(daily.items())
                    if d >= (today - datetime.timedelta(days=30)).isoformat()
                ],
            }
        rows = self._fetch_all(
            "SELECT username, COUNT(*) as count FROM audit_log GROUP BY username ORDER BY count DESC LIMIT 10"
        )
        stats = {"by_user": rows}
        rows = self._fetch_all(
            "SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY count DESC"
        )
        stats["by_action"] = rows
        rows = self._fetch_all(
            "SELECT table_name, COUNT(*) as count FROM audit_log GROUP BY table_name ORDER BY count DESC"
        )
        stats["by_table"] = rows
        rows = self._fetch_all(
            "SELECT DATE(timestamp) as day, COUNT(*) as count FROM audit_log WHERE timestamp >= date('now','-30 days') GROUP BY DATE(timestamp) ORDER BY day"
        )
        stats["daily"] = rows
        return stats

    def delete_old_logs(self, days: int = 90):
        if self.data.is_remote():
            self.db.get_rest_client().delete_old_audit_logs(days)
        else:
            cutoff = (
                datetime.datetime.now() - datetime.timedelta(days=days)
            ).isoformat()
            self._execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
            self._commit()

    def export_all(self) -> List[Dict]:
        if self.data.is_remote():
            return self.db.get_rest_client().get_audit_log()
        return self._fetch_all("SELECT * FROM audit_log ORDER BY id DESC")
