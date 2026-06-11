#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
os.environ["HAWAA_SERVER_PROCESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from waitress import serve
except ModuleNotFoundError:
    serve = None
from flask_server import app

if __name__ == '__main__':
    print("🚀 تشغيل خادم هوى الشام...")
    try:
        
        if serve is not None:
            serve(app, host='0.0.0.0', port=8000, threads=4)
        else:
            print('تحذير: waitress غير مثبتة؛ سيتم تشغيل Flask development server.')
            app.run(host='0.0.0.0', port=8000)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف الخادم.")
