# -*- coding: utf-8 -*-
import os
import json
from pathlib import Path
from database.connection import get_local_db_path

_CONFIG_FILE = None

_DEFAULT_COMPANY_INFO = {
    'name': 'هوى الشام للسياحة والسفر',
    'address': 'الجمهورية العربية السورية - محافظة درعا - نوى',
    'phone': '+963 968 155 010',
    'email': 'hawa.alsham990@gmail.com',
    'tax_number': '',
}

_LEGACY_COMPANY_INFO = {
    'address': 'المملكة العربية السعودية - الرياض',
    'phone': '+966 12 3456789',
    'email': 'info@hawaa.com',
}


def _bundled_default_logo_path() -> str:
    candidate = Path(__file__).resolve().parent / 'assets' / 'app_logo.png'
    return str(candidate) if candidate.exists() else ''


def default_company_info() -> dict:
    info = dict(_DEFAULT_COMPANY_INFO)
    info['logo_path'] = _bundled_default_logo_path()
    return info


def _clean(value, default=''):
    value = '' if value is None else str(value)
    value = value.strip()
    return value or default


def _normalize_company_value(key: str, value: str, default: str) -> str:
    value = _clean(value, default)
    if key in _LEGACY_COMPANY_INFO and value == _LEGACY_COMPANY_INFO[key]:
        return default
    return value


def _get_config_file():
    global _CONFIG_FILE
    if _CONFIG_FILE is None:
        _CONFIG_FILE = os.path.join(os.path.dirname(get_local_db_path()), 'config.json')
    return _CONFIG_FILE


def _load_config():
    cfg_file = _get_config_file()
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(config):
    cfg_file = _get_config_file()
    os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
    with open(cfg_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_company_info():
    config = _load_config()
    defaults = default_company_info()
    logo_path = _clean(config.get('company/logo_path', ''), defaults['logo_path'])
    if logo_path and not os.path.exists(logo_path):
        logo_path = defaults['logo_path']
    return {
        'name': _normalize_company_value('name', config.get('company/name', ''), defaults['name']),
        'address': _normalize_company_value('address', config.get('company/address', ''), defaults['address']),
        'phone': _normalize_company_value('phone', config.get('company/phone', ''), defaults['phone']),
        'email': _normalize_company_value('email', config.get('company/email', ''), defaults['email']),
        'tax_number': _clean(config.get('company/tax_number', ''), defaults['tax_number']),
        'logo_path': logo_path,
    }


def save_company_info(info):
    defaults = default_company_info()
    config = _load_config()
    config['company/name'] = _normalize_company_value('name', info.get('name', ''), defaults['name'])
    config['company/address'] = _normalize_company_value('address', info.get('address', ''), defaults['address'])
    config['company/phone'] = _normalize_company_value('phone', info.get('phone', ''), defaults['phone'])
    config['company/email'] = _normalize_company_value('email', info.get('email', ''), defaults['email'])
    config['company/tax_number'] = _clean(info.get('tax_number', ''), defaults['tax_number'])
    logo_path = _clean(info.get('logo_path', ''), defaults['logo_path'])
    if logo_path and not os.path.exists(logo_path):
        logo_path = defaults['logo_path']
    config['company/logo_path'] = logo_path
    _save_config(config)
