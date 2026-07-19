"""
videos 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.routes.openai.media.videos
- 文件名：videos.py
- 父包：provider-core/src/routes/openai/media

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


import time
import uuid
from typing import Any, Dict

import aiohttp.web

from src.core.server import REGISTRY_KEY, get_json as _get_json
from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import _err, _json, _not_supported

__all__ = [
    "create_video",
    "list_videos",
    "retrieve_video",
    "delete_video",
    "retrieve_video_content",
    "remix_video",
    "create_video_character",
    "retrieve_video_character",
    "create_video_edit",
    "create_video_extension",
    "legacy_video_generations",
]

logger = get_logger(__name__)

_VIDEOS: Dict[str, Dict[str, Any]] = {}


async def create_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos — 创建视频（能力路由）。"""
    body = await _get_json(request)
    if body is None:
        return _err(400, "Invalid JSON", "invalid_json")

    registry = request.app[REGISTRY_KEY]
    cand = await registry.get_capable_candidate("video_gen")
    if cand is None:
        return _not_supported("Video generation")

    adapter = registry.adapter_for(cand)
    try:
        result = await adapter.create_video(
            cand,
            body.get("prompt", ""),
            body.get("model", ""),
            **{k: v for k, v in body.items() if k not in ("prompt", "model")},
        )
    except NotImplementedError:
        return _not_supported("Video generation")
    except Exception as exc:
        return _err(502, str(exc), "provider_error")

    vid = result.get("id") if isinstance(result, dict) else "video_{}".format(uuid.uuid4().hex[:16])
    stored = {
        "id": vid,
        "object": "video",
        "created_at": int(time.time()),
        "status": "completed",
        "model": body.get("model", ""),
        "result": result,
    }
    _VIDEOS[vid] = stored
    return _json(stored)


async def list_videos(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos。"""
    data = list(_VIDEOS.values())
    return _json({"object": "list", "data": data})


async def retrieve_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos/{video_id}。"""
    item = _VIDEOS.get(request.match_info["video_id"])
    if item is None:
        return _err(404, "Video not found", "not_found")
    return _json(item)


async def delete_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """DELETE /v1/videos/{video_id}。"""
    vid = request.match_info["video_id"]
    if vid not in _VIDEOS:
        return _err(404, "Video not found", "not_found")
    del _VIDEOS[vid]
    return _json({"id": vid, "object": "video.deleted", "deleted": True})


async def retrieve_video_content(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos/{video_id}/content。"""
    item = _VIDEOS.get(request.match_info["video_id"])
    if item is None:
        return _err(404, "Video not found", "not_found")
    return _err(501, "Video content download not implemented", "not_implemented")


async def remix_video(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/{video_id}/remix。"""
    return _not_supported("Video remix")


async def create_video_character(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/characters。"""
    return _not_supported("Video characters")


async def retrieve_video_character(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/videos/characters/{character_id}。"""
    return _err(404, "Character not found", "not_found")


async def create_video_edit(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/edits。"""
    return _not_supported("Video edits")


async def create_video_extension(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/extensions。"""
    return _not_supported("Video extensions")


async def legacy_video_generations(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/videos/generations — 兼容旧路径。"""
    return await create_video(request)

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
