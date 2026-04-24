#!/bin/bash

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 正在启动 B站评论监测系统 (高级版)..."

# 检查并准备虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 正在初始化虚拟环境..."
    if command -v uv &> /dev/null
    then
        uv venv .venv --quiet
    else
        python3 -m venv .venv
    fi
fi

# 激活环境并安装/检查依赖
source .venv/bin/activate
if command -v uv &> /dev/null
then
    uv pip install -r requirements.txt --quiet
else
    pip install -r requirements.txt --quiet
fi

echo "📊 环境就绪，正在运行 Streamlit 界面..."
streamlit run app_advanced.py
