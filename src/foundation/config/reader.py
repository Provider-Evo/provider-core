

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.foundation.logger import get_logger

logger = get_logger(__name__)

__all__ = ["ConfigReader", "get_config_reader", "load_plugin_api_keys"]


def _import_tomllib():  # type: ignore[no-untyped-def]
    """兼容 Python 3.11+ tomllib / 3.10 tomli。"""
    try:
        import tomllib  # type: ignore[import-untyped]
        return tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-untyped]
            return tomllib
        except ImportError:
            return None


def _import_tomlkit():  # type: ignore[no-untyped-def]
    """尝试导入 tomlkit（保留注释格式）。"""
    try:
        import tomlkit  # type: ignore[import-untyped]
        return tomlkit
    except ImportError:
        return None


class ConfigReader:
    """统一配置读取接口。

    提供三种读取方式：
    - ``get_raw_toml(path)``：读取 TOML 文件为 dict（替代各处 tomllib 直读）
    - ``get_plugin_config(plugin_path)``：读取插件 config.toml + config_schema.json
    - ``get_server_config()``：获取当前 AppConfig（委托 get_config）
    """

    def get_server_config(self) -> Any:
        """获取当前服务端配置（AppConfig）。"""
        from src.foundation.config import get_config
        return get_config()

    def get_raw_toml(self, path: Path) -> Dict[str, Any]:
        """读取 TOML 文件为 dict。

        替代各处 ``import tomllib; tomllib.load(f)`` 的重复模式。
        优先使用 tomlkit（保留注释），回退 tomllib。
        """
        if not path.is_file():
            return {}

        tomlkit = _import_tomlkit()
        if tomlkit is not None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return dict(tomlkit.loads(f.read()))
            except Exception as exc:
                logger.debug("tomlkit 读取 %s 失败，回退 tomllib: %s", path, exc)

        tomllib = _import_tomllib()
        if tomllib is not None:
            try:
                with open(path, "rb") as f:
                    return dict(tomllib.load(f))
            except Exception as exc:
                logger.debug("tomlkit 读取 %s 失败: %s", path, exc)

        logger.warning("无可用 TOML 库（tomlkit/tomllib），无法读取 %s", path)
        return {}

    def get_plugin_config(
        self, plugin_path: Path
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """读取插件配置：config.toml + config_schema.json + 原始文本。

        返回 ``(config_dict, schema_dict, raw_toml_text)``。
        替代 ``_read_plugin_config_files()`` 的重复实现。
        """
        config_path = plugin_path / "config.toml"
        schema_path = plugin_path / "config_schema.json"

        config: Dict[str, Any] = {}
        if config_path.is_file():
            config = self.get_raw_toml(config_path)

        schema: Dict[str, Any] = {}
        if schema_path.is_file():
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("读取 %s 失败: %s", schema_path, exc)

        raw_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
        return config, schema, raw_text


def load_plugin_api_keys(
    plugin_path: Path,
    accounts_keys: Optional[list] = None,
    config_key: str = "api_keys",
) -> list:
    """合并 accounts.py 与 config.toml 中的 API Key 列表。

    accounts_keys 非空时优先；否则回退到 config.toml[config_key]。
    """
    keys = []
    if accounts_keys:
        keys = [str(k).strip() for k in accounts_keys if k and str(k).strip()]
    if keys:
        return keys
    config, _, _ = get_config_reader().get_plugin_config(plugin_path)
    raw = config.get(config_key, [])
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(k).strip() for k in raw if k and str(k).strip()]
    return []


_reader: Optional[ConfigReader] = None


def get_config_reader() -> ConfigReader:
    """获取全局 ConfigReader 单例。"""
    global _reader
    if _reader is None:
        _reader = ConfigReader()
    return _reader
