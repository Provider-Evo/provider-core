from __future__ import annotations

"""核心基础设施包（core）。

此包是 ``src/core/`` 的公共入口，提供两层职责：

1. **子包模块对象导出**：将子包以模块对象形式暴露，
   支持 ``from src.core import registry`` 访问模块对象。

2. **常用符号提升**：将子包中常用的类/函数提升到包级别，
   支持 ``from src.core import Registry`` 等用法。

导入兼容性
----------
重构前后均支持的导入路径：

.. code-block:: python

    # 类/函数直接导入（推荐）
    from src.core import Registry
    from src.core import create_app
    from src.core import FileWatcher

    # 模块对象导入
    from src.core import registry
    from src.core import server

    # 子模块导入（显式路径）
    from src.core.dispatch.registry import Registry
    from src.core.server.server import create_app

架构说明
--------
``src/core/`` 目录结构（重构后）：

::

    src/core/
    ├── __init__.py          本文件，统一导出
    ├── shims.py             16 个原始 shim 文件的合并体
    ├── errors.py            错误处理 shim
    ├── models_cache.py      ModelsCache 实质实现
    ├── proxy_selector.py    ProxySelector/ProxyRecord 重导出
    ├── terminal_sessions.py TerminalSessionStore 实质实现
    ├── tools.py             工具调用统一接口
    ├── config/              配置管理子包
    ├── dispatch/            调度子包
    │   ├── candidate.py
    │   ├── gateway.py
    │   ├── registry.py
    │   └── ...
    ├── server/              服务器子包
    │   ├── autoupdate.py
    │   ├── http.py
    │   ├── server.py
    │   └── ...
    └── utils/               工具函数子包
        ├── files.py
        └── ...
"""

# ==============================================================================
# 1. 导入子包模块对象（模块别名导出）
# ==============================================================================

# config 子包
from src.core import config

# 本目录下的重构文件（7 个 .py 文件）
from src.core import errors
from src.core import models_cache
from src.core import proxy_selector
from src.core import shims
from src.core import terminal_sessions
from src.core import tools

# dispatch 子包
from src.core.dispatch import candidate
from src.core.dispatch import gateway
from src.core.dispatch import registry
from src.core.dispatch import runtime_view
from src.core.dispatch import selector

# server 子包
from src.core.server import autoupdate
from src.core.server import http
from src.core.server import process
from src.core.server import proxy
from src.core.server import server
from src.core.server import watcher

# utils 子包
from src.core.utils import files
from src.core.utils import ids
from src.core.utils import io_utils
from src.core.utils import retry
from src.core.utils import scheduler

# ==============================================================================
# 2. 提升常用符号到包级别（向下兼容原有导入路径）
# ==============================================================================

# --- config 子包 ---
from src.core.config import get_config, start_config_watcher

# --- dispatch 子包 ---
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.gateway import dispatch
from src.core.dispatch.registry import Registry
from src.core.dispatch.runtime_view import build_runtime_summary
from src.core.dispatch.selector import Selector

# --- server 子包 ---
from src.core.server.autoupdate import AutoUpdater
from src.core.server.http import http_request, stream_request
from src.core.server.server import create_app
from src.core.server.watcher import FileWatcher

# --- utils 子包 ---
from src.core.utils.retry import with_retry

# --- 重构后的本地模块 ---
from src.core.models_cache import ModelsCache, models
from src.core.terminal_sessions import TerminalSessionStore, get_terminal_store
from src.core.tools import (
    FncallStreamParser,
    LoopDetectionResult,
    ToolProtocol,
    detect_tool_loop,
    format_tool_descs,
    get_protocol,
    inject_fncall,
    normalize_content,
    parse_fncall,
    parse_fncall_xml,
)
from src.core.proxy_selector import ProxyRecord, ProxySelector

# --- errors 子包符号 ---
from src.core.errors import classify_http_error

# --- shims 通配符导入（包含所有子模块的公共符号）---
from src.core.shims import *  # noqa: F401, F403

# ==============================================================================
# __all__：声明包的公共接口
# ==============================================================================

__all__ = [
    # --------------------------------------------------------------------------
    # 子包模块对象
    # --------------------------------------------------------------------------
    "config",
    "errors",
    "models_cache",
    "proxy_selector",
    "shims",
    "terminal_sessions",
    "tools",
    "candidate",
    "gateway",
    "registry",
    "runtime_view",
    "selector",
    "autoupdate",
    "http",
    "process",
    "proxy",
    "server",
    "watcher",
    "files",
    "ids",
    "io_utils",
    "retry",
    "scheduler",
    # --------------------------------------------------------------------------
    # config 子包常用符号
    # --------------------------------------------------------------------------
    "get_config",
    "start_config_watcher",
    # --------------------------------------------------------------------------
    # dispatch 子包常用符号
    # --------------------------------------------------------------------------
    "Candidate",
    "dispatch",
    "Registry",
    "build_runtime_summary",
    "Selector",
    # --------------------------------------------------------------------------
    # server 子包常用符号
    # --------------------------------------------------------------------------
    "AutoUpdater",
    "http_request",
    "stream_request",
    "create_app",
    "FileWatcher",
    # --------------------------------------------------------------------------
    # utils 子包常用符号
    # --------------------------------------------------------------------------
    "with_retry",
    # --------------------------------------------------------------------------
    # 本地模块符号
    # --------------------------------------------------------------------------
    "ModelsCache",
    "models",
    "TerminalSessionStore",
    "get_terminal_store",
    "inject_fncall",
    "parse_fncall",
    "parse_fncall_xml",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "detect_tool_loop",
    "LoopDetectionResult",
    "ToolProtocol",
    "get_protocol",
    "ProxySelector",
    "ProxyRecord",
    "classify_http_error",
]
