


from typing import Any, Dict


def build_registry(servers: Dict[str, Any]) -> Dict[str, Any]:
    """从服务器列表构建模型注册表。

    Args:
        servers: 服务器字典 {ip: server_info}。

    Returns:
        模型注册表 {model_name: model_info}。
    """
    reg: Dict[str, Any] = {}
    for ip, srv in servers.items():
        for m in srv.get("models", []):
            name = m.get("name", "")
            if not name:
                continue
            if name not in reg:
                reg[name] = {
                    "servers": [],
                    "capabilities": m.get("capabilities", {"chat": True}),
                    "family": m.get("family", ""),
                }
            reg[name]["servers"].append({
                "ip": ip,
                "base_url": srv["base_url"],
            })
            for k, v in m.get("capabilities", {}).items():
                if v:
                    reg[name]["capabilities"][k] = True
    return reg

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payloads import (
    build_image_messages,
    build_chat_payload,
)

from .sse import (
    parse_ollama_line,
)

__all__ = [
    "build_image_messages",
    "build_chat_payload",
    "parse_ollama_line",
]
