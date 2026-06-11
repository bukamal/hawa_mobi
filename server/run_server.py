#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
os.environ["HAWAA_SERVER_PROCESS"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from waitress import serve
except ModuleNotFoundError:
    serve = None
try:
    from server.config import load_server_config
    from server.flask_server import app
except ModuleNotFoundError:
    # Allows running from inside hf/server as: python run_server.py
    from config import load_server_config
    from flask_server import app

if __name__ == '__main__':
    cfg = load_server_config()
    print(f"🚀 تشغيل خادم هوى الشام على {cfg.host}:{cfg.port} ...")
    try:
        if serve is not None:
            serve(app, host=cfg.host, port=cfg.port, threads=cfg.threads)
        else:
            print('تحذير: waitress غير مثبتة؛ سيتم تشغيل Flask development server.')
            app.run(host=cfg.host, port=cfg.port)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف الخادم.")
