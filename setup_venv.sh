#!/bin/sh
# 在项目根目录运行，创建 .venv 并安装依赖（Linux / macOS）
cd "$(dirname "$0")"
if [ -d .venv ]; then
    echo ".venv 已存在，跳过创建。直接运行: source .venv/bin/activate"
else
    echo "正在创建虚拟环境 .venv ..."
    python3 -m venv .venv || { echo "失败。请确保已安装 python3-venv / python3"; exit 1; }
fi
echo "正在安装依赖..."
.venv/bin/pip install -r python/requirements.txt
echo ""
echo "完成。激活环境请执行: source .venv/bin/activate"
