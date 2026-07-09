#!/bin/bash
# 为所有插件添加测试和 CI
# Usage: bash scripts/add_tests_ci.sh

set -e

PLUGINS_DIR="plugins"

echo "=== 添加测试和 CI ==="

for plugin_dir in "$PLUGINS_DIR"/Provider-*/; do
    plugin_name=$(basename "$plugin_dir")
    echo ""
    echo "--- $plugin_name ---"

    cd "$plugin_dir"

    # 创建 tests 目录
    mkdir -p tests

    # 创建测试文件
    if [ ! -f "tests/__init__.py" ]; then
        echo "" > tests/__init__.py
    fi

    # 获取插件 Python 包名（小写，去掉 Provider- 和 -Adapter 后缀）
    pkg_name=$(echo "$plugin_name" | sed 's/^Provider-//' | sed 's/-Adapter$//' | tr '[:upper:]' '[:lower:]' | tr '-' '_')

    if [ ! -f "tests/test_plugin.py" ]; then
        cat > tests/test_plugin.py << EOF
"""$plugin_name 基本测试。"""
from __future__ import annotations


def test_manifest_exists():
    """验证 manifest 文件存在。"""
    from pathlib import Path
    manifest = Path(__file__).parent.parent / "_manifest.json"
    assert manifest.is_file(), f"{manifest} not found"


def test_plugin_entry():
    """验证插件入口模块可导入。"""
    import sys
    from pathlib import Path
    plugin_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(plugin_dir))
    import plugin
    assert hasattr(plugin, "create_plugin"), "create_plugin not found"
EOF
        echo "  创建测试文件"
    fi

    # 创建 CI 工作流目录
    mkdir -p .github/workflows

    # 创建 CI 工作流
    if [ ! -f ".github/workflows/ci.yml" ]; then
        cat > .github/workflows/ci.yml << EOF
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python \${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: \${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .

      - name: Run tests
        run: |
          python -m pytest tests/ -v
EOF
        echo "  创建 CI 工作��"
    fi

    # 提交更改
    git add -A
    if ! git diff --cached --quiet; then
        git commit -m "test: add tests and CI workflow"
        echo "  提交完成"
    else
        echo "  无更改需要提交"
    fi

    cd - > /dev/null
done

echo ""
echo "=== 完成 ==="
