from __future__ import annotations

"""ModelsCache — 模型列表缓存，复用 echotools.ListCache。

此模块提供两个公共符号：

* :class:`ModelsCache` — 封装 ``echotools.cache.list_cache.ListCache``，
  保持项目原有的 ``ModelsCache`` API 不变。
* :func:`models` — 返回全局单例 ``ModelsCache``，供无需自定义配置的
  调用方快速获取当前模型列表。

存储结构
--------
缓存文件保存于项目根目录下的 ``persist/`` 子目录：

::

    persist/
        {platform}/
            models.json      -- JSON 格式的模型列表缓存

JSON 文件结构
-------------
::

    {
        "models": ["model-a", "model-b", ...]
    }

设计说明
--------
- ``ModelsCache`` 继承自 ``ListCache``，所有 ``ListCache`` 的公共方法
  均可直接使用，无需额外封装。
- ``models`` 属性是对 ``ListCache.items`` 的别名，保持原始 API 兼容。
- ``fetch_enabled=False`` 时，``ListCache`` 不会覆盖已有缓存，适用于
  离线场景或需要固定模型列表的测试环境。
- 全局单例 ``_cache`` 在首次调用 :func:`models` 时以空配置初始化，
  适合快速访问而无需关心具体平台的场景。

使用示例
--------
.. code-block:: python

    # 场景 1：为特定平台创建缓存
    cache = ModelsCache(
        platform="openai",
        fallback_models=["gpt-4o", "gpt-4o-mini"],
        fetch_enabled=True,
    )
    print(cache.models)   # ['gpt-4o', 'gpt-4o-mini', ...]

    # 场景 2：使用全局单例（空配置，仅读取已有缓存）
    from core.models_cache import models
    print(models().items)

    # 场景 3：禁用拉取，只使用兜底列表
    offline_cache = ModelsCache(
        platform="anthropic",
        fallback_models=["claude-3-5-sonnet-20241022"],
        fetch_enabled=False,
    )

兼容性说明
----------
此模块保持与原始 ``core/models_cache.py`` 完全相同的公共 API：

* ``ModelsCache(platform, fallback_models, fetch_enabled)``
* ``ModelsCache.models`` 属性
* ``models()`` 工厂函数
"""

from pathlib import Path
from typing import List, Optional

from echotools.cache.list_cache import ListCache
from src.logger import get_logger

__all__ = ["ModelsCache", "models"]

logger = get_logger(__name__)

# 缓存根目录：<project_root>/persist/
_PERSIST_ROOT: Path = Path(__file__).resolve().parent.parent.parent / "persist"

# 模块级全局单例，首次调用 models() 时初始化。
_cache: Optional["ModelsCache"] = None


class ModelsCache(ListCache):
    """模型列表缓存，封装 ``echotools.ListCache``。

    通过继承 ``ListCache`` 复用其文件 I/O、JSON 解析、兜底逻辑等
    基础能力，同时暴露项目惯用的 ``models`` 属性接口。

    Parameters
    ----------
    platform:
        平台标识字符串，例如 ``"openai"``、``"anthropic"``。
        用于：

        1. 作为 ``ListCache`` 的 ``name`` 参数。
        2. 确定缓存文件路径：``persist/{platform}/models.json``。

    fallback_models:
        当缓存文件不存在或拉取失败时使用的兜底模型列表。
        必须为非空列表，否则 ``ListCache`` 可能返回空结果。

    fetch_enabled:
        是否允许在初始化时覆盖写入缓存文件。
        传递给 ``ListCache`` 的 ``overwrite`` 参数：

        - ``True``（默认）：允许覆盖，适合生产环境动态拉取。
        - ``False``：禁止覆盖，适合离线或测试环境。

    Attributes
    ----------
    models:
        当前模型列表，等价于 ``ListCache.items``。
        只读属性，不可直接赋值。

    Examples
    --------
    >>> cache = ModelsCache("openai", ["gpt-4o"])
    >>> isinstance(cache.models, list)
    True
    >>> cache.models[0]
    'gpt-4o'
    """

    def __init__(
        self,
        platform: str,
        fallback_models: List[str],
        fetch_enabled: bool = True,
    ) -> None:
        cache_path = str(_PERSIST_ROOT / platform / "models.json") if platform else ""
        super().__init__(
            name=platform,
            fallback=fallback_models,
            cache_path=cache_path,
            overwrite=fetch_enabled,
            data_key="models",
        )
        logger.debug(
            "ModelsCache 初始化完成: platform=%r, fetch_enabled=%r, cache_path=%r",
            platform,
            fetch_enabled,
            cache_path,
        )

    @property
    def models(self) -> List[str]:
        """当前模型列表（兼容原始 API）。

        Returns
        -------
        List[str]
            ``ListCache.items`` 的直接引用，反映最新缓存状态。
        """
        return self.items


def models() -> "ModelsCache":
    """获取全局 ModelsCache 单例。

    首次调用时以空平台配置初始化（``platform=""``、``fallback_models=[]``），
    后续调用始终返回同一实例。

    此函数适用于无需关心具体平台、只需快速访问已有缓存的场景。
    若需要为特定平台创建独立缓存，请直接实例化 :class:`ModelsCache`。

    Returns
    -------
    ModelsCache
        模块级全局单例。

    Examples
    --------
    >>> store = models()
    >>> isinstance(store, ModelsCache)
    True
    """
    global _cache
    if _cache is None:
        _cache = ModelsCache(platform="", fallback_models=[])
        logger.debug("全局 ModelsCache 单例已创建")
    return _cache
