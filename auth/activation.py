# -*- coding: utf-8 -*-
import os, json, hashlib, base64, platform, getpass, threading, time, requests, datetime
from typing import Tuple, Optional, Callable

SERVER_URL = 'https://license.manhal-almasriiii199119.workers.dev/activate'


def _license_dir() -> str:
    base = os.environ.get('FLET_APP_STORAGE_DATA') or os.environ.get('HAWAA_DATA_DIR') or os.path.expanduser('~/.hawaa')
    path = os.path.join(base, 'config')
    os.makedirs(path, exist_ok=True)
    return path


def get_license_file_path() -> str:
    return os.path.join(_license_dir(), 'license.dat')


def _legacy_license_file() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'license.dat')


LICENSE_FILE = get_license_file_path()


def _migrate_legacy_license() -> None:
    target = get_license_file_path()
    legacy = _legacy_license_file()
    if os.path.exists(target) or not os.path.exists(legacy):
        return
    try:
        with open(legacy, 'r', encoding='utf-8') as src, open(target, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    except Exception:
        pass


def get_device_id() -> str:
    try: username = getpass.getuser()
    except Exception: username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
    info = platform.node() + platform.processor() + username + platform.system() + platform.machine()
    return hashlib.sha256(info.encode()).hexdigest()


def _derive_key(device_id: str, salt: bytes = b'hawaa_salt_2025') -> bytes:
    return hashlib.pbkdf2_hmac('sha256', device_id.encode(), salt, 100000, dklen=32)


def _xor_encrypt_decrypt(data: bytes, key: bytes) -> bytes:
    return bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])


def _encrypt_license(data: dict, device_id: str) -> str:
    key = _derive_key(device_id)
    plaintext = json.dumps(data, ensure_ascii=False).encode()
    encrypted = _xor_encrypt_decrypt(plaintext, key)
    return base64.b64encode(encrypted).decode()


def _decrypt_license(encrypted: str, device_id: str) -> Optional[dict]:
    try:
        key = _derive_key(device_id)
        enc_bytes = base64.b64decode(encrypted)
        plaintext = _xor_encrypt_decrypt(enc_bytes, key)
        return json.loads(plaintext.decode())
    except Exception:
        return None


def _parse_expiration(value):
    if value in (None, ''):
        return 'unknown', None
    text = str(value).strip()
    lifetime = {'lifetime', 'unlimited', 'permanent', 'never', 'غير محدود', 'مدى الحياة', 'لا ينتهي'}
    if text.lower() in lifetime or text in lifetime:
        return 'lifetime', None
    try:
        num = float(text)
        if num > 10_000_000_000:  # milliseconds
            num = num / 1000
        return 'date', datetime.datetime.fromtimestamp(num, datetime.timezone.utc).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%d/%m/%Y', '%d.%m.%Y'):
        try:
            return 'date', datetime.datetime.strptime(text, fmt)
        except Exception:
            pass
    try:
        normalized = text.replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return 'date', dt
    except Exception:
        return 'invalid', None


def activate(license_key: str) -> Tuple[bool, str]:
    device_id = get_device_id()
    try:
        resp = requests.post(SERVER_URL, json={'licenseCode': license_key, 'fingerprint': device_id}, timeout=15)
        if resp.status_code != 200:
            return False, resp.text or "فشل التفعيل"
        result = resp.json()
        expiration = result.get('expirationDate') or result.get('expiration') or result.get('expiresAt')
        data = {'key': license_key, 'device': device_id, 'expiration': expiration, 'activated_at': datetime.datetime.now().isoformat()}
        with open(get_license_file_path(), 'w', encoding='utf-8') as f:
            f.write(_encrypt_license(data, device_id))
        return True, ""
    except Exception as e:
        return False, str(e)


def check_activation() -> Tuple[bool, str]:
    _migrate_legacy_license()
    path = get_license_file_path()
    if not os.path.exists(path):
        return False, "لم يتم التفعيل"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            encrypted = f.read().strip()
        device_id = get_device_id()
        data = _decrypt_license(encrypted, device_id)
        if not data or data.get('device') != device_id:
            return False, "ترخيص غير صالح"
        kind, parsed = _parse_expiration(data.get('expiration'))
        if kind == 'invalid':
            return False, "تاريخ انتهاء الترخيص غير مفهوم"
        if kind == 'date' and parsed and datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) > parsed:
            return False, "انتهت صلاحية الترخيص"
        return True, ""
    except Exception as e:
        return False, str(e)


_license_checker_thread = None
_license_checker_stop = False
_on_invalid = None


def start_license_checker(interval_hours: int = 24, on_invalid: Callable = None):
    global _license_checker_thread, _license_checker_stop, _on_invalid
    _license_checker_stop = False
    _on_invalid = on_invalid
    def loop():
        while not _license_checker_stop:
            time.sleep(interval_hours * 3600)
            valid, _ = check_activation()
            if not valid and _on_invalid: _on_invalid()
    _license_checker_thread = threading.Thread(target=loop, daemon=True)
    _license_checker_thread.start()


def stop_license_checker():
    global _license_checker_stop
    _license_checker_stop = True


def get_license_details() -> dict:
    """Return safe license metadata for UI screens."""
    _migrate_legacy_license()
    device_id = get_device_id()
    path = get_license_file_path()
    valid, message = check_activation()
    details = {
        'activated': valid,
        'message': 'الترخيص مفعل' if valid else message,
        'device_id': device_id,
        'expiration': '',
        'expiration_kind': '',
        'activated_at': '',
        'key_preview': '',
        'license_file': path,
    }
    if not os.path.exists(path):
        return details
    try:
        with open(path, 'r', encoding='utf-8') as f:
            encrypted = f.read().strip()
        data = _decrypt_license(encrypted, device_id)
        if not data or data.get('device') != device_id:
            return details
        key = str(data.get('key', ''))
        kind, parsed = _parse_expiration(data.get('expiration'))
        exp = 'غير محدود' if kind == 'lifetime' else (parsed.isoformat() if parsed else str(data.get('expiration') or ''))
        details.update({
            'expiration': exp,
            'expiration_kind': kind,
            'activated_at': str(data.get('activated_at') or ''),
            'key_preview': ('****-' + key[-4:]) if len(key) >= 4 else '****',
        })
        return details
    except Exception as exc:
        details['message'] = str(exc)
        return details
