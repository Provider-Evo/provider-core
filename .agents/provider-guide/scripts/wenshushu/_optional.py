# -*- coding: utf-8 -*-
"""可选导入工具模块。

提供 ``_optional_import`` 函数,用于在第三方依赖缺失时返回代理对象,
访问代理对象的任何属性时抛出包含 ``pip install`` 指引的 ImportError。
"""
from __future__ import annotations

from typing import Any


def _optional_import(module: str, pip_name: str = "") -> Any:
    """尝试导入模块,缺失时返回代理对象,访问任何属性抛出含 pip install 指引的 ImportError。

    Args:
        module: 模块导入路径。
        pip_name: pip 包名,为空时使用 module 的顶层名称。

    Returns:
        导入的模块或代理对象。

    >>> proxy = _optional_import("nonexistent_module_xyz", "nonexistent-pkg")
    >>> try:
    ...     proxy.something
    ... except ImportError as e:
    ...     "pip install" in str(e)
    True
    """
    try:
        import importlib
        return importlib.import_module(module)
    except ImportError:
        _pip = pip_name or module.split(".")[0]

        class _Proxy:
            def __getattr__(self, name: str) -> Any:
                raise ImportError(
                    f"模块 '{module}' 未安装。请执行: pip install {_pip}"
                )
        return _Proxy()
