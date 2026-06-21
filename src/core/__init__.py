from __future__ import annotations

"""核心基础设施包（core）。

向下兼容层：通过模块对象导出和符号提升，保持所有原有导入路径有效。

重构说明
--------
- ``src/core/server/`` 目录已合并为单个 ``src/core/server.py`` 文件
- ``src/core/`` 下散落的 17 个 shim 文件已合并为 7 个文件
- 所有公共 API 通过本 ``__init__.py`` 保持向下兼容

导入方式（推荐优先级从高到低）
------------------------------

1. **完整路径导入**（最明确，类型检查友好）：

   .. code-block:: python

       from src.core.dispatch.registry import Registry
       from src.core.server import create_app, FileWatcher

2. **包级别符号导入**（简洁）：

   .. code-block:: python

       from src.core import Registry, create_app, FileWatcher

3. **模块对象导入**（适合有命名冲突时）：

   .. code-block:: python

       from src.core import registry, server
       reg = registry.Registry()
       app = await server.create_app(...)
"""

# ==============================================================================
# 1. 导入子包模块对象
# ==============================================================================

from src.core import config
from src.core import errors
from src.core import models_cache
from src.core import proxy_selector
from src.core import server  # 单文件模块，不再是包
from src.core import shims
from src.core import terminal_sessions
from src.core import tools

from src.core.dispatch import candidate
from src.core.dispatch import gateway
from src.core.dispatch import registry
from src.core.dispatch import runtime_view
from src.core.dispatch import selector

from src.core.utils import files
from src.core.utils import ids
from src.core.utils import io_utils
from src.core.utils import retry
from src.core.utils import scheduler

# ==============================================================================
# 2. 提升常用符号到包级别
# ==============================================================================

# --- config 子包 ---
from src.core.config import get_config, start_config_watcher

# --- dispatch 子包 ---
from src.core.dispatch.candidate import Candidate
from src.core.dispatch.gateway import dispatch
from src.core.dispatch.registry import Registry
from src.core.dispatch.runtime_view import build_runtime_summary
from src.core.dispatch.selector import Selector

# --- server 模块（已从包合并为单文件）---
from src.core.server import (
    AutoUpdater,
    FileWatcher,
    REGISTRY_KEY,
    SESSION_KEY,
    activate,
    clean_fncall,
    create_app,
    deactivate,
    get_json,
    get_proxy_dict,
    get_proxy_server,
    get_updater,
    is_active,
    json_response,
    safe_flush,
    set_updater,
)

# --- utils 子包 ---
from src.core.utils.retry import retry_with_backoff

# --- 本地模块（src/core/ 下的 7 个 .py 文件）---
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
from src.core.errors import classify_http_error

# --- shims 通配符导入（透传所有子模块符号）---
from src.core.shims import *  # noqa: F401, F403

# ==============================================================================
# __all__：声明包的公共接口
# ==============================================================================

__all__ = [
    # --------------------------------------------------------------------------
    # 子包/模块对象
    # --------------------------------------------------------------------------
    "config",
    "errors",
    "models_cache",
    "proxy_selector",
    "server", 
    "shims",
    "terminal_sessions",
    "tools",
    "candidate",
    "gateway",
    "registry",
    "runtime_view",
    "selector",
    "files",
    "ids",
    "io_utils",
    "retry",
    "scheduler",
    # --------------------------------------------------------------------------
    # config 符号
    # --------------------------------------------------------------------------
    "get_config",
    "start_config_watcher",
    # --------------------------------------------------------------------------
    # dispatch 符号
    # --------------------------------------------------------------------------
    "Candidate",
    "dispatch",
    "Registry",
    "build_runtime_summary",
    "Selector",
    # --------------------------------------------------------------------------
    # server 符号（从单文件模块导入）
    # --------------------------------------------------------------------------
    "AutoUpdater",
    "FileWatcher",
    "REGISTRY_KEY",
    "SESSION_KEY",
    "activate",
    "clean_fncall",
    "create_app",
    "deactivate",
    "get_json",
    "get_proxy_dict",
    "get_proxy_server",
    "get_updater",
    "is_active",
    "json_response",
    "safe_flush",
    "set_updater",
    # --------------------------------------------------------------------------
    # utils 符号
    # --------------------------------------------------------------------------
    "retry_with_backoff",
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
