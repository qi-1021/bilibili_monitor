import streamlit as st
import requests
import re
import time
import pandas as pd
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="B站视频数据实时监测",
    page_icon="📺",
    layout="wide"
)

def get_video_stats(bvid):
    """获取B站视频数据"""
    # 提取BV号
    match = re.search(r'BV[A-Za-z0-9]+', bvid)
    if match:
        bvid = match.group(0)

    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        else:
            return None
    except Exception as e:
        st.error(f"解析出错: {e}")
        return None

# 初始化 Session State 用于存储历史数据
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['时间', '评论数', '播放量', '点赞量'])
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False

st.title("📺 B站视频数据实时监测工具")

# 侧边栏配置
with st.sidebar:
    st.header("配置")
    target_url = st.text_input("视频链接或BV号", placeholder="https://www.bilibili.com/video/BV...")
    refresh_rate = st.slider("刷新频率 (秒)", min_value=2, max_value=60, value=5)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("开始监测", type="primary"):
            st.session_state.monitoring = True
    with col2:
        if st.button("停止监测"):
            st.session_state.monitoring = False
    
    if st.button("清空历史数据"):
        st.session_state.history = pd.DataFrame(columns=['时间', '评论数', '播放量', '点赞量'])
        st.rerun()

# 主界面
if target_url:
    video_data = get_video_stats(target_url)
    if video_data:
        st.subheader(video_data['title'])
        
        # 实时指标卡片
        stat = video_data['stat']
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        
        # 计算增量（如果有点话）
        replies = stat['reply']
        views = stat['view']
        likes = stat['like']
        
        m_col1.metric("评论数量", f"{replies:,}")
        m_col2.metric("播放总量", f"{views:,}")
        m_col3.metric("点赞数量", f"{likes:,}")
        m_col4.metric("投币数量", f"{stat['coin']:,}")

        # 图表展示
        if st.session_state.monitoring:
            # 添加新数据到历史记录
            new_data = {
                '时间': datetime.now().strftime('%H:%M:%S'),
                '评论数': replies,
                '播放量': views,
                '点赞量': likes
            }
            st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_data])], ignore_index=True)
            
            # 只保留最近 50 条记录
            if len(st.session_state.history) > 50:
                st.session_state.history = st.session_state.history.tail(50)

            # 绘制图表
            st.divider()
            st.subheader("趋势可视化")
            
            c1, c2 = st.columns(2)
            with c1:
                st.caption("📈 评论总量趋势")
                st.line_chart(st.session_state.history.set_index('时间')[['评论数']], height=250)
            
            with c2:
                st.caption("🚀 评论增长速度 (每轮增量)")
                st.session_state.history['增量'] = st.session_state.history['评论数'].diff().fillna(0)
                st.line_chart(st.session_state.history.set_index('时间')[['增量']], height=250)

            # 倒计时刷新
            time.sleep(refresh_rate)
            st.rerun()
        else:
            st.info("点击左侧“开始监测”按钮启动实时跟踪。")
    else:
        st.error("无法获取视频信息，请检查 BV 号或链接是否正确。")
else:
    st.info("👈 请在左侧输入框内输入 B 站视频链接或 BV 号。")
