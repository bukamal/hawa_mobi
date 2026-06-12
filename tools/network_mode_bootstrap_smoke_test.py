# -*- coding: utf-8 -*-
import os, tempfile
os.environ['HAWAA_DATA_DIR'] = tempfile.mkdtemp(prefix='hawaa_network_bootstrap_')
from database.migrations import ensure_db
ensure_db()
from database.connection import _set_local_setting_direct, DatabaseConnection

_set_local_setting_direct('network/mode', 'client')
_set_local_setting_direct('network/server_url', 'http://192.168.2.102:8000')
DatabaseConnection._instance = None
DatabaseConnection._local_conn = None

db = DatabaseConnection()
assert db.is_remote(), f'expected client mode, got {db.mode}'
assert db.get_rest_client() is not None, 'missing rest client in client mode'
assert db.server_url == 'http://192.168.2.102:8000', db.server_url
print('network_mode_bootstrap_smoke_test OK')
