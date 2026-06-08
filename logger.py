# -*- coding: utf-8 -*-
import logging
import os
import sys
from datetime import datetime

# تحديد مسار ملف السجل داخل مجلد التطبيق
def get_log_path():
    # محاولة استخدام مجلد التطبيق (يعمل على Android و سطح المكتب)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # في Android، المسار قد لا يكون قابلاً للكتابة، لذا نستخدم مجلد البيانات
    if os.path.exists('/data/data/com.hawaa'):
        log_dir = '/data/data/com.hawaa/files'
    else:
        log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f'hawaa_{datetime.now().strftime("%Y%m%d")}.log')

def setup_logger():
    log_path = get_log_path()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('hawaa')

logger = setup_logger()
