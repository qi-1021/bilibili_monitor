import time
import os
import sqlite3
import requests
import re
from datetime import datetime

# 配置区域
DB_PATH = "data/monitor.db"
INTERVAL = int(os.getenv("MONITOR_INTERVAL", 60))  # 默认 60 秒抓一次
BVIDS = os.getenv("MONITOR_BVIDS", "").split(",")  # 从环境变量读取 BV 号列表

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (timestamp REAL, datetime TEXT, bvid TEXT, title TEXT, 
                  reply INTEGER, view INTEGER, likes INTEGER)''')
    conn.commit()
    conn.close()

def get_video_stats(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data['code'] == 0:
            return {
                'bvid': bvid,
                'title': data['data']['title'],
                'stat': data['data']['stat']
            }
    except:
        pass
    return None

def run_collector():
    print(f"🚀 采集器启动，监测列表: {BVIDS}")
    init_db()
    
    while True:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for bvid in BVIDS:
            bvid = bvid.strip()
            if not bvid: continue
            
            stats = get_video_stats(bvid)
            if stats:
                now = datetime.now()
                c.execute("INSERT INTO history VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (now.timestamp(), now.strftime('%Y-%m-%d %H:%M:%S'), 
                           bvid, stats['title'], stats['stat']['reply'], 
                           stats['stat']['view'], stats['stat']['like']))
                print(f"[{now.strftime('%H:%M:%S')}] 已记录: {stats['title'][:20]}")
        
        conn.commit()
        conn.close()
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_collector()
