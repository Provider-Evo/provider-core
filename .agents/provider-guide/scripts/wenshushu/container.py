# -*- coding: utf-8 -*-
"""依赖注入容器与配置管理模块。

提供 Container (IoC 容器) 和 Config (统一配置) 两个核心类,
用于组装应用各组件并管理运行时配置。
"""
from __future__ import annotations

import dataclasses
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable

from .exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# 文叔叔相关常量（Config 默认值引用）
# ---------------------------------------------------------------------------
WSS_BASE_URL = "https://www.wenshushu.cn"
WSS_CHUNK_SIZE = 2097152  # 2 MiB
WSS_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) "
    "Gecko/20100101 Firefox/82.0"
)

# 上传线程池大小
UPLOAD_MAX_WORKERS = 4


# ===========================================================================
# Container 依赖注入容器
# ===========================================================================

class Container:
    """依赖注入容器。

    >>> c = Container()
    >>> c.instance(str, "hello").resolve(str)
    'hello'
    """

    def __init__(self) -> None:
        self._singletons: dict[type | str, Callable] = {}
        self._factories: dict[type | str, Callable] = {}
        self._instances: dict[type | str, Any] = {}
        self._singleton_cache: dict[type | str, Any] = {}
        self._lock = threading.Lock()

    def singleton(self, interface: type | str, factory: Callable[..., Any]) -> Container:
        """注册单例工厂。

        Args:
            interface: 接口类型或名称。
            factory: 工厂函数。

        Returns:
            自身。
        """
        self._singletons[interface] = factory
        return self

    def factory(self, interface: type | str, factory: Callable[..., Any]) -> Container:
        """注册工厂(每次创建新实例)。

        Args:
            interface: 接口类型或名称。
            factory: 工厂函数。

        Returns:
            自身。
        """
        self._factories[interface] = factory
        return self

    def instance(self, interface: type | str, existing_obj: Any) -> Container:
        """注册已有实例。

        Args:
            interface: 接口类型或名称。
            existing_obj: 已有对象。

        Returns:
            自身。
        """
        self._instances[interface] = existing_obj
        return self

    def resolve(self, interface: type | str) -> Any:
        """解析依赖。

        Args:
            interface: 接口类型或名称。

        Returns:
            解析到的对象。

        Raises:
            ConfigurationError: 未注册时。
        """
        # 实例优先
        if interface in self._instances:
            return self._instances[interface]
        # 单例
        if interface in self._singletons:
            with self._lock:
                if interface not in self._singleton_cache:
                    self._singleton_cache[interface] = self._singletons[interface](self)
                return self._singleton_cache[interface]
        # 工厂
        if interface in self._factories:
            return self._factories[interface](self)
        raise ConfigurationError(
            f"依赖 '{interface}' 未注册",
            context={"interface": str(interface)},
        )

    def build(self) -> Container:
        """构建容器(当前为空操作,预留扩展)。

        Returns:
            自身。
        """
        return self


# ===========================================================================
# Config 统一配置
# ===========================================================================

@dataclass
class Config:
    """统一配置,支持: 默认值 < 环境变量 < CLI 参数 覆盖链。

    Attributes:
        log_level: 日志级别名称。
        log_file: 日志文件路径。
        chunk_size: 上传分块大小(字节)。
        max_workers: 上传线程池大小。
        base_url: 文叔叔基础 URL。
        user_agent: HTTP User-Agent。

    >>> c = Config()
    >>> c.chunk_size == WSS_CHUNK_SIZE
    True
    """

    log_level: str = "INFO"
    log_file: str | None = None
    chunk_size: int = WSS_CHUNK_SIZE
    max_workers: int = UPLOAD_MAX_WORKERS
    base_url: str = WSS_BASE_URL
    user_agent: str = WSS_DEFAULT_USER_AGENT

    @classmethod
    def from_env(cls, prefix: str = "WSS_") -> Config:
        """从环境变量加载配置。

        Args:
            prefix: 环境变量前缀。

        Returns:
            Config 实例。
        """
        kwargs: dict[str, Any] = {}
        env_map: dict[str, tuple[str, type]] = {
            "LOG_LEVEL": ("log_level", str),
            "LOG_FILE": ("log_file", str),
            "CHUNK_SIZE": ("chunk_size", int),
            "MAX_WORKERS": ("max_workers", int),
            "BASE_URL": ("base_url", str),
            "USER_AGENT": ("user_agent", str),
        }
        for env_suffix, (attr_name, attr_type) in env_map.items():
            val = os.environ.get(f"{prefix}{env_suffix}")
            if val is not None:
                try:
                    kwargs[attr_name] = attr_type(val)
                except (ValueError, TypeError):
                    pass
        return cls(**kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """从字典创建配置。

        Args:
            data: 配置字典。

        Returns:
            Config 实例。
        """
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def override(self, **kwargs: Any) -> Config:
        """链式覆盖配置项,返回新实例。

        Args:
            **kwargs: 要覆盖的配置项。

        Returns:
            新的 Config 实例。
        """
        current = dataclasses.asdict(self)
        current.update(kwargs)
        return Config.from_dict(current)

    def validate(self) -> None:
        """校验配置有效性。

        Raises:
            ConfigurationError: 配置无效时。
        """
        if self.chunk_size <= 0:
            raise ConfigurationError("chunk_size 必须为正整数", context={"chunk_size": self.chunk_size})
        if self.max_workers <= 0:
            raise ConfigurationError("max_workers 必须为正整数", context={"max_workers": self.max_workers})
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            raise ConfigurationError(
                f"无效的日志级别: {self.log_level}",
                context={"log_level": self.log_level, "valid": list(valid_levels)},
            )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            配置字典。
        """
        return dataclasses.asdict(self)
