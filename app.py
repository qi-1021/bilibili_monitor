import streamlit as st
import requests
import re
import time
import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# --- 时区设置 ---
CST = timezone(timedelta(hours=8)) # 中国标准时间 (东八区)

# 设置页面配置 (绝对第一位)
st.set_page_config(
    page_title="B站多视频实时趋势分析",
    page_icon="📈",
    layout="wide"
)

# --- DATABASE SETUP ---
def get_db_path():
    # 自动探测云端持久化路径
    paths = [
        "/mnt/workspace/monitor.db",  # 魔搭持久化路径
        "/data/monitor.db",           # Hugging Face 持久化路径
        "monitor.db"                  # 本地/回退路径
    ]
    for p in paths:
        try:
            # 检查目录是否存在且可写
            d = os.path.dirname(p)
            if d == "" or os.path.exists(d):
                return p
        except: continue
    return "monitor.db"

DB_PATH = get_db_path()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL") # 开启 WAL 模式支持多进程并发
    cursor = conn.cursor()
    # 历史记录表
    cursor.execute('''CREATE TABLE IF NOT EXISTS history 
                     (timestamp REAL, datetime TEXT, bvid TEXT, title TEXT, reply INTEGER, view INTEGER, likes INTEGER, growth REAL)''')
    # 长期对照库表 (增加 total_deleted 永久计数器, last_known_count 状态机)
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracked_videos 
                     (bvid TEXT PRIMARY KEY, title TEXT, is_active INTEGER DEFAULT 0, 
                      total_deleted INTEGER DEFAULT 0, last_known_count INTEGER DEFAULT 0)''')
    # 全局设置表 (用于多端同步)
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)''')
    
    # 迁移旧数据（如果缺少列）
    cursor.execute("PRAGMA table_info(tracked_videos)")
    cols = [col[1] for col in cursor.fetchall()]
    for col_name in ['is_active', 'total_deleted', 'last_known_count']:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE tracked_videos ADD COLUMN {col_name} INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

def set_config(key, value):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def get_config(key, default=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except: return default

def add_tracked_video(bvid, title, is_active=1):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    # 保持原有的状态和计数
    cursor.execute('''INSERT OR IGNORE INTO tracked_videos (bvid, title, is_active, total_deleted, last_known_count) 
                      VALUES (?, ?, ?, 0, 0)''', (bvid, title, is_active))
    cursor.execute('UPDATE tracked_videos SET title = ?, is_active = ? WHERE bvid = ?', (title, is_active, bvid))
    conn.commit()
    conn.close()

def sync_and_detect_deletions(bvid, current_count):
    """持久化状态机：彻底解决监测断档问题"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10) # 增加超时等待
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_known_count FROM tracked_videos WHERE bvid = ?', (bvid,))
        row = cursor.fetchone()
        
        if row:
            last_count = row[0]
            # 1. 初始化或异常恢复：如果上次是0，直接同步当前值作为基准
            if last_count <= 0:
                cursor.execute('UPDATE tracked_videos SET last_known_count = ? WHERE bvid = ?', (current_count, bvid))
            # 2. 发现删评：当前值显著小于上次记录
            elif current_count < last_count:
                diff = last_count - current_count
                # 累加删评总数，并同步最新计数值
                cursor.execute('''UPDATE tracked_videos 
                                 SET total_deleted = total_deleted + ?, last_known_count = ? 
                                 WHERE bvid = ?''', (diff, current_count, bvid))
            # 3. 正常增长：只同步最新计数值
            else:
                cursor.execute('UPDATE tracked_videos SET last_known_count = ? WHERE bvid = ?', (current_count, bvid))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def toggle_active_video(bvid, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE tracked_videos SET is_active = ? WHERE bvid = ?', (1 if status else 0, bvid))
    conn.commit()
    conn.close()

def get_tracked_videos(only_active=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if only_active:
        cursor.execute('SELECT bvid, title, total_deleted FROM tracked_videos WHERE is_active = 1')
    else:
        cursor.execute('SELECT bvid, title, is_active, total_deleted FROM tracked_videos')
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_history(record):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO history VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                  (record['timestamp'], record['datetime'], record['bvid'], record['title'], 
                   record['reply'], record['view'], record['likes'], record['growth']))
    conn.commit()
    conn.close()

def get_history(limit=2000):
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
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
        df['datetime_dt'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S')
        df = df.sort_values('timestamp')
    return df

def clear_all_history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    # 同时清空累计删评计数器
    cursor.execute("UPDATE tracked_videos SET total_deleted = 0")
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
st.caption(f"🕒 本次更新: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")

with st.sidebar:
    st.header("1. 监测控制")
    # 从数据库读取全局频率设置
    saved_rate = int(get_config("refresh_rate", 5))
    refresh_rate = st.select_slider("刷新频率 (秒)", options=[1, 2, 5, 10, 30, 60], value=saved_rate)
    if refresh_rate != saved_rate:
        set_config("refresh_rate", refresh_rate)
    
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
        for v_bvid, v_title, v_active, v_del in all_saved:
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
    now = datetime.now(CST)
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
                        # 计算本次真实变动
                        current_diff = s['reply'] - last['评论数']
                        growth = current_diff / time_diff if time_diff > 0 else 0
                        
                        # 核心改进：调用持久化状态机进行删评监测
                        if st.session_state.monitoring:
                            sync_and_detect_deletions(v_bvid, s['reply'])
                    
                    with cols[j]:
                        # 绿色/红色 Delta 区显示本次新增/减少的绝对数量
                        st.metric(label=f"{data['title'][:10]}", 
                                  value=f"{s['reply']:,}", 
                                  delta=f"{current_diff} 条" if not prev_record.empty else None)
                        st.caption(f"🚀 实时增速: {growth:.1f} 条/分")
            
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

    # --- 增强版：删评深度分析板块 ---
    st.divider()
    st.subheader("🛡️ 删评深度审计 (Censorship Audit)")
    
    audit_data = []
    # 重新获取活跃视频，这次包含最新的 total_deleted 字段
    active_with_stats = get_tracked_videos(only_active=True)
    for v_bvid, v_title, v_total_del in active_with_stats:
        if v_total_del > 0:
            v_history = df_history[df_history['bvid'] == v_bvid].sort_values('timestamp')
            current_total = v_history.iloc[-1]['评论数'] if not v_history.empty else 0
            del_ratio = (v_total_del / (current_total + v_total_del)) * 100 if (current_total + v_total_del) > 0 else 0
            
            severity = "🟢 正常"
            if v_total_del > 50 or del_ratio > 5: severity = "🔴 严重清评"
            elif v_total_del > 10 or del_ratio > 1: severity = "🟡 疑似控评"
            
            # 提取具体的删评记录用于展示
            v_deletions = v_history[v_history['评论数'].diff() < 0].tail(5)
            
            audit_data.append({
                '标题': v_title,
                '累计删评': v_total_del,
                '删评占比': f"{del_ratio:.2f}%",
                '严重程度': severity,
                'details': v_deletions[['datetime', '评论数']] if not v_deletions.empty else pd.DataFrame()
            })

    if not audit_data:
        st.success("✨ 暂未发现删评迹象，评论环境自然增长中。")
    else:
        for audit in audit_data:
            with st.expander(f"{audit['严重程度']} | {audit['标题'][:20]}... (累计删除 {audit['累计删评']} 条)", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("累计被删评论", f"{audit['累计删评']} 条")
                c2.metric("删评率 (估算)", audit['删评占比'])
                c3.write(f"**审计建议：**\n{ '该视频可能正在经历大规模人工干预或清评。' if '严重' in audit['严重程度'] else '属于正常的用户自删或平台过滤。' }")
                
                if not audit['details'].empty:
                    st.caption("🕒 最近删评快照")
                    st.table(audit['details'])

    if not df_history.empty:
        st.divider()
        import plotly.express as px
        
        # 统一图表配置
        chart_config = {
            'height': 450,
            'template': 'plotly_dark' if st.get_option("theme.base") == "dark" else 'plotly_white'
        }

        st.markdown("### 📈 深度趋势分析 (现实时间轴)")
        
        # 图表 1: 累计评论数趋势
        try:
            fig1 = px.line(df_history, 
                          x='datetime_dt', 
                          y='评论数', 
                          color='视频标题',
                          title='1. 累计评论数实时趋势',
                          labels={'datetime_dt': '现实时间', '评论数': '总评论数'},
                          markers=True)
            fig1.update_layout(xaxis_title="观测时间 (现实时间)", yaxis_title="评论总量", **chart_config)
            st.plotly_chart(fig1, use_container_width=True)
        except Exception as e:
            st.error(f"趋势图 1 异常: {e}")

        # 图表 2: 评论增速趋势
        try:
            fig2 = px.line(df_history, 
                          x='datetime_dt', 
                          y='评论增速', 
                          color='视频标题',
                          title='2. 评论发布速度变化 (条/分)',
                          labels={'datetime_dt': '现实时间', '评论增速': '增速 (条/分)'},
                          markers=True)
            fig2.update_layout(xaxis_title="观测时间 (现实时间)", yaxis_title="增长速率", **chart_config)
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"趋势图 2 异常: {e}")
        
        if st.session_state.monitoring:
            time.sleep(refresh_rate)
            st.rerun()

