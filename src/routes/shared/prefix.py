"""API 路径前缀工具。"""

OAI_PREFIX = "/openai/v1"
ANT_PREFIX = "/anthropic/v1"
ENT_PREFIX = "/v1"


def oai_path(path: str) -> str:
    """/v1/chat/completions → /openai/v1/chat/completions"""
    if path.startswith(OAI_PREFIX):
        return path
    if path.startswith("/v1/"):
        return OAI_PREFIX + path[3:]
    if path.startswith("/"):
        return OAI_PREFIX + path
    return OAI_PREFIX + "/" + path


def ant_path(path: str) -> str:
    """/v1/messages → /anthropic/v1/messages"""
    if path.startswith(ANT_PREFIX):
        return path
    if path.startswith("/v1/"):
        return ANT_PREFIX + path[3:]
    if path == "/messages":
        return f"{ANT_PREFIX}/messages"
    if path.startswith("/"):
        return ANT_PREFIX + path
    return ANT_PREFIX + "/" + path
