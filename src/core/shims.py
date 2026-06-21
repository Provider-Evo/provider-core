from __future__ import annotations

"""向后兼容 shim 集合。

将原先散落在 16 个独立文件中的所有单行 shim 集中到此处统一管理。
外部代码通过 ``from core.xxx import yyy`` 形式导入时，由各个原始
模块名对应的属性访问路径保持不变；``core/__init__.py`` 同时将本模
块的所有符号提升到包级别，确保 ``from core import yyy`` 也持续有效。

原始文件映射关系
----------------

服务器相关
~~~~~~~~~~
- ``core/autoupdate.py``   -> ``src.core.server.autoupdate``
- ``core/http.py``         -> ``src.core.server.http``
- ``core/process.py``      -> ``src.core.server.process``
- ``core/proxy.py``        -> ``src.core.server.proxy``
- ``core/server.py``       -> ``src.core.server.server``
- ``core/watcher.py``      -> ``src.core.server.watcher``

调度相关
~~~~~~~~
- ``core/candidate.py``    -> ``src.core.dispatch.candidate``
- ``core/gateway.py``      -> ``src.core.dispatch.gateway``
- ``core/registry.py``     -> ``src.core.dispatch.registry``
- ``core/runtime_view.py`` -> ``src.core.dispatch.runtime_view``
- ``core/selector.py``     -> ``src.core.dispatch.selector``

工具函数相关
~~~~~~~~~~~~
- ``core/files.py``        -> ``src.core.utils.files``
- ``core/ids.py``          -> ``src.core.utils.ids``
- ``core/io_utils.py``     -> ``src.core.utils.io_utils``
- ``core/retry.py``        -> ``src.core.utils.retry``
- ``core/scheduler.py``    -> ``src.core.utils.scheduler``

错误处理相关
~~~~~~~~~~~~
- ``core/errors.py``       -> ``src.core.errors.{base,platform,business}``
                              + ``src.core.errors.classify_http_error``

代理选择器
~~~~~~~~~~
- ``core/proxy_selector.py`` -> ``echotools.dispatch.proxy_selector``

设计原则
--------
1. 此文件只做重导出，不包含任何业务逻辑。
2. 所有 ``*`` 导入均附带 ``noqa`` 注释，lint 工具不会误报。
3. 新增底层实现时，只需在对应子包的 ``__all__`` 中声明，
   此文件无需修改即可自动透传。
4. 若未来某个子模块迁移了实现路径，只需修改此文件中对应的
   一行 import，所有调用方无感知。

使用示例
--------
以下三种导入方式均等价，均受此文件支持：

.. code-block:: python

    # 方式 1：从 core 包直接导入
    from core import some_function

    # 方式 2：从 core.shims 导入（不推荐，但可用）
    from core.shims import some_function

    # 方式 3：从原始路径导入（绕过 shim，直接访问实现）
    from src.core.server import some_function
"""

# ==============================================================================
# 服务器相关
# ==============================================================================

from src.core.server import *  # noqa: F401, F403

# ==============================================================================
# 调度相关
# ==============================================================================

from src.core.dispatch.candidate import *  # noqa: F401, F403
from src.core.dispatch.gateway import *  # noqa: F401, F403
from src.core.dispatch.registry import *  # noqa: F401, F403
from src.core.dispatch.runtime_view import *  # noqa: F401, F403
from src.core.dispatch.selector import *  # noqa: F401, F403

# ==============================================================================
# 工具函数相关
# ==============================================================================

from src.core.utils.files import *  # noqa: F401, F403
from src.core.utils.ids import *  # noqa: F401, F403
from src.core.utils.io_utils import *  # noqa: F401, F403
from src.core.utils.retry import *  # noqa: F401, F403
from src.core.utils.scheduler import *  # noqa: F401, F403

# ==============================================================================
# 错误处理相关
# ==============================================================================

from src.core.errors.base import *  # noqa: F401, F403
from src.core.errors.platform import *  # noqa: F401, F403
from src.core.errors.business import *  # noqa: F401, F403
from src.core.errors import classify_http_error  # noqa: F401

# ==============================================================================
# 代理选择器（来自 echotools）
# ==============================================================================

from echotools.dispatch.proxy_selector import ProxyRecord  # noqa: F401
from echotools.dispatch.proxy_selector import ProxySelector  # noqa: F401

# ==============================================================================
# 显式 __all__：聚合所有已知的具名导出，供 IDE 和静态分析工具使用
# ==============================================================================
# 注意：通配符导入已覆盖大部分符号；此处仅列出可静态确定的具名符号。
# 子模块通过 __all__ 动态贡献的符号无需在此重复声明。

__all__ = [
    # 代理选择器
    "ProxySelector",
    "ProxyRecord",
    # 错误处理（具名导入部分）
    "classify_http_error",
]
