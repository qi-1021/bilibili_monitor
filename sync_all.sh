#!/bin/bash
echo "🚀 开始全平台同步 (四位一体)..."

echo "1/4 同步 GitHub (Origin)..."
git push origin main --force

echo "2/4 同步 Hugging Face (HF)..."
git push hf main --force

echo "3/4 同步 Gitee (Gitee)..."
git push gitee main --force

echo "4/4 同步 ModelScope (MS)..."
# 使用临时目录解决魔搭分支保护和同步冲突问题
MS_TMP="ms_sync_tmp"
rm -rf $MS_TMP
git clone https://oauth2:ms-ac0ff44b-8ff6-44c8-81fe-bc39529b0570@www.modelscope.cn/studios/isqi1021/bilibili_monitor.git $MS_TMP
if [ -d "$MS_TMP" ]; then
    cp app.py $MS_TMP/app.py
    cp requirements.txt $MS_TMP/
    cp README.md $MS_TMP/
    cd $MS_TMP
    git add .
    git commit -m "Auto-sync from local"
    git push origin master
    cd ..
    rm -rf $MS_TMP
    echo "✅ 魔搭同步完成！"
else
    echo "❌ 魔搭同步失败：无法克隆仓库"
fi

echo "✨ 所有平台 (GitHub, HF, Gitee, ModelScope) 已同步至最新状态！"
