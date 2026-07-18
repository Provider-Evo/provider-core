"""constants 模块 — Provider 适配器层。

职责：
    集中放置 provider 常量定义（模型名、URL 模板、错误码等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Dict, Final, List

MODELS: Final[List[str]] = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunyangNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-DavisNeural",
]

CAPS: Final[Dict[str, bool]] = {
    "audio_gen": True,
}

DEFAULT_VOICE: Final[str] = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE: Final[str] = "+0%"
DEFAULT_VOLUME: Final[str] = "+0%"
DEFAULT_PITCH: Final[str] = "+0Hz"
DEFAULT_FORMAT: Final[str] = "audio-24khz-48kbitrate-mono-mp3"

CHROMIUM_FULL_VERSION: Final[str] = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: Final[str] = CHROMIUM_FULL_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION: Final[str] = "1-{}".format(CHROMIUM_FULL_VERSION)
TRUSTED_CLIENT_TOKEN: Final[str] = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
WSS_HOST: Final[str] = "speech.platform.bing.com"
WSS_PATH_BASE: Final[str] = (
    "/consumer/speech/synthesize/readaloud/edge/v1"
    "?TrustedClientToken={}".format(TRUSTED_CLIENT_TOKEN)
)

MAX_RETRIES: Final[int] = 3
WIN_EPOCH: Final[int] = 11644473600
S_TO_NS: Final[float] = 1e9

BASE_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{mv}.0.0.0 Safari/537.36 Edg/{mv}.0.0.0"
    ).format(mv=CHROMIUM_MAJOR_VERSION),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

WSS_HANDSHAKE_HEADERS: Final[Dict[str, str]] = {
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
    **{
        "User-Agent": BASE_HEADERS["User-Agent"],
        "Accept-Encoding": BASE_HEADERS["Accept-Encoding"],
        "Accept-Language": BASE_HEADERS["Accept-Language"],
    },
}

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
# =======================================================================
# 重导出 — 同包协同模块（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .adaptercore import (
    EdgeTtsAdapter,
)

from .client import (
    Client,
)
__all__ = [
    "EdgeTtsAdapter",
    "Client",
]
