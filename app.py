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
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 历史记录表
    cursor.execute('''CREATE TABLE IF NOT EXISTS history 
                     (timestamp REAL, datetime TEXT, bvid TEXT, title TEXT, reply INTEGER, view INTEGER, likes INTEGER, growth REAL)''')
    # 长期对照库表
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracked_videos 
                     (bvid TEXT PRIMARY KEY, title TEXT, is_active INTEGER DEFAULT 0)''')
    
    # 迁移旧数据（如果缺少 is_active 列）
    cursor.execute("PRAGMA table_info(tracked_videos)")
    cols = [col[1] for col in cursor.fetchall()]
    if 'is_active' not in cols:
        cursor.execute("ALTER TABLE tracked_videos ADD COLUMN is_active INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

def add_tracked_video(bvid, title, is_active=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO tracked_videos (bvid, title, is_active) VALUES (?, ?, ?)', (bvid, title, is_active))
    conn.commit()
    conn.close()

def toggle_active_video(bvid, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE tracked_videos SET is_active = ? WHERE bvid = ?', (1 if status else 0, bvid))
    conn.commit()
    conn.close()

def remove_tracked_video(bvid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tracked_videos WHERE bvid = ?", (bvid,))
    conn.commit()
    conn.close()

def get_tracked_videos(only_active=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if only_active:
        cursor.execute('SELECT bvid, title FROM tracked_videos WHERE is_active = 1')
    else:
        cursor.execute('SELECT bvid, title, is_active FROM tracked_videos')
    rows = cursor.fetchall()
    conn.close()
    return rows

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

st.title("📈 B站实时监测 (全设备适配版)")
st.caption(f"🕒 本次更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with st.sidebar:
    st.header("1. 监测控制")
    refresh_rate = st.select_slider("刷新频率 (秒)", options=[1, 2, 5, 10, 30, 60], value=5)
    c1, c2 = st.columns(2)
    if c1.button("▶️ 开始", use_container_width=True): st.session_state.monitoring = True
    if c2.button("⏹️ 停止", use_container_width=True): st.session_state.monitoring = False
    
    st.divider()
    st.header("2. 添加项目")
    new_video = st.text_input("BVID / 链接", placeholder="存入对照库")
    if st.button("📥 永久存入库"):
        video_info = get_video_stats(new_video)
        if video_info:
            add_tracked_video(video_info['bvid'], video_info['title'], is_active=1)
            st.rerun()

    st.divider()
    st.header("📚 对照仓库 (持久化)")
    all_saved = get_tracked_videos()
    if not all_saved:
        st.caption("仓库空空如也")
    else:
        for v_bvid, v_title, v_active in all_saved:
            col_t, col_btn = st.columns([3, 1])
            label = "✅" if v_active else "📁"
            if col_t.button(f"{label} {v_title[:10]}", key=f"tgl_{v_bvid}"):
                toggle_active_video(v_bvid, not v_active)
                st.rerun()
            if col_btn.button("🗑️", key=f"del_{v_bvid}"):
                remove_tracked_video(v_bvid)
                st.rerun()

    if st.button("🧹 清理历史数据", use_container_width=True):
        clear_all_history()
        st.rerun()

# 获取当前活跃的视频
active_tracked = get_tracked_videos(only_active=True)

if not active_tracked:
    st.info("👈 请在左侧点击项目图标（📁 -> ✅）来激活实时对比。")
else:
    now = datetime.now()
    df_history = get_history(limit=2000)
    current_batch = []
    
    # 使用并行抓取提高性能
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda v: get_video_stats(v[0]), active_tracked))

    # 使用响应式网格布局：电脑端并排，手机端自动适配
    st.markdown("### 📊 实时数据概览")
    for i in range(0, len(results), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(results):
                data = results[i + j]
                if data:
                    v_bvid = data['bvid']
                    s = data['stat']
                    growth = 0.0
                    prev_record = df_history[df_history['bvid'] == v_bvid]
                    if not prev_record.empty:
                        last = prev_record.iloc[-1]
                        time_diff = (now.timestamp() - last['timestamp']) / 60
                        growth = (s['reply'] - last['评论数']) / time_diff if time_diff > 0 else 0
                    
                    with cols[j]:
                        st.metric(label=f"{data['title'][:10]}", 
                                  value=f"{s['reply']:,}", 
                                  delta=f"{growth:.1f} 条/分")
                        st.caption(f"🚀 增速: {growth:.1f}")
            
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

    # --- 删评分析板块 ---
    st.divider()
    st.subheader("🛡️ 删评预警分析")
    
    # 从历史记录中提取删评事件 (当前评论数 < 上一次记录的评论数)
    # 我们按视频分组并计算差值
    deletion_events = []
    for v_bvid, v_title in active_tracked:
        v_history = df_history[df_history['bvid'] == v_bvid].sort_values('timestamp')
        if len(v_history) > 1:
            # 计算相邻两次采集的评论数差值
            v_history['diff'] = v_history['评论数'].diff()
            # 过滤出差值为负的情况
            deletions = v_history[v_history['diff'] < 0].copy()
            if not deletions.empty:
                total_deleted = abs(deletions['diff'].sum())
                deletion_events.append({
                    'title': v_title,
                    'count': total_deleted,
                    'last_time': deletions.iloc[-1]['datetime']
                })
    
    if not deletion_events:
        st.success("✅ 暂未监测到异常删评行为 (评论总量持续增长中)")
    else:
        cols_del = st.columns(min(len(deletion_events), 3))
        for idx, ev in enumerate(deletion_events):
            with cols_del[idx % 3]:
                st.warning(f"**{ev['title'][:10]}...**")
                st.metric("累计删评数", f"{int(ev['count'])} 条", delta="- 异常减少", delta_color="inverse")
                st.caption(f"最后发生: {ev['last_time']}")

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

