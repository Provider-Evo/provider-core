"""models_cache 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 models_cache 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import List, Optional

from echotools.cache.list_cache import ListCache
from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir as _persist_dir

__all__ = ["ModelsCache", "models"]

logger = get_logger(__name__)

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
        cache_path = str(_persist_dir(platform) / "models.json") if platform else ""
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
