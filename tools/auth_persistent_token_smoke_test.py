# -*- coding: utf-8 -*-
import os, tempfile
os.environ['HAWAA_DATA_DIR'] = tempfile.mkdtemp(prefix='hawaa_auth_token_')
from database.migrations import ensure_db
ensure_db()
from database.connection import _set_local_setting_direct, DatabaseConnection
from database.connection_rest import RestClient
from auth.session import UserSession

# A token saved by login must be used by a fresh client instance.
_set_local_setting_direct('auth/network_token', 'persisted-token')
client = RestClient('http://server:8000')
assert client._headers().get('Authorization') == 'Bearer persisted-token'

# An in-memory session token takes precedence and is also persisted.
UserSession.login({'id': 1, 'username': 'admin', 'role': 'admin', '_auth_token': 'session-token'})
client2 = RestClient('http://server:8000')
assert client2._headers().get('Authorization') == 'Bearer session-token'

# DatabaseConnection-created RestClient must also receive the token.
_set_local_setting_direct('network/mode', 'client')
_set_local_setting_direct('network/server_url', 'http://server:8000')
db = DatabaseConnection()
db.refresh_mode()
assert db.get_rest_client()._headers().get('Authorization') == 'Bearer session-token'

print('auth_persistent_token_smoke_test OK')
