"""API 路径前缀工具。"""

OAI_PREFIX = "/v1/openai"
ANT_PREFIX = "/v1/anthropic"
ENT_PREFIX = "/v1"


def oai_path(path: str) -> str:
    """/v1/chat/completions → /v1/openai/chat/completions"""
    if path.startswith(OAI_PREFIX):
        return path
    if path.startswith("/v1/"):
        return OAI_PREFIX + path[3:]
    if path.startswith("/"):
        return OAI_PREFIX + path
    return OAI_PREFIX + "/" + path


def ant_path(path: str) -> str:
    """/v1/messages → /v1/anthropic/messages；/anthropic/v1/models → /v1/anthropic/models"""
    if path.startswith(ANT_PREFIX):
        return path
    if path.startswith("/anthropic/v1/"):
        return ANT_PREFIX + path[len("/anthropic/v1") :]
    if path.startswith("/v1/"):
        return ANT_PREFIX + path[3:]
    if path == "/messages":
        return f"{ANT_PREFIX}/messages"
    if path.startswith("/"):
        return ANT_PREFIX + path
    return ANT_PREFIX + "/" + path
