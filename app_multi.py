import streamlit as st
import requests
import re
import time
import pandas as pd
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="B站多视频实时对比监测",
    page_icon="📊",
    layout="wide"
)

def get_video_stats(target):
    """获取B站视频数据"""
    # 提取BV号
    match = re.search(r'BV[A-Za-z0-9]+', target)
    if not match:
        return None
    bvid = match.group(0)

    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data['code'] == 0:
            return {
                'bvid': bvid,
                'title': data['data']['title'],
                'stat': data['data']['stat']
            }
        else:
            return None
    except Exception:
        return None

# 初始化 Session State
if 'video_list' not in st.session_state:
    st.session_state.video_list = []  # 存储已添加的视频信息 {bvid, title}
if 'history_all' not in st.session_state:
    st.session_state.history_all = pd.DataFrame(columns=['时间', '视频标题', '评论数', '播放量', '点赞量'])
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False

st.title("📊 B站多视频数据实时对比监测")

# 侧边栏：添加视频和配置
with st.sidebar:
    st.header("1. 添加视频")
    new_video = st.text_input("输入视频链接或BV号", key="new_video_input")
    if st.button("添加对比视频"):
        if new_video:
            video_info = get_video_stats(new_video)
            if video_info:
                if video_info['bvid'] not in [v['bvid'] for v in st.session_state.video_list]:
                    st.session_state.video_list.append(video_info)
                    st.success(f"已添加: {video_info['title'][:15]}...")
                else:
                    st.warning("该视频已在列表内")
            else:
                st.error("获取视频信息失败，请检查链接")

    if st.session_state.video_list:
        st.write("---")
        st.header("2. 已添加列表")
        for i, v in enumerate(st.session_state.video_list):
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"• {v['title'][:20]}...")
            if col_b.button("🗑️", key=f"del_{i}"):
                st.session_state.video_list.pop(i)
                st.rerun()

    st.write("---")
    st.header("3. 运行配置")
    refresh_rate = st.slider("刷新频率 (秒)", min_value=3, max_value=60, value=5)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("开始监测", type="primary", use_container_width=True):
            st.session_state.monitoring = True
    with c2:
        if st.button("停止监测", use_container_width=True):
            st.session_state.monitoring = False
    
    if st.button("清空所有数据", use_container_width=True):
        st.session_state.history_all = pd.DataFrame(columns=['时间', '视频标题', '评论数', '播放量', '点赞量'])
        st.rerun()

# 主界面展示
if not st.session_state.video_list:
    st.info("👈 请在左侧侧边栏添加至少一个视频开始对比。")
else:
    # 实时数据表格/指标
    st.subheader("📍 最新数据概览")
    current_data = []
    
    for v in st.session_state.video_list:
        data = get_video_stats(v['bvid'])
        if data:
            s = data['stat']
            current_data.append({
                "视频标题": data['title'],
                "评论数": s['reply'],
                "播放量": s['view'],
                "点赞量": s['like'],
                "投币量": s['coin']
            })
            
            # 如果监测开启，存入历史
            if st.session_state.monitoring:
                ts = datetime.now().strftime('%H:%M:%S')
                new_row = {
                    '时间': ts,
                    '视频标题': data['title'],
                    '评论数': s['reply'],
                    '播放量': s['view'],
                    '点赞量': s['like']
                }
                st.session_state.history_all = pd.concat([st.session_state.history_all, pd.DataFrame([new_row])], ignore_index=True)

    # 显示当前实时表格
    st.table(pd.DataFrame(current_data))

    # 可视化对比图表
    if not st.session_state.history_all.empty:
        st.divider()
        st.subheader("📈 趋势对比可视化")
        
        tab1, tab2, tab3 = st.tabs(["评论数对比", "播放量对比", "点赞量对比"])
        
        with tab1:
            chart_data = st.session_state.history_all.pivot(index='时间', columns='视频标题', values='评论数')
            st.line_chart(chart_data)
            
        with tab3:
            chart_data = st.session_state.history_all.pivot(index='时间', columns='视频标题', values='点赞量')
            st.line_chart(chart_data)

        with tab2:
            chart_data = st.session_state.history_all.pivot(index='时间', columns='视频标题', values='播放量')
            st.line_chart(chart_data)

        # 保持数据量可控
        max_points = 50 * len(st.session_state.video_list)
        if len(st.session_state.history_all) > max_points:
            st.session_state.history_all = st.session_state.history_all.tail(max_points)

    if st.session_state.monitoring:
        time.sleep(refresh_rate)
        st.rerun()
    else:
        st.info("点击左侧“开始监测”查看动态演变。")
