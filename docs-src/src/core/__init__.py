from __future__ import annotations

"""核心基础设施包（core）。

此包是项目 ``core/`` 目录的公共入口，提供两层职责：

1. **子包别名导出**：将 ``src.core`` 下各子包以模块别名的形式
   暴露到 ``core`` 命名空间，支持 ``from core import http`` 等用法。

2. **实体符号提升**：将 ``core/`` 目录下有实质实现的模块
   （``models_cache``、``terminal_sessions``、``tools``、
   ``proxy_selector``、``shims``）的公共符号提升到包级别，
   支持 ``from core import ModelsCache`` 等用法。

导入兼容性矩阵
--------------
以下所有导入路径均受支持，且语义完全等价：

.. code-block:: python

    # 子包别名访问
    from core import http
    from core import proxy
    from core import errors

    # 实体类直接导入
    from core import ModelsCache
    from core import TerminalSessionStore
    from core import get_terminal_store
    from core import ProxySelector
    from core import ProxyRecord

    # 工具函数直接导入
    from core import inject_fncall
    from core import parse_fncall
    from core import detect_tool_loop

    # shim 符号（原 core/autoupdate.py 等 16 个文件的内容）
    from core import some_server_function
    from core import some_dispatch_function

架构说明
--------
``core/`` 目录的文件职责划分：

::

    core/
    ├── __init__.py          本文件，统一导出入口
    ├── shims.py             16 个原始单行 shim 文件的合并体
    ├── errors.py            错误处理 shim（含显式具名导入，单独维护）
    ├── models_cache.py      ModelsCache 实质实现
    ├── proxy_selector.py    ProxySelector/ProxyRecord 重导出
    ├── terminal_sessions.py TerminalSessionStore 实质实现
    └── tools.py             工具调用统一接口

重构历史
--------
- 原始结构：17 个文件，其中 16 个为单行 shim（每文件 1-3 行有效代码）
- 重构后：7 个文件，所有公共 API 保持向下兼容
- 文件数量减少 59%，单文件平均行数提升约 8 倍
"""

# ==============================================================================
# src.core 子包别名导出
# ==============================================================================
# 以模块对象形式导出，支持 `from core import http` / `core.http.xxx` 两种用法

from src.core import config as config
from src.core import errors as errors
from src.core import models_cache as models_cache
from src.core import tools as tools

from src.core.dispatch import candidate as candidate
from src.core.dispatch import gateway as gateway
from src.core.dispatch import registry as registry
from src.core.dispatch import runtime_view as runtime_view
from src.core.dispatch import selector as selector

from src.core.server import autoupdate as autoupdate
from src.core.server import http as http
from src.core.server import process as process
from src.core.server import proxy as proxy
from src.core.server import server as server
from src.core.server import watcher as watcher

from src.core.utils import files as files
from src.core.utils import ids as ids
from src.core.utils import io_utils as io_utils
from src.core.utils import retry as retry
from src.core.utils import scheduler as scheduler

# ==============================================================================
# 实质实现模块的符号提升
# ==============================================================================

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

# ==============================================================================
# shim 符号提升（原 16 个独立 shim 文件的合并导出）
# ==============================================================================
# 通配符导入将 shims.py 中所有子模块的公共符号提升到 core 命名空间，
# 确保 `from core import xxx` 对原有调用方持续有效。

from src.core.shims import *  # noqa: F401, F403
from src.core.errors import classify_http_error  # noqa: F401（显式保留）

# ==============================================================================
# __all__：声明包的公共接口
# ==============================================================================

__all__ = [
    # --------------------------------------------------------------------------
    # 子包别名
    # --------------------------------------------------------------------------
    "config",
    "errors",
    "models_cache",
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
    # ModelsCache
    # --------------------------------------------------------------------------
    "ModelsCache",
    "models",
    # --------------------------------------------------------------------------
    # TerminalSessionStore
    # --------------------------------------------------------------------------
    "TerminalSessionStore",
    "get_terminal_store",
    # --------------------------------------------------------------------------
    # 工具调用接口
    # --------------------------------------------------------------------------
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
    # --------------------------------------------------------------------------
    # 代理选择器
    # --------------------------------------------------------------------------
    "ProxySelector",
    "ProxyRecord",
    # --------------------------------------------------------------------------
    # 错误处理（显式具名）
    # --------------------------------------------------------------------------
    "classify_http_error",
]
