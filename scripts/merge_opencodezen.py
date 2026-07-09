#!/usr/bin/env python3
"""创建 Provider-OpencodeZen-Adapter 合并插件。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
SRC_OP = PLUGINS / "Provider-Opencode-Adapter"
SRC_ZN = PLUGINS / "Provider-Zen-Adapter"
DST = PLUGINS / "Provider-OpencodeZen-Adapter"
PKG = DST / "provider_opencodezen"

ADAPTER = '''"""OpencodeZen 合并平台 — USE_PROXY_POOL 切换代理池 / API Key 模式。"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.utils.compat.models_cache import ModelsCache
from src.logger import get_logger
from src.platforms.base import PlatformAdapter

try:
    from provider_opencodezen.accounts import USE_PROXY_POOL
except ImportError:
    USE_PROXY_POOL = True

from .constants import CAPS, FETCH_MODELS_ENABLED, MODEL_FETCH_INTERVAL, MODELS

logger = get_logger(__name__)


class OpencodeZenAdapter(PlatformAdapter):
  """合并 opencode（代理池）与 zen（API Key）策略。"""

  def __init__(self) -> None:
    self._client: Any = None
    self._models: List[str] = list(MODELS)
    self._cache: Optional[ModelsCache] = None
    self._refresh_task: Optional[asyncio.Task] = None
    self._use_proxy_pool = bool(USE_PROXY_POOL)

  @property
  def name(self) -> str:
    return "opencodezen"

  @property
  def supported_models(self) -> List[str]:
    return list(self._models)

  @property
  def default_capabilities(self) -> Dict[str, bool]:
    return CAPS

  async def init(self, session: aiohttp.ClientSession) -> None:
    if self._use_proxy_pool:
      from .opencode.client import OpencodeClient
      self._client = OpencodeClient()
      plat = "opencodezen-proxy"
    else:
      from .zen.client import ZenClient
      self._client = ZenClient()
      plat = "opencodezen-key"
    await self._client.init_immediate(session)
    self._cache = ModelsCache(
      platform=plat,
      fallback_models=MODELS,
      fetch_enabled=FETCH_MODELS_ENABLED,
    )
    cached = await self._cache.load()
    if cached:
      self._models = cached
      self._client.update_models(self._models)
    self._refresh_task = asyncio.ensure_future(self._background_init())

  async def _background_init(self) -> None:
    try:
      await self._client.background_setup()
    except Exception as exc:
      logger.warning("opencodezen background init failed: %s", exc)
    if self._cache is not None:
      asyncio.ensure_future(
        self._cache.start_refresh_loop(
          fetch_fn=self.fetch_remote_models,
          interval=MODEL_FETCH_INTERVAL,
          on_update=self._on_models_updated,
        )
      )

  async def _on_models_updated(self, models: List[str]) -> None:
    self._models = models
    if self._client is not None:
      self._client.update_models(models)

  async def fetch_remote_models(self) -> List[str]:
    if self._client is None:
      return list(MODELS)
    return await self._client.fetch_remote_models()

  async def candidates(self) -> List[Candidate]:
    if self._client is None:
      return []
    return await self._client.candidates()

  async def ensure_candidates(self, count: int) -> int:
    if self._client is None:
      return 0
    return await self._client.ensure_candidates(count)

  async def complete(
    self,
    candidate: Candidate,
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool,
    *,
    thinking: bool = False,
    search: bool = False,
    **kw: Any,
  ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    async for chunk in self._client.complete(
      candidate, messages, model, stream,
      thinking=thinking, search=search, **kw,
    ):
      yield chunk

  async def close(self) -> None:
    if self._refresh_task is not None and not self._refresh_task.done():
      self._refresh_task.cancel()
      try:
        await self._refresh_task
      except asyncio.CancelledError:
        pass
    if self._client is not None:
      await self._client.close()


Adapter = OpencodeZenAdapter
'''

PLUGIN_PY = '''from __future__ import annotations

import importlib

from provider_sdk import ProviderPlugin
from provider_sdk.extensions.platform.bridge import attach_platform_adapter


def _find_adapter_class(mod: object) -> type:
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if not isinstance(obj, type) or not attr.endswith("Adapter"):
            continue
        if all(hasattr(obj, m) for m in ("name", "init", "candidates", "complete", "close")):
            return obj
    raise RuntimeError(f"no adapter class in {mod.__name__}")


class OpencodeZenPlugin(ProviderPlugin):
    async def on_load(self) -> None:
        mod = importlib.import_module("provider_opencodezen.core.adaptercore")
        adapter = _find_adapter_class(mod)()
        attach_platform_adapter(self, adapter)


def create_plugin() -> OpencodeZenPlugin:
    return OpencodeZenPlugin()
'''

ACCOUNTS_EXAMPLE = '''# Copy to accounts.py
# True: opencode 代理池策略（含直连选择）
# False: zen API Key 策略（无代理选择）
USE_PROXY_POOL = True
API_KEYS = []
LOCAL_PROXIES = []
'''

MANIFEST = {
  "manifest_version": 2,
  "id": "nichengfuben.provider-opencodezen-adapter",
  "name": "Provider OpencodeZen Adapter",
  "version": "1.0.0",
  "description": "合并 opencode 代理池与 zen API Key 模式",
  "plugin_type": "platform",
  "author": {"name": "nichengfuben"},
  "host_application": {"min_version": "2.2.268", "max_version": "2.2.99"},
  "sdk": {"min_version": "0.3.0", "max_version": "0.99.99"},
  "dependencies": [],
  "capabilities": ["platform.adapter"],
}

GITIGNORE = '''accounts.py
__pycache__/
*.pyc
.venv/
'''


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)
    PKG.mkdir(parents=True)
    (PKG / "__init__.py").write_text("", encoding="utf-8")
    (PKG / "core").mkdir(parents=True)

    shutil.copytree(SRC_OP / "provider_opencode" / "core", PKG / "core" / "opencode")
    shutil.copytree(SRC_ZN / "provider_zen" / "core", PKG / "core" / "zen")
    (PKG / "core" / "__init__.py").write_text("", encoding="utf-8")
    (PKG / "core" / "adaptercore.py").write_text(ADAPTER, encoding="utf-8")
    shutil.copy2(SRC_OP / "provider_opencode" / "core" / "constants.py", PKG / "core" / "constants.py")

    (DST / "plugin.py").write_text(PLUGIN_PY, encoding="utf-8")
    (DST / "accounts.py.example").write_text(ACCOUNTS_EXAMPLE, encoding="utf-8")
    (DST / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (DST / "_manifest.json").write_text(json.dumps(MANIFEST, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for old in (SRC_OP, SRC_ZN):
        manifest = old / "_manifest.json"
        if manifest.exists():
            manifest.rename(old / "_manifest.json.disabled")

    print("created", DST)


if __name__ == "__main__":
    main()
