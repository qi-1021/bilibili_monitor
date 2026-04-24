import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

DB_PATH = "data/monitor.db"

st.set_page_config(page_title="B站视频数据看板 (Docker版)", layout="wide")

def get_data():
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY timestamp ASC", conn)
    conn.close()
    if not df.empty: df['datetime'] = pd.to_datetime(df['datetime'])
    return df

st.title("🛡️ B站数据 24h 自动化监测 (Docker版)")

df = get_data()

if df.empty:
    st.info("⌛ 采集器运行中，正在同步首批数据...")
else:
    unique_videos = df['bvid'].unique()
    cols = st.columns(len(unique_videos))
    for i, bvid in enumerate(unique_videos):
        v = df[df['bvid'] == bvid].iloc[-1]
        with cols[i]:
            st.metric(label=v['title'][:15], value=f"{v['reply']:,} 评论")

    st.divider()
    cl, cr = st.columns(2)
    with cl:
        st.subheader("评论增长趋势")
        st.line_chart(df, x='datetime', y='reply', color='title', width="stretch")
    with cr:
        st.subheader("播放量趋势")
        st.line_chart(df, x='datetime', y='view', color='title', width="stretch")

st.sidebar.caption(f"最后刷新: {datetime.now().strftime('%H:%M:%S')}")
if st.sidebar.button("手动刷新"): st.rerun()
