from __future__ import annotations

"""Ollama 模型注册表构建。"""

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
