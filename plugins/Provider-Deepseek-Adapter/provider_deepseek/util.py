"""
util 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Deepseek-Adapter.provider_deepseek.util
- 文件名：util.py
- 父包：provider-plugin/Provider-Deepseek-Adapter/provider_deepseek

职责：

    提供运行期凭证占位（API keys / accounts / session cookies 等）。
    真实凭证由 git 仓库外的 accounts.py 或 .env-like override 提供；
    本文件只暴露字段名与默认空值，供 SDK 与插件入口在导入失败时回退。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


from typing import Any, Dict, Optional

from src.foundation.logger import get_logger
from provider_deepseek.core.protocol.payloads import make_stream_id
from provider_deepseek.core.protocol.constants import (
    CAPS,
    CAPS_FLASH,
    CAPS_PRO,
    CAPS_VISION,
    DEFAULT_HOST,
    FETCH_MODELS_ENABLED,
    MAX_CONTINUE,
    MAX_RETRIES,
    MODEL_FETCH_INTERVAL,
    MODEL_FLASH,
    MODEL_PRO,
    MODEL_TYPE_MAP,
    MODEL_VISION,
    MODELS,
)
from provider_deepseek.core.protocol.headers import build_basic_headers, build_headers
from provider_deepseek.core.guard.hif import HifTokenManager, fetch_hif_tokens
from provider_deepseek.core.guard.modelcache import ModelsCache
from provider_deepseek.core.guard.pow import WasmPow, download_wasm, get_pow_response
from provider_deepseek.core.session.sessionapi import (
    create_session,
    delete_all_sessions,
    delete_session,
    get_history_messages,
    get_session_list,
    message_feedback,
    stop_stream,
    update_pinned,
    update_session_title,
)
from provider_deepseek.core.stream.streamparser import StreamParser
from provider_deepseek.core.user.userapi import (
    export_all_history,
    get_client_settings,
    get_current_user,
    get_user_settings,
    login,
    login_by_sms,
    logout,
    logout_all,
    send_email_code,
    send_sms_code,
    update_user_settings,
)

logger = get_logger(__name__)


def build_payload(
    session_id: str,
    prompt: str,
    model: str,
    *,
    thinking: bool = False,
    search: bool = False,
    stream_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建 DeepSeek ``/api/v0/chat/completion`` 请求体。"""
    return {
        "chat_session_id": session_id,
        "parent_message_id": None,
        "model_type": MODEL_TYPE_MAP.get(model, "default"),
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": False if model == MODEL_VISION else thinking,
        "search_enabled": search,
        "preempt": False,
        "client_stream_id": stream_id if stream_id is not None else make_stream_id(),
    }


def parse_sse_line(
    data_str: str,
    parser: Optional[StreamParser] = None,
) -> Optional[Dict[str, Any]]:
    """解析单行 SSE 数据，委托给 ``StreamParser``。"""
    if parser is None:
        return None
    if not data_str.strip():
        return None
    return parser.parse_line(data_str)


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in {"DeepseekAdapter", "Adapter"}:
        from provider_deepseek.core.adapter.adaptercore import (  # noqa: PLC0415
            DeepseekAdapter as _DeepseekAdapter,
        )

        return _DeepseekAdapter
    if name == "DeepseekClient":
        from provider_deepseek.core.adapter.client import (  # noqa: PLC0415
            DeepseekClient as _DeepseekClient,
        )

        return _DeepseekClient
    if name == "Account":
        from provider_deepseek.core.adapter.client import (  # noqa: PLC0415
            Account as _Account,
        )

        return _Account
    raise AttributeError(
        "module 'src.platforms.deepseek.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "MODELS",
    "CAPS",
    "CAPS_PRO",
    "CAPS_FLASH",
    "CAPS_VISION",
    "MODEL_PRO",
    "MODEL_FLASH",
    "MODEL_VISION",
    "MODEL_TYPE_MAP",
    "DEFAULT_HOST",
    "MAX_CONTINUE",
    "MAX_RETRIES",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "Account",
    "ModelsCache",
    "WasmPow",
    "StreamParser",
    "HifTokenManager",
    "build_headers",
    "build_basic_headers",
    "download_wasm",
    "get_pow_response",
    "fetch_hif_tokens",
    "login",
    "login_by_sms",
    "send_sms_code",
    "send_email_code",
    "get_current_user",
    "logout",
    "logout_all",
    "get_user_settings",
    "update_user_settings",
    "get_client_settings",
    "export_all_history",
    "create_session",
    "get_session_list",
    "get_history_messages",
    "stop_stream",
    "message_feedback",
    "update_session_title",
    "delete_session",
    "delete_all_sessions",
    "update_pinned",
    "make_stream_id",
    "build_payload",
    "parse_sse_line",
    "DeepseekClient",
    "DeepseekAdapter",
    "Adapter",
]
