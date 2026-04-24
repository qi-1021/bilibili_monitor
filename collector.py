import time
import sqlite3
import requests
import os
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# --- 时区设置 ---
CST = timezone(timedelta(hours=8)) # 中国标准时间 (东八区)

# --- 配置与数据库 ---
def get_db_path():
    paths = ["/mnt/workspace/monitor.db", "/data/monitor.db", "monitor.db"]
    for p in paths:
        try:
            d = os.path.dirname(p)
            if d == "" or os.path.exists(d): return p
        except: continue
    return "monitor.db"

DB_PATH = get_db_path()

def sync_and_detect_deletions(bvid, current_count):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('SELECT last_known_count FROM tracked_videos WHERE bvid = ?', (bvid,))
        row = cursor.fetchone()
        if row:
            last_count = row[0]
            if last_count <= 0:
                cursor.execute('UPDATE tracked_videos SET last_known_count = ? WHERE bvid = ?', (current_count, bvid))
            elif current_count < last_count:
                diff = last_count - current_count
                cursor.execute('UPDATE tracked_videos SET total_deleted = total_deleted + ?, last_known_count = ? WHERE bvid = ?', 
                               (diff, current_count, bvid))
            else:
                cursor.execute('UPDATE tracked_videos SET last_known_count = ? WHERE bvid = ?', (current_count, bvid))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Collector DB Error: {e}")

def save_history(record):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    cursor.execute('INSERT INTO history VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                  (record['timestamp'], record['datetime'], record['bvid'], record['title'], 
                   record['reply'], record['view'], record['likes'], record['growth']))
    conn.commit()
    conn.close()

def get_video_stats(bvid):
    try:
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5).json()
        if res['code'] == 0:
            return {'bvid': bvid, 'title': res['data']['title'], 'stat': res['data']['stat']}
    except: return None
    return None

def task():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT bvid, title FROM tracked_videos WHERE is_active = 1')
            active_videos = cursor.fetchall()
            
            # 读取频率设置
            cursor.execute('SELECT value FROM settings WHERE key = "refresh_rate"')
            row = cursor.fetchone()
            interval = int(row[0]) if row else 5
            conn.close()

            if not active_videos:
                time.sleep(10)
                continue

            now = datetime.now(CST)
            for bvid, title in active_videos:
                data = get_video_stats(bvid)
                if data:
                    s = data['stat']
                    # 1. 记录历史 (用于图表)
                    # 这里简化了增速计算，主要为了保证数据的连续性
                    save_history({
                        'timestamp': now.timestamp(),
                        'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
                        'bvid': bvid,
                        'title': title,
                        'reply': s['reply'],
                        'view': s['view'],
                        'likes': s['like'],
                        'growth': 0 # 后台暂不计算复杂增速
                    })
                    # 2. 状态机对比 (核心删评审计)
                    sync_and_detect_deletions(bvid, s['reply'])
            
            print(f"[{now}] 后台采集完成: {len(active_videos)} 个项目")
            time.sleep(interval)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    print("🚀 B站忠诚监测后台启动...")
    task()
