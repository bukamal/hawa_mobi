# -*- coding: utf-8 -*-
import os, shutil, tempfile
from auth.session import UserSession
from database.connection_rest import RestClient


def main():
    tmp = tempfile.mkdtemp(prefix='hawaa_auth_header_')
    old = os.environ.get('HAWAA_DATA_DIR')
    os.environ['HAWAA_DATA_DIR'] = tmp
    try:
        UserSession.logout()
        UserSession.login({'id': 1, 'username': 'admin', 'role': 'admin', '_auth_token': 'abc123'})
        client = RestClient('http://server:8000')
        headers = client._headers()
        assert headers.get('Authorization') == 'Bearer abc123', headers
        assert 'token' not in (UserSession.get_current() or {}), 'token leaked into current user dict'
        UserSession.logout()
        print('auth_token_smoke_test OK')
    finally:
        if old is None:
            os.environ.pop('HAWAA_DATA_DIR', None)
        else:
            os.environ['HAWAA_DATA_DIR'] = old
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
