---
title: Bilibili Monitor
emoji: 📈
colorFrom: blue
colorTo: red
sdk: streamlit
sdk_version: 1.31.0
app_file: app.py
pinned: false
---

# B站多视频实时趋势分析工具 🚀

一个高性能、实时的 B 站视频数据监测看板，支持多视频对比、数据持久化及 Docker 一键部署。

## ✨ 核心功能
- **📊 实时数据看板**：实时监测视频的评论数、播放量、点赞数。
- **📈 趋势对比曲线**：多视频同图对比评论总量增长趋势。
- **🚀 增速实时分析**：独家“评论发布速度”曲线，一眼看出哪个视频正在爆火。
- **💾 数据持久化**：内置 SQLite 数据库，即便重启程序，历史曲线也不会丢失。
- **🐳 Docker 支持**：支持容器化部署，环境隔离，运行稳定。

## 🛠️ 安装与使用

### 本地快速启动
1. 确保已安装 Python 3.9+。
2. 运行启动脚本：
   ```bash
   bash start.sh
   ```
   脚本会自动创建虚拟环境、安装依赖并启动看板。

### Docker 部署
```bash
docker-compose up -d --build
```
启动后访问 [http://localhost:8501](http://localhost:8501) 即可。

## 📂 项目结构
- `app_advanced.py`: 主程序（高级版，支持多视频对比与持久化）。
- `app.py`: 基础版（单视频快速监测）。
- `data/`: 数据库存储目录。
- `docker-compose.yml`: Docker 编排配置。

## ⚙️ 技术栈
- **Streamlit**: 网页交互界面。
- **SQLite**: 本地数据存储。
- **Pandas & NumPy**: 数据处理与分析。
- **Concurrent.futures**: 高并发并行数据抓取。

---
*注意：本工具使用 B 站公开 API。请合理设置刷新频率（建议 5 秒以上），尊重平台规则。*
