# -*- coding: utf-8 -*-
from auth.session import UserSession
from database.connection_rest import RestClient


def main():
    UserSession.logout()
    UserSession.login({'id': 1, 'username': 'admin', 'role': 'admin', '_auth_token': 'abc123'})
    client = RestClient('http://server:8000')
    headers = client._headers()
    assert headers.get('Authorization') == 'Bearer abc123', headers
    assert 'token' not in (UserSession.get_current() or {}), 'token leaked into current user dict'
    UserSession.logout()
    print('auth_token_smoke_test OK')


if __name__ == '__main__':
    main()
