from __future__ import annotations

"""WebUI 在线文档数据。"""

from typing import List

from src.webui.models import DocLink, DocSection

__all__ = ["build_doc_sections"]


def build_doc_sections() -> List[DocSection]:
    """构建在线文档分组。"""
    return [
        DocSection(
            title="管理入口",
            items=[
                DocLink("管理台", "统一查看平台状态、配置摘要、模型信息和运行日志提示。", "/webui"),
                DocLink("在线文档", "集成式协议导航、运维入口与只读摘要说明。", "/docs"),
                DocLink("健康检查", "最小可用性检查接口，适合探针和快速联通验证。", "/health"),
            ],
        ),
        DocSection(
            title="OpenAI 兼容接口",
            items=[
                DocLink("模型列表", "获取全部模型、能力和上下文长度。", "/v1/models"),
                DocLink("聊天补全", "OpenAI 兼容聊天接口。", "/v1/chat/completions"),
                DocLink("Responses", "OpenAI Responses 兼容入口。", "/v1/responses"),
                DocLink("图片生成", "OpenAI 兼容图片生成接口。", "/v1/images/generations"),
                DocLink("语音合成", "OpenAI 兼容语音合成接口。", "/v1/audio/speech"),
            ],
        ),
        DocSection(
            title="Anthropic 兼容接口",
            items=[
                DocLink("消息接口", "Anthropic 兼容消息接口。", "/v1/messages"),
                DocLink("Token 计数", "估算输入 token 数量。", "/v1/messages/count_tokens"),
                DocLink("Anthropic 模型列表", "Anthropic 兼容模型视图。", "/anthropic/v1/models"),
            ],
        ),
        DocSection(
            title="运维与只读摘要",
            items=[
                DocLink("WebUI 摘要", "平台可用性、模型数、安全配置概览与汇总计数。", "/v1/webui/summary"),
                DocLink("平台状态", "逐平台候选项、可用数、模型数与上下文长度。", "/v1/status"),
                DocLink("能力矩阵", "逐平台能力字典，便于前端与运维观察。", "/v1/capabilities"),
                DocLink("刷新模型缓存", "触发各平台模型缓存刷新。", "/v1/admin/refresh_models"),
            ],
        ),
    ]
