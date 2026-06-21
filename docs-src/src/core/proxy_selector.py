from __future__ import annotations

"""代理选择器重导出模块。

规范实现位于 ``echotools.dispatch.proxy_selector``。
此模块仅为保持向后兼容的导入路径而存在：

.. code-block:: python

    # 以下两种导入均可用，语义完全相同
    from core.proxy_selector import ProxySelector, ProxyRecord
    from echotools.dispatch.proxy_selector import ProxySelector, ProxyRecord

导出符号
--------
- :class:`ProxySelector` — 代理选择器，负责从候选代理池中按策略
  选择最优代理，支持轮询、加权、健康检测等策略。
- :class:`ProxyRecord` — 代理记录数据类，封装单个代理的地址、
  权重、健康状态等元信息。

使用示例
--------
.. code-block:: python

    from core.proxy_selector import ProxySelector, ProxyRecord

    proxies = [
        ProxyRecord(url="http://proxy1:8080", weight=1),
        ProxyRecord(url="http://proxy2:8080", weight=2),
    ]
    selector = ProxySelector(proxies)
    best = selector.select()
    print(best.url)

迁移说明
--------
若未来 ``echotools`` 迁移或重命名了 ``ProxySelector``/``ProxyRecord``，
只需修改此文件的 import 路径，项目内所有 ``from core.proxy_selector``
的调用方无需任何修改。
"""

from echotools.dispatch.proxy_selector import (  # noqa: F401
    ProxyRecord,
    ProxySelector,
)

__all__ = [
    "ProxySelector",
    "ProxyRecord",
]
