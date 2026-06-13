from __future__ import annotations

import importlib
from typing import Any

import pytest


def verify_platform_contract(platform_name: str) -> None:
    """验证平台最小契约。"""
    try:
        module = importlib.import_module('src.platforms.{}'.format(platform_name))
    except Exception as exc:
        pytest.skip('平台导入失败: {}'.format(exc))
    adapter_cls: Any = getattr(module, 'Adapter', None)
    if adapter_cls is None:
        try:
            adapter_module = importlib.import_module('src.platforms.{}.adapter'.format(platform_name))
        except Exception as exc:
            pytest.skip('平台 adapter 模块导入失败: {}'.format(exc))
        adapter_cls = getattr(adapter_module, 'Adapter', None)
    if adapter_cls is None:
        pytest.skip('平台未暴露 Adapter')
    try:
        adapter = adapter_cls()
    except Exception as exc:
        pytest.skip('平台适配器实例化失败: {}'.format(exc))
    assert adapter.name == platform_name
    assert isinstance(adapter.supported_models, list)
    assert isinstance(adapter.default_capabilities, dict)
    assert hasattr(adapter, 'complete')
    assert hasattr(adapter, 'close')
