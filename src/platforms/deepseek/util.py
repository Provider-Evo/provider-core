from __future__ import annotations

"""DeepSeek 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.deepseek.core`` 子模块
- ``DeepseekAdapter`` 与 ``DeepseekClient`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any, Dict, Optional

from src.logger import get_logger
from src.platforms.deepseek.core.accounts import ACCOUNTS, Account
from src.platforms.deepseek.core.client import make_stream_id
from src.platforms.deepseek.core.constants import (
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
from src.platforms.deepseek.core.headers import build_basic_headers, build_headers
from src.platforms.deepseek.core.hif import HifTokenManager, fetch_hif_tokens
from src.platforms.deepseek.core.models_cache import ModelsCache
from src.platforms.deepseek.core.pow import WasmPow, download_wasm, get_pow_response
from src.platforms.deepseek.core.session_api import (
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
from src.platforms.deepseek.core.stream_parser import StreamParser
from src.platforms.deepseek.core.user_api import (
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
    if name == "DeepseekAdapter":
        from src.platforms.deepseek.core.adapter_impl import (  # noqa: PLC0415
            DeepseekAdapter as _DeepseekAdapter,
        )

        return _DeepseekAdapter
    if name == "DeepseekClient":
        from src.platforms.deepseek.core.client import (  # noqa: PLC0415
            DeepseekClient as _DeepseekClient,
        )

        return _DeepseekClient
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
    "ACCOUNTS",
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
]
