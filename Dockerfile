FROM python:3.12-slim

WORKDIR /app

# 安装基础依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv (为了更快的安装速度)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv
ENV PATH="/uv/bin:$PATH"

# 复制项目文件
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

# 创建数据目录挂载点
RUN mkdir -p data

# 暴露 Streamlit 端口
EXPOSE 8501

# 启动脚本：运行 Streamlit 高级版界面
CMD ["streamlit", "run", "app_advanced.py", "--server.port=8501", "--server.address=0.0.0.0"]
