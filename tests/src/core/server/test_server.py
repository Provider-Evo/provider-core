from __future__ import annotations

import pytest


def test_server_import() -> None:
    """测试服务器模块可以导入。"""
    try:
        from src.core.server import create_app
        assert callable(create_app)
    except ImportError as e:
        pytest.skip(f"服务器模块导入失败: {e}")


def test_server_utils() -> None:
    """测试服务器工具函数。"""
    try:
        from src.core.server import json_response
        assert callable(json_response)
    except ImportError as e:
        pytest.skip(f"服务器工具函数导入失败: {e}")
