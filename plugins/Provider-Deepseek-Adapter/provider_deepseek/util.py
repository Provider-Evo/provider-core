

from typing import Any, Dict, Optional

from pathlib import Path

from src.foundation.config.reader import get_config_reader

_PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_use_proxy(default: bool = False) -> bool:
    """读取插件 config.toml 中的 use_proxy。"""
    reader = get_config_reader()
    config, _schema, _raw = reader.get_plugin_config(_PLUGIN_DIR)
    return bool(config.get("use_proxy", default))


from src.foundation.logger import get_logger
from provider_deepseek.core.protocol.payload import make_stream_id
from provider_deepseek.core.protocol.consts import (
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
from provider_deepseek.core.guard.mdlcache import ModelsCache
from provider_deepseek.core.guard.pow import WasmPow, download_wasm, get_pow_response
from provider_deepseek.core.session.sessapi import (
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
from provider_deepseek.core.stream.strmpars import StreamParser
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
        from provider_deepseek.core.adapter.acore import (  # noqa: PLC0415
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
