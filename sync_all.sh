#!/bin/bash
echo "🚀 开始全平台同步..."

echo "1/3 同步 GitHub (Origin)..."
git push origin main

echo "2/3 同步 Hugging Face (HF)..."
git push hf main --force

echo "3/3 同步 Gitee (Gitee)..."
git push gitee main --force

echo "✅ 所有平台 (GitHub, HF, Gitee) 已完成同步！"
