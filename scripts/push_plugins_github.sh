#!/bin/bash
# 创建并推送所有插件仓库到 GitHub
# Usage: bash scripts/push_plugins_github.sh

set -e

PLUGINS_DIR="plugins"
PROXY="http://127.0.0.1:10808"
GITHUB_USER="nichengfuben"

echo "=== 创建并推送插件到 GitHub ==="

# 设置代理
export http_proxy="$PROXY"
export https_proxy="$PROXY"

for plugin_dir in "$PLUGINS_DIR"/Provider-*/; do
    plugin_name=$(basename "$plugin_dir")
    echo ""
    echo "--- $plugin_name ---"

    cd "$plugin_dir"

    # 检查远程仓库是否已存在
    if ! gh repo view "$GITHUB_USER/$plugin_name" >/dev/null 2>&1; then
        echo "  创建远程仓库..."
        if gh repo create "$GITHUB_USER/$plugin_name" --private --description "$plugin_name for Provider-V2" 2>&1; then
            echo "  远程仓库创建成功"
        else
            echo "  远程仓库创建失败"
            cd - > /dev/null
            continue
        fi
    else
        echo "  远程仓库已存在"
    fi

    # 推送到 GitHub
    echo "  推送中..."
    if git push -u origin master --force 2>&1; then
        echo "  推送成功"
    else
        echo "  推送失败"
    fi

    cd - > /dev/null
done

# 取消代理
unset http_proxy
unset https_proxy

echo ""
echo "=== 完成 ==="
