import streamlit as st
import requests
import re
import time
import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 设置页面配置 (绝对第一位)
st.set_page_config(
    page_title="B站多视频实时趋势分析",
    page_icon="📈",
    layout="wide"
)

# --- DATABASE SETUP ---
DB_PATH = "data/monitor.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (timestamp REAL, datetime TEXT, bvid TEXT, title TEXT, 
                  reply INTEGER, view INTEGER, likes INTEGER, growth REAL)''')
    # 检查并修复旧表缺少 growth 列的问题
    c.execute("PRAGMA table_info(history)")
    columns = [col[1] for col in c.fetchall()]
    if 'growth' not in columns:
        c.execute("ALTER TABLE history ADD COLUMN growth REAL DEFAULT 0.0")
    
    c.execute('''CREATE TABLE IF NOT EXISTS tracked_videos
                 (bvid TEXT PRIMARY KEY, title TEXT)''')
    conn.commit()
    conn.close()

def add_tracked_video(bvid, title):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO tracked_videos VALUES (?, ?)", (bvid, title))
    conn.commit()
    conn.close()

def remove_tracked_video(bvid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tracked_videos WHERE bvid = ?", (bvid,))
    conn.commit()
    conn.close()

def get_tracked_videos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM tracked_videos", conn)
    conn.close()
    return df.to_dict('records')

def save_history(record):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (record['timestamp'], record['datetime'], record['bvid'], record['title'], 
               record['reply'], record['view'], record['likes'], record['growth']))
    conn.commit()
    conn.close()

def get_history(limit=2000):
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    # 使用别名将数据库列名映射回老版本的中文名称，以便图表展示一致
    df = pd.read_sql_query(f"""
        SELECT timestamp, datetime, bvid, 
               title AS 视频标题, 
               reply AS 评论数, 
               view AS 播放量, 
               likes AS 点赞量, 
               growth AS 评论增速 
        FROM history ORDER BY timestamp DESC LIMIT {limit}
    """, conn)
    conn.close()
    if not df.empty:
        # 确保转换为绝对时间对象
        df['datetime_dt'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S')
        df = df.sort_values('timestamp')
    return df

def clear_all_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

# --- DATA FETCHING ---
def get_video_stats(target):
    match = re.search(r'BV[A-Za-z0-9]+', target)
    if not match: return None
    bvid = match.group(0)
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        if data['code'] == 0:
            return {'bvid': bvid, 'title': data['data']['title'], 'stat': data['data']['stat']}
    except: return None
    return None

init_db()

if 'monitoring' not in st.session_state: st.session_state.monitoring = False

st.title("📈 B站多视频实时对比 (电脑交互版)")
st.caption(f"🕒 上次数据更新时间: {datetime.now().strftime('%H:%M:%S')}")

with st.sidebar:
    st.header("1. 添加对比视频")
    new_video = st.text_input("链接或BV号")
    if st.button("添加"):
        video_info = get_video_stats(new_video)
        if video_info:
            add_tracked_video(video_info['bvid'], video_info['title'])
            st.rerun()

    st.header("2. 监测控制")
    refresh_rate = st.select_slider("刷新频率 (秒)", options=[1, 2, 5, 10, 30, 60], value=5)
    c1, c2 = st.columns(2)
    if c1.button("▶️ 开始监测", use_container_width=True): st.session_state.monitoring = True
    if c2.button("⏹️ 停止监测", use_container_width=True): st.session_state.monitoring = False
    if st.button("🧹 清空所有数据", use_container_width=True):
        clear_all_history()
        st.rerun()

    tracked = get_tracked_videos()
    if tracked:
        st.write("---")
        st.subheader("已添加列表")
        for v in tracked:
            col_t, col_b = st.columns([4, 1])
            col_t.text(v['title'][:15])
            if col_b.button("🗑️", key=v['bvid']):
                remove_tracked_video(v['bvid'])
                st.rerun()

if not tracked:
    st.info("👈 请在左侧添加视频开始实时对比。")
else:
    now = datetime.now()
    summary_cols = st.columns(len(tracked))
    df_history = get_history(limit=2000)
    
    current_batch = []
    
    # 使用并行抓取提高性能
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda v: get_video_stats(v['bvid']), tracked))

    for idx, data in enumerate(results):
        if data:
            v_bvid = data['bvid']
            s = data['stat']
            growth = 0.0
            
            # 从历史记录中寻找上一次该视频的数据
            prev_record = df_history[df_history['bvid'] == v_bvid]
            if not prev_record.empty:
                last = prev_record.iloc[-1]
                time_diff = (now.timestamp() - last['timestamp']) / 60
                growth = (s['reply'] - last['评论数']) / time_diff if time_diff > 0 else 0
            
            with summary_cols[idx]:
                st.metric(label=f"{data['title'][:10]}", 
                          value=f"{s['reply']:,}", 
                          delta=f"{s['reply'] - (last['评论数'] if not prev_record.empty else s['reply'])} 新增")
                st.caption(f"🚀 增速: {growth:.1f} 条/分")
            
            if st.session_state.monitoring:
                current_batch.append({
                    'timestamp': now.timestamp(),
                    'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'bvid': v_bvid,
                    '视频标题': data['title'],
                    '评论数': s['reply'],
                    '播放量': s['view'],
                    '点赞量': s['like'],
                    '评论增速': growth
                })

    if st.session_state.monitoring:
        for record in current_batch:
            save_history({
                'timestamp': record['timestamp'], 'datetime': record['datetime'],
                'bvid': record['bvid'], 'title': record['视频标题'],
                'reply': record['评论数'], 'view': record['播放量'], 'likes': record['点赞量'],
                'growth': record['评论增速']
            })
        
        # 重新获取历史以包含最新数据
        df_history = get_history(limit=2000)

    if not df_history.empty:
        st.divider()
        c_l, c_r = st.columns(2)
        
        # 使用透视表 (Wide Format) 是 Streamlit 图表最稳定的展示方式，能有效避免云端渲染报错
        with c_l:
            st.markdown("**1. 评论数增长趋势**")
            try:
                chart_data_total = df_history.pivot_table(index='datetime_dt', columns='视频标题', values='评论数', aggfunc='last')
                st.line_chart(chart_data_total, height=400)
            except Exception as e:
                st.error(f"图表 1 渲染失败: {e}")
                
        with c_r:
            st.markdown("**2. 评论发布速度**")
            try:
                chart_data_growth = df_history.pivot_table(index='datetime_dt', columns='视频标题', values='评论增速', aggfunc='last')
                st.line_chart(chart_data_growth, height=400)
            except Exception as e:
                st.error(f"图表 2 渲染失败: {e}")
        
        if st.session_state.monitoring:
            time.sleep(refresh_rate)
            st.rerun()

