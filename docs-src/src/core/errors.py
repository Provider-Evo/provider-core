from __future__ import annotations

"""错误处理向后兼容 shim。

项目错误体系的规范实现已迁移至 ``src.core.errors`` 包，拆分为三个
子模块以实现关注点分离：

- ``src.core.errors.base``      — 基础异常类与通用错误工具
- ``src.core.errors.platform``  — 平台相关错误（如第三方 API 错误码映射）
- ``src.core.errors.business``  — 业务逻辑错误（如参数校验、权限不足）

此文件保留为向后兼容的单入口，确保以下导入路径持续有效：

.. code-block:: python

    # 以下导入均受支持，无需修改
    from core.errors import SomeException
    from core.errors import classify_http_error
    import core.errors

导出结构
--------
通过三个 ``*`` 导入将子模块的所有公共符号提升到 ``core.errors`` 命名空间：

.. code-block:: text

    core.errors
    ├── * from src.core.errors.base       (基础异常、错误工具)
    ├── * from src.core.errors.platform   (平台错误映射)
    ├── * from src.core.errors.business   (业务错误)
    └── classify_http_error               (HTTP 错误分类函数，具名导入)

``classify_http_error`` 采用显式具名导入而非通配符，原因：

1. 该函数是跨层通用工具，需确保在静态分析工具中可见。
2. 避免因 ``src.core.errors.__init__`` 的 ``__all__`` 变化导致
   该函数意外消失。

维护指南
--------
- 新增错误类时，在对应子模块（base/platform/business）中定义并
  添加到其 ``__all__``，此文件无需修改即可自动透传。
- 若需要将某个符号从 ``core.errors`` 移除，应在子模块的 ``__all__``
  中移除，而非修改此 shim。
- 不要在此文件中添加任何业务逻辑或新的异常类定义。
"""

from src.core.errors.base import *  # noqa: F401, F403
from src.core.errors.platform import *  # noqa: F401, F403
from src.core.errors.business import *  # noqa: F401, F403
from src.core.errors import classify_http_error  # noqa: F401
