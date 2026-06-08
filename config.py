# -*- coding: utf-8 -*-
import os
import json
from database.connection import get_local_db_path

_CONFIG_FILE = None

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
        except:
            pass
    return {}

def _save_config(config):
    cfg_file = _get_config_file()
    os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
    with open(cfg_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_company_info():
    config = _load_config()
    return {
        'name': config.get('company/name', 'هوى الشام للسياحة والسفر'),
        'address': config.get('company/address', 'المملكة العربية السعودية - الرياض'),
        'phone': config.get('company/phone', '+966 12 3456789'),
        'email': config.get('company/email', 'info@hawaa.com'),
        'tax_number': config.get('company/tax_number', ''),
        'logo_path': config.get('company/logo_path', ''),
    }

def save_company_info(info):
    config = _load_config()
    config['company/name'] = info.get('name', '')
    config['company/address'] = info.get('address', '')
    config['company/phone'] = info.get('phone', '')
    config['company/email'] = info.get('email', '')
    config['company/tax_number'] = info.get('tax_number', '')
    config['company/logo_path'] = info.get('logo_path', '')
    _save_config(config)
