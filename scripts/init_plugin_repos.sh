#!/bin/bash
# 初始化所有插件仓库
# Usage: bash scripts/init_plugin_repos.sh

set -e

PLUGINS_DIR="plugins"
REMOTE_BASE="git@github.com:nichengfuben"

echo "=== 初始化插件仓库 ==="

for plugin_dir in "$PLUGINS_DIR"/Provider-*/; do
    plugin_name=$(basename "$plugin_dir")
    echo ""
    echo "--- $plugin_name ---"

    cd "$plugin_dir"

    # 初始化 git 仓库
    if [ ! -d ".git" ]; then
        git init
        echo "  git init 完成"
    fi

    # 创建初始提交
    git add -A
    if git diff --cached --quiet; then
        echo "  无更改需要提交"
    else
        git commit -m "feat: initial scaffold for $plugin_name"
        echo "  初始提交完成"
    fi

    # 添加远程仓库
    remote_name="${plugin_name,,}"  # 转小写
    remote_name="${remote_name//[^a-z0-9]/-}"  # 替换特殊字符
    if ! git remote | grep -q "origin"; then
        git remote add origin "$REMOTE_BASE/$plugin_name.git"
        echo "  添加远程仓库: $REMOTE_BASE/$plugin_name.git"
    fi

    cd - > /dev/null
done

echo ""
echo "=== 完成 ==="
echo "所有插件仓库已初始化"
echo "使用 'git -C plugins/<name> push -u origin main' 推送到 GitHub"
