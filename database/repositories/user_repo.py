from database.repositories.base_repo import BaseRepository
from auth.password import hash_password, upgraded_hash, verify_password
from auth.session import UserSession
import datetime
from typing import List, Dict, Optional


class UserRepository(BaseRepository):
    def get_all(self) -> List[Dict]:
        if self.data.is_remote():
            return self.data.get_users()
        return self._fetch_all(
            "SELECT id, username, full_name, role, created_at, last_login, force_password_change FROM users ORDER BY id"
        )

    def get_by_id(self, user_id: int) -> Optional[Dict]:
        if self.data.is_remote():
            users = self.get_all()
            for u in users:
                if u["id"] == user_id:
                    return u
            return None
        return self._fetch_one("SELECT * FROM users WHERE id=?", (user_id,))

    def get_by_username(self, username: str) -> Optional[Dict]:
        if self.data.is_remote():
            users = self.get_all()
            for u in users:
                if u["username"] == username:
                    return u
            return None
        return self._fetch_one("SELECT * FROM users WHERE username=?", (username,))

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        if self.data.is_remote():
            raise NotImplementedError("Use RestClient.login() for remote")
        user = self.get_by_username(username)
        if user and verify_password(password, user["password_hash"], user["salt"]):
            now = datetime.datetime.now().isoformat()
            upgraded = upgraded_hash(password, user["password_hash"], user["salt"])
            if upgraded:
                new_hash, new_salt = upgraded
                self._execute(
                    "UPDATE users SET password_hash=?, salt=?, last_login=? WHERE id=?",
                    (new_hash, new_salt, now, user["id"]),
                )
                user["password_hash"] = new_hash
                user["salt"] = new_salt
            else:
                self._execute(
                    "UPDATE users SET last_login=? WHERE id=?", (now, user["id"])
                )
            self._commit()
            return user
        return None

    def create(self, username: str, password: str, full_name: str, role: str) -> int:
        if self.data.is_remote():
            data = {
                "username": username,
                "password": password,
                "full_name": full_name,
                "role": role,
            }
            return self.data.add_user(data)
        pwd_hash, salt = hash_password(password)
        now = datetime.datetime.now().isoformat()
        conn = self.db.get_connection()
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            (username, pwd_hash, salt, full_name, role, now),
        )
        conn.commit()
        uid = cur.lastrowid
        curr = UserSession.get_current()
        self.db._log_audit_local(
            curr["id"] if curr else None,
            curr["username"] if curr else "",
            "إضافة مستخدم",
            "users",
            uid,
            f"المستخدم: {username}",
        )
        return uid

    def update(self, user_id: int, full_name: str, role: str):
        if self.data.is_remote():
            self.db.get_rest_client().update_user(
                user_id, {"full_name": full_name, "role": role}
            )
            return
        conn = self.db.get_connection()
        conn.execute(
            "UPDATE users SET full_name=?, role=? WHERE id=?",
            (full_name, role, user_id),
        )
        conn.commit()
        curr = UserSession.get_current()
        self.db._log_audit_local(
            curr["id"] if curr else None,
            curr["username"] if curr else "",
            "تعديل مستخدم",
            "users",
            user_id,
            f"الاسم: {full_name}, صلاحية: {role}",
        )

    def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> bool:
        if self.data.is_remote():
            try:
                self.db.get_rest_client().change_password(old_password, new_password)
                return True
            except Exception:
                return False
        user = self.get_by_id(user_id)
        if not user or not verify_password(
            old_password, user["password_hash"], user["salt"]
        ):
            return False
        new_hash, new_salt = hash_password(new_password)
        conn = self.db.get_connection()
        conn.execute(
            "UPDATE users SET password_hash=?, salt=?, force_password_change=0 WHERE id=?",
            (new_hash, new_salt, user_id),
        )
        conn.commit()
        curr = UserSession.get_current()
        self.db._log_audit_local(
            curr["id"] if curr else None,
            curr["username"] if curr else "",
            "تغيير كلمة المرور",
            "users",
            user_id,
            "",
        )
        return True

    def delete(self, user_id: int) -> bool:
        if user_id == 1:
            return False
        if self.data.is_remote():
            try:
                self.db.get_rest_client().delete_user(user_id)
                return True
            except Exception:
                return False
        user = self.get_by_id(user_id)
        conn = self.db.get_connection()
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        curr = UserSession.get_current()
        self.db._log_audit_local(
            curr["id"] if curr else None,
            curr["username"] if curr else "",
            "حذف مستخدم",
            "users",
            user_id,
            f"المستخدم: {user['username']}",
        )
        return True

    def set_force_password_change(self, user_id: int, force: bool):
        if self.data.is_remote():
            return
        val = 1 if force else 0
        self._execute(
            "UPDATE users SET force_password_change=? WHERE id=?", (val, user_id)
        )
        self._commit()
