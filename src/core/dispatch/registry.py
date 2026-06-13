from __future__ import annotations

#src/core/registry.py

import asyncio
import importlib
import pkgutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.config import get_config
from src.core.dispatch.selector import Selector
from src.logger import get_logger
from src.platforms.base import PlatformAdapter

__all__ = ["Registry"]
logger = get_logger(__name__)

_PERSIST_ROOT = Path(__file__).parent.parent.parent / "persist"


class Registry:
    """平台注册表。

    初始化策略：
    1. 递归发现 src.platforms 下所有平台适配器
    2. 立即调用 adapter.init()（适配器内部立即返回）
    3. 注册到表中，服务立即可用
    4. 各平台后台 Task 完成登录/token 刷新/模型拉取后实时更新候选项
    """

    def __init__(self) -> None:
        """初始化注册表。"""
        self._adapters: Dict[str, Any] = {}
        self.selector = Selector(
            persist_dir=str(_PERSIST_ROOT / "gateway")
        )

    def _is_adapter_class(self, attr: Any) -> bool:
        """判断一个对象是否像平台适配器类。

        说明：
        - 兼容两种情况：
          1. 严格继承 PlatformAdapter 的类
          2. 仅实现 required interface 的类
        - 这样可以兼容现有 deepseek 目录结构的最小改动方案

        Args:
            attr: 待判断对象。

        Returns:
            是否为适配器类。
        """
        if not isinstance(attr, type):
            return False
        if attr is PlatformAdapter:
            return False

        module_name = getattr(attr, "__module__", "")
        if not module_name.startswith("src.platforms."):
            return False

        required_methods = ("init", "candidates", "ensure_candidates", "complete", "close")
        for method_name in required_methods:
            member = getattr(attr, method_name, None)
            if member is None or not callable(member):
                return False

        # 必须是 PlatformAdapter 子类，或具有 name property
        if issubclass(attr, PlatformAdapter):
            return True
        # 非 PlatformAdapter 子类：必须有 name property（排除 OllamaClient 等纯客户端类）
        name_member = getattr(attr, "name", None)
        if isinstance(name_member, property):
            return True
        return False

    def _collect_adapters_from_module(
        self,
        module: Any,
        discovered: List[Any],
        seen_classes: Set[str],
    ) -> None:
        """从单个模块中收集适配器类。

        Args:
            module: 已导入的模块对象。
            discovered: 已发现的适配器类列表。
            seen_classes: 已去重的类标识集合。
        """
        for attr_name in dir(module):
            try:
                attr = getattr(module, attr_name)
            except Exception as exc:
                logger.debug("获取模块属性 %s 失败: %s", attr_name, exc)
                continue

            if not self._is_adapter_class(attr):
                continue

            class_key = "{}.{}".format(
                getattr(attr, "__module__", ""),
                getattr(attr, "__qualname__", getattr(attr, "__name__", "")),
            )
            if class_key in seen_classes:
                continue

            seen_classes.add(class_key)
            discovered.append(attr)

    def _scan_package_tree(
        self,
        package: Any,
        discovered: List[Any],
        seen_modules: Set[str],
        seen_classes: Set[str],
    ) -> None:
        """递归扫描包树。

        Args:
            package: 包模块。
            discovered: 已发现的适配器类列表。
            seen_modules: 已扫描的模块名集合。
            seen_classes: 已去重的类标识集合。
        """
        pkg_path = getattr(package, "__path__", None)
        if pkg_path is None:
            return

        for module_info in pkgutil.iter_modules(pkg_path, package.__name__ + "."):
            module_name = module_info.name
            if module_name in seen_modules:
                continue
            # 跳过测试模块和纯客户端模块
            base_name = module_name.rsplit(".", 1)[-1]
            if base_name in ("test", "client"):
                continue

            seen_modules.add(module_name)
            try:
                mod = importlib.import_module(module_name)
            except Exception as exc:
                logger.warning("加载%s失败:%s", module_name, exc)
                continue

            self._collect_adapters_from_module(mod, discovered, seen_classes)

            if module_info.ispkg:
                self._scan_package_tree(mod, discovered, seen_modules, seen_classes)

    def _discover_adapter_classes(self, root_package: str) -> List[Any]:
        """递归发现指定包下的所有平台适配器类。

        Args:
            root_package: 根包名，例如 src.platforms 或 src.platforms.deepseek。

        Returns:
            适配器类列表。
        """
        discovered: List[Any] = []
        seen_modules: Set[str] = set()
        seen_classes: Set[str] = set()

        try:
            root_mod = importlib.import_module(root_package)
        except Exception as exc:
            logger.warning("导入%s失败:%s", root_package, exc)
            return discovered

        self._collect_adapters_from_module(root_mod, discovered, seen_classes)
        self._scan_package_tree(root_mod, discovered, seen_modules, seen_classes)
        return discovered

    async def init(self, session: aiohttp.ClientSession) -> None:
        """扫描并初始化所有平台适配器。

        Args:
            session: 共享 aiohttp ClientSession。
        """
        try:
            import src.platforms as pkg
        except ImportError:
            logger.warning("src.platforms 包不存在")
            return

        discovered = self._discover_adapter_classes(pkg.__name__)
        if not discovered:
            logger.warning("未发现任何平台适配器")
            return

        cfg = get_config()
        platform_cfg = cfg.platforms
        plat_list_type = cfg.platforms_cfg.platform_list_type
        plat_list_set = cfg.platforms_cfg.platform_list_set

        logger.info("发现%d个平台适配器，开始注册", len(discovered))

        async def _init_one(adapter_cls: type) -> None:
            """注册单个平台适配器。

            Args:
                adapter_cls: 适配器类。
            """
            adapter = adapter_cls()
            adapter_name = getattr(adapter, "name", adapter_cls.__name__)

            # 黑白名单检查（唯一控制点）
            if plat_list_type == "whitelist":
                if adapter_name not in plat_list_set:
                    logger.info("平台[%s]不在白名单中，跳过注册", adapter_name)
                    return
            else:  # blacklist
                if adapter_name in plat_list_set:
                    logger.info("平台[%s]在黑名单中，跳过注册", adapter_name)
                    return

            try:
                await adapter.init(session)
                self._adapters[adapter_name] = adapter
                logger.info(
                    "平台[%s]已注册(%d模型)",
                    adapter_name,
                    len(getattr(adapter, "supported_models", []) or []),
                )
            except Exception as exc:
                logger.error("平台[%s]注册失败:%s", adapter_name, exc)
                try:
                    await adapter.close()
                except Exception as exc:
                    logger.warning("平台[%s]初始化失败后关闭资源异常: %s", adapter_name, exc)

        await asyncio.gather(
            *[_init_one(cls) for cls in discovered],
            return_exceptions=True,
        )
        logger.info("注册完成:%s", list(self._adapters.keys()))

    async def reload_platform(
        self, platform_name: str, session: aiohttp.ClientSession
    ) -> bool:
        """热重载指定平台适配器。

        完整清理 sys.modules 中所有与该平台相关的子模块，
        确保重载后拿到最新代码。

        Args:
            platform_name: 平台标识名。
            session: 共享 session。

        Returns:
            是否重载成功。
        """
        old = self._adapters.get(platform_name)
        if old is not None:
            try:
                await old.close()
            except Exception as exc:
                logger.warning("热重载平台[%s]关闭旧适配器失败: %s", platform_name, exc)

        # 清理 sys.modules 中所有相关子模块（顺序：子模块先于父模块）
        prefix = "src.platforms.{}".format(platform_name)
        to_remove = sorted(
            [k for k in sys.modules if k == prefix or k.startswith(prefix + ".")],
            key=lambda x: -len(x),  # 子模块优先删除
        )
        for mod_key in to_remove:
            del sys.modules[mod_key]

        try:
            discovered = self._discover_adapter_classes(prefix)
            if not discovered:
                logger.error("重载[%s]未找到适配器类", platform_name)
                return False

            new_cls = discovered[0]
            new_adapter = new_cls()
            await new_adapter.init(session)
            self._adapters[platform_name] = new_adapter
            logger.info("平台[%s]热重载成功", platform_name)
            return True
        except Exception as exc:
            logger.error("平台[%s]热重载失败:%s", platform_name, exc)
            # 从注册表移除损坏的适配器
            self._adapters.pop(platform_name, None)
            return False

    @property
    def adapters(self) -> Dict[str, Any]:
        """全部适配器字典。

        Returns:
            适配器字典。
        """
        return self._adapters

    async def get_candidates(
        self,
        model: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> List[Candidate]:
        """获取匹配 model 和 capability 的可用候选项。

        Args:
            model: 模型名过滤（可选）。
            capability: 能力名过滤（可选）。

        Returns:
            候选项列表。
        """
        out: List[Candidate] = []
        for a in self._adapters.values():
            try:
                for c in await a.candidates():
                    if not c.available or c.busy:
                        continue
                    if model is not None and model not in c.models:
                        continue
                    if capability is not None and not c.has_capability(capability):
                        continue
                    out.append(c)
            except Exception as exc:
                logger.warning("[%s] candidates 失败:%s", a.name, exc)
        return out

    async def ensure_candidates(self, model: str, count: int) -> None:
        """确保候选项数量。

        Args:
            model: 模型名。
            count: 期望数量。
        """
        for a in self._adapters.values():
            if model in a.supported_models:
                try:
                    await a.ensure_candidates(count)
                except Exception as exc:
                    logger.warning("[%s] ensure_candidates 失败: %s", getattr(a, "name", "?"), exc)

    def adapter_for(self, c: Candidate) -> Optional[Any]:
        """根据候选项找对应适配器。

        Args:
            c: 候选项。

        Returns:
            适配器实例或 None。
        """
        return self._adapters.get(c.platform)

    async def get_capable_adapter(self, capability: str) -> Optional[Any]:
        """获取第一个支持指定能力的适配器。

        Args:
            capability: 能力名。

        Returns:
            适配器实例或 None。
        """
        for a in self._adapters.values():
            caps = a.default_capabilities
            if caps.get(capability, False):
                return a
        return None

    async def get_capable_candidate(
        self, capability: str
    ) -> Optional[Candidate]:
        """获取第一个支持指定能力的候选项。

        Args:
            capability: 能力名。

        Returns:
            候选项或 None。
        """
        cands = await self.get_candidates(capability=capability)
        if cands:
            selected = await self.selector.select(cands, 1)
            if selected:
                return selected[0]
        return None

    async def all_models(self) -> List[Dict[str, Any]]:
        """收集所有模型及其能力信息。

        Returns:
            模型字典列表（/v1/models 格式）。
        """
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for a in self._adapters.values():
            caps = a.default_capabilities
            ctx_len = getattr(a, "context_length", None)
            for m in a.supported_models:
                if m not in seen:
                    seen.add(m)
                    entry: Dict[str, Any] = {
                        "id": m,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": a.name,
                        "capabilities": dict(caps),
                    }
                    if ctx_len is not None:
                        entry["context_length"] = ctx_len
                    out.append(entry)
        return out

    async def list_models(self) -> List[Dict[str, Any]]:
        """列出全部模型信息。"""
        return await self.all_models()

    async def close(self) -> None:
        """并发关闭全部适配器。"""

        async def _close_one(name: str, adapter: Any) -> None:
            """关闭单个适配器。

            Args:
                name: 平台名。
                adapter: 适配器实例。
            """
            try:
                await asyncio.wait_for(adapter.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("关闭[%s]超时", name)
            except Exception as exc:
                logger.warning("关闭[%s]失败:%s", name, exc)

        await asyncio.gather(
            *[_close_one(n, a) for n, a in self._adapters.items()],
            return_exceptions=True,
        )
