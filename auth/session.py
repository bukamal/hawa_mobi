from typing import Optional, Dict
class UserSession:
    _current_user: Optional[Dict] = None
    @classmethod
    def login(cls, user: Dict): cls._current_user = user
    @classmethod
    def logout(cls): cls._current_user = None
    @classmethod
    def get_current(cls) -> Optional[Dict]: return cls._current_user
    @classmethod
    def is_authenticated(cls) -> bool: return cls._current_user is not None
    @classmethod
    def is_admin(cls) -> bool: return cls._current_user and cls._current_user.get('role') == 'admin'
    @classmethod
    def force_password_change(cls) -> bool: return cls._current_user and cls._current_user.get('force_password_change', 0) == 1
