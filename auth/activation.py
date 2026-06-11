import os, json, hashlib, base64, platform, getpass, threading, time, requests
from typing import Tuple, Optional, Callable

SERVER_URL = 'https://license.manhal-almasriiii199119.workers.dev/activate'
LICENSE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'license.dat')

def get_device_id() -> str:
    try: username = getpass.getuser()
    except: username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
    info = platform.node() + platform.processor() + username + platform.system() + platform.machine()
    return hashlib.sha256(info.encode()).hexdigest()

def _derive_key(device_id: str, salt: bytes = b'hawaa_salt_2025') -> bytes:
    return hashlib.pbkdf2_hmac('sha256', device_id.encode(), salt, 100000, dklen=32)

def _xor_encrypt_decrypt(data: bytes, key: bytes) -> bytes:
    return bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])

def _encrypt_license(data: dict, device_id: str) -> str:
    key = _derive_key(device_id)
    plaintext = json.dumps(data).encode()
    encrypted = _xor_encrypt_decrypt(plaintext, key)
    return base64.b64encode(encrypted).decode()

def _decrypt_license(encrypted: str, device_id: str) -> Optional[dict]:
    try:
        key = _derive_key(device_id)
        enc_bytes = base64.b64decode(encrypted)
        plaintext = _xor_encrypt_decrypt(enc_bytes, key)
        return json.loads(plaintext.decode())
    except: return None

def activate(license_key: str) -> Tuple[bool, str]:
    device_id = get_device_id()
    try:
        resp = requests.post(SERVER_URL, json={'licenseCode': license_key, 'fingerprint': device_id}, timeout=15)
        if resp.status_code != 200: return False, resp.text or "فشل التفعيل"
        result = resp.json()
        data = {'key': license_key, 'device': device_id, 'expiration': result.get('expirationDate'), 'activated_at': __import__('datetime').datetime.now().isoformat()}
        with open(LICENSE_FILE, 'w') as f: f.write(_encrypt_license(data, device_id))
        return True, ""
    except Exception as e: return False, str(e)

def check_activation() -> Tuple[bool, str]:
    if not os.path.exists(LICENSE_FILE): return False, "لم يتم التفعيل"
    try:
        with open(LICENSE_FILE, 'r') as f: encrypted = f.read().strip()
        device_id = get_device_id()
        data = _decrypt_license(encrypted, device_id)
        if not data or data.get('device') != device_id: return False, "ترخيص غير صالح"
        return True, ""
    except Exception as e: return False, str(e)

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
