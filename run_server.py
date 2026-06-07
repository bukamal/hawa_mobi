#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from waitress import serve
from flask_server import app

if __name__ == '__main__':
    print("🚀 تشغيل خادم هوى الشام...")
    try:
        serve(app, host='0.0.0.0', port=8000, threads=4)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف الخادم.")
