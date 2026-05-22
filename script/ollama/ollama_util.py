"""
ollama_util.py
Ollama API 服务器工具模块 - 包含模型定义、处理器和存储类
版本: 1.0.0

核心改造: 集成 Nous 风格 XML 函数调用提示词系统
(<function=name>args</function> / <tool_response>)
- 向 ollama_client 发送请求时使用 NousXML fncall 格式
- 向外部用户响应时保持 OpenAI/Anthropic 兼容格式
- 移除模型映射处理（Ollama 直接使用原始模型名称）
- 移除大文本分割逻辑（直接发送完整文本）
"""

import asyncio
import json
import os
import re
import time
import uuid
from asyncio import Lock
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import *

from pydantic import BaseModel, ConfigDict, Field
import logging

logger = logging.getLogger("ollama_server.util")


# ==========================================================================
#  NousXML FnCall 常量
# ==========================================================================

# 函数调用 XML 标记
FN_CALL_START_TAG = "<function="  # <function=fn_name>
FN_CALL_END_TAG = "</function>"
TOOL_RESPONSE_START_TAG = "<tool_response>"
TOOL_RESPONSE_END_TAG = "</tool_response>"
TOOLS_START_TAG = "<tools>"
TOOLS_END_TAG = "</tools>"

# 流式输出停止词
FN_STOP_WORDS: List[str] = [FN_CALL_END_TAG, TOOL_RESPONSE_END_TAG]

# 向后兼容别名
FN_NAME = FN_CALL_START_TAG
FN_ARGS = ">"  # 函数名与参数之间的分隔符
FN_RESULT = TOOL_RESPONSE_START_TAG
FN_EXIT = TOOL_RESPONSE_END_TAG

# 特殊代码模式 (code_interpreter 工具的特殊处理)
SPECIAL_CODE_MODE: bool = (
    os.getenv("SPECIAL_CODE_MODE", "false").lower() == "true"
)
CODE_TOOL_PATTERN: str = "code_interpreter"


# ==========================================================================
#  NousXML 函数调用提示词模板
# ==========================================================================

# ---- 英文模板 ----

FN_CALL_TEMPLATE_EN = """\
You are a helpful AI assistant that can interact with tools to solve tasks.

# Tools

You have access to the following functions:

<tools>
{tool_descs}
</tools>

If you choose to call a function ONLY reply in the following format with NO suffix:

<function=function_name>{{param_name: param_value}}</function>

<IMPORTANT>
Reminder:\
- Function calls MUST follow the specified format:\
  an inner <function=...></function> block.\
- Required parameters MUST be specified.\
- You may provide optional reasoning for your function call in natural language\
  BEFORE the function call, but NOT after.\
- If there is no function call available, answer the question like normal with\
  your current knowledge and do not tell the user about function calls.
</IMPORTANT>"""

FN_CALL_TEMPLATE_WITH_CI_EN = """\
You are a helpful AI assistant that can interact with tools to solve tasks.

# Tools

You have access to the following functions:

<tools>
{tool_descs}
</tools>

If you choose to call a function ONLY reply in the following format with NO suffix:

<function=function_name>{{param_name: param_value}}</function>

For code parameters, use placeholders first, and then put the code within\
 <code></code> XML tags, such as:
<function=function_name>{{code: }}
<code>
Here is the code.
</code>
</function>

<IMPORTANT>
Reminder:\
- Function calls MUST follow the specified format:\
  an inner <function=...></function> block.\
- Required parameters MUST be specified.\
- You may provide optional reasoning for your function call in natural language\
  BEFORE the function call, but NOT after.\
- If there is no function call available, answer the question like normal with\
  your current knowledge and do not tell the user about function calls.
</IMPORTANT>"""

# ---- 中文模板 ----

FN_CALL_TEMPLATE_ZH = """\
你是一个乐于助人的AI助手，可以使用工具来解决任务。

# 工具

你可以使用以下函数：

<tools>
{tool_descs}
</tools>

如果你选择调用函数，请严格按照以下格式回复，不要添加任何后缀：

<function=函数名称>{{参数名: 参数值}}</function>

<IMPORTANT>
注意事项：\
- 函数调用必须严格遵循指定格式：使用 <function=...></function> 标签。\
- 必须指定所有必需参数。\
- 你可以在函数调用之前用自然语言提供可选的推理说明，但不能在之后。\
- 如果没有可用的函数调用，请用你现有的知识正常回答问题，不要告诉用户关于函数调用的信息。
</IMPORTANT>"""

FN_CALL_TEMPLATE_WITH_CI_ZH = """\
你是一个乐于助人的AI助手，可以使用工具来解决任务。

# 工具

你可以使用以下函数：

<tools>
{tool_descs}
</tools>

如果你选择调用函数，请严格按照以下格式回复，不要添加任何后缀：

<function=函数名称>{{参数名: 参数值}}</function>

对于代码参数，先使用占位符，然后将代码放在 <code></code> XML 标签中，例如：
<function=函数名称>{{code: }}
<code>
这里是代码。
</code>
</function>

<IMPORTANT>
注意事项：\
- 函数调用必须严格遵循指定格式：使用 <function=...></function> 标签。\
- 必须指定所有必需参数。\
- 你可以在函数调用之前用自然语言提供可选的推理说明，但不能在之后。\
- 如果没有可用的函数调用，请用你现有的知识正常回答问题，不要告诉用户关于函数调用的信息。
</IMPORTANT>"""

# 模板索引字典
FN_CALL_TEMPLATE: Dict[str, str] = {
    "en": FN_CALL_TEMPLATE_EN,
    "zh": FN_CALL_TEMPLATE_ZH,
    "en_ci": FN_CALL_TEMPLATE_WITH_CI_EN,
    "zh_ci": FN_CALL_TEMPLATE_WITH_CI_ZH,
}


# ==========================================================================
#  服务器配置
# ==========================================================================


class ServerConfig:
    """服务器配置类"""

    HOST: str = "0.0.0.0"
    PORT: int = 1329
    DEBUG: bool = True


# ==========================================================================
#  枚举定义
# ==========================================================================


class AnthropicStopReason(str, Enum):
    """Anthropic 停止原因枚举"""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"


class AnthropicContentType(str, Enum):
    """Anthropic 内容类型枚举"""

    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    DOCUMENT = "document"


class AnthropicMessageRole(str, Enum):
    """Anthropic 消息角色枚举"""

    USER = "user"
    ASSISTANT = "assistant"


class AnthropicBetaFeature(str, Enum):
    """Anthropic Beta 特性枚举"""

    MESSAGE_BATCHES = "message-batches-2024-09-24"
    FILES_API = "files-api-2025-04-14"
    PROMPT_CACHING = "prompt-caching-2024-07-31"
    TOKEN_COUNTING = "token-counting-2024-11-01"


# ==========================================================================
#  OpenAI 兼容 Pydantic 模型
# ==========================================================================


class ImageURL(BaseModel):
    """图片 URL"""

    url: str = Field(..., description="图片 URL 或 Base64 data URI")
    detail: Optional[str] = Field(
        None, description="图片详细程度: auto, low, high"
    )


class AudioURL(BaseModel):
    """音频 URL"""

    url: str = Field(..., description="音频 URL 或 Base64 data URI")


class VideoURL(BaseModel):
    """视频 URL"""

    url: str = Field(..., description="视频 URL 或 Base64 data URI")


class FileURL(BaseModel):
    """文件 URL"""

    url: str = Field(..., description="文件 URL 或 Base64 data URI")


class InputAudio(BaseModel):
    """输入音频"""

    data: str = Field(..., description="Base64 编码的音频数据")
    format: str = Field("wav", description="音频格式: wav, mp3 等")


class ContentPart(BaseModel):
    """内容部分"""

    type: str = Field(
        ...,
        description=(
            "类型: text, image_url, audio_url, video_url, "
            "file_url, input_audio"
        ),
    )
    text: Optional[str] = None
    image_url: Optional[ImageURL] = None
    audio_url: Optional[AudioURL] = None
    video_url: Optional[VideoURL] = None
    file_url: Optional[FileURL] = None
    input_audio: Optional[InputAudio] = None


class FunctionCall(BaseModel):
    """函数调用"""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用 (非流式响应用)"""

    id: str
    type: str = "function"
    function: FunctionCall


class ToolCallChunk(BaseModel):
    """流式工具调用块 (流式响应用，包含 index 字段)"""

    index: int
    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    """聊天消息"""

    role: str = Field(
        ..., description="消息角色: system, user, assistant, tool"
    )
    content: Optional[Union[str, List[ContentPart]]] = Field(
        None, description="消息内容"
    )
    name: Optional[str] = Field(None, description="发送者名称")
    tool_calls: Optional[List[ToolCall]] = Field(
        None, description="工具调用列表"
    )
    tool_call_id: Optional[str] = Field(
        None, description="工具调用 ID"
    )


class FunctionDefinition(BaseModel):
    """函数定义"""

    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ToolDefinition(BaseModel):
    """工具定义"""

    type: str = "function"
    function: FunctionDefinition


class ResponseFormat(BaseModel):
    """响应格式"""

    type: str = "text"


class EmbeddingRequest(BaseModel):
    """嵌入向量请求"""

    input: Union[str, List[str]] = Field(
        ..., description="输入文本"
    )
    model: str = Field(
        default="nomic-embed-text", description="嵌入模型"
    )
    dimensions: Optional[int] = Field(
        default=None, description="输出维度"
    )
    encoding_format: str = Field(
        default="float", description="编码格式"
    )


class EmbeddingData(BaseModel):
    """嵌入数据"""

    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingUsage(BaseModel):
    """嵌入使用量"""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """嵌入向量响应"""

    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""

    model: str = Field(default="llama3.2:latest")
    messages: List[ChatMessage] = Field(...)
    stream: bool = Field(default=False)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    top_p: Optional[float] = Field(None, ge=0, le=1)
    max_tokens: Optional[int] = Field(None, ge=1)
    presence_penalty: Optional[float] = Field(
        None, ge=-2, le=2
    )
    frequency_penalty: Optional[float] = Field(
        None, ge=-2, le=2
    )
    user: Optional[str] = Field(None)
    stop: Optional[Union[str, List[str]]] = Field(None)
    n: int = Field(default=1, ge=1, le=1)
    tools: Optional[List[ToolDefinition]] = Field(None)
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(
        None
    )
    response_format: Optional[ResponseFormat] = Field(None)
    extra_body: Optional[Dict[str, Any]] = Field(None)

    model_config = ConfigDict(extra="allow")


class ChatCompletionMessageResponse(BaseModel):
    """聊天补全消息响应"""

    role: str
    content: Optional[str] = None
    reasoning_content: Optional[str] = Field(
        None, description="推理内容"
    )
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChoice(BaseModel):
    """聊天补全选择"""

    index: int
    message: ChatCompletionMessageResponse
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


class ChatCompletionUsage(BaseModel):
    """聊天补全使用量"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """聊天补全响应"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage
    system_fingerprint: Optional[str] = None


class ChatCompletionChunkDelta(BaseModel):
    """聊天补全块增量"""

    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = Field(
        None, description="推理内容增量"
    )
    tool_calls: Optional[List[ToolCallChunk]] = None


class ChatCompletionChunkChoice(BaseModel):
    """聊天补全块选择"""

    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None
    logprobs: Optional[Any] = None


class ChatCompletionChunk(BaseModel):
    """聊天补全块"""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]
    usage: Optional[ChatCompletionUsage] = None
    system_fingerprint: Optional[str] = None


class ImageGenerationRequest(BaseModel):
    """图像生成请求 (占位，Ollama 不直接支持)"""

    prompt: str = Field(..., description="图像描述提示词")
    model: str = Field(default="", description="模型名称")
    n: int = Field(default=1, ge=1, le=10)
    size: Optional[str] = Field(None)
    response_format: str = Field(default="url")

    model_config = ConfigDict(extra="allow")


class ImageData(BaseModel):
    """图像数据"""

    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    """图像生成响应"""

    created: int
    data: List[ImageData]


class ModelInfo(BaseModel):
    """模型信息"""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "ollama"
    permission: List[Dict[str, Any]] = Field(
        default_factory=list
    )
    root: Optional[str] = None
    parent: Optional[str] = None
    info: Optional[Dict[str, Any]] = Field(
        default=None, description="模型能力元数据"
    )


class ModelsResponse(BaseModel):
    """模型列表响应"""

    object: str = "list"
    data: List[ModelInfo]


class ErrorDetail(BaseModel):
    """错误详情"""

    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""

    error: ErrorDetail


class ResponsesRequest(BaseModel):
    """Responses API 请求"""

    model: str = Field(default="llama3.2:latest")
    input: Union[str, List[Dict[str, Any]]] = Field(
        ..., description="输入内容"
    )
    instructions: Optional[str] = Field(
        None, description="系统指令"
    )
    max_output_tokens: Optional[int] = Field(None)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    tools: Optional[List[Dict[str, Any]]] = Field(None)
    stream: bool = Field(default=False)

    model_config = ConfigDict(extra="allow")


# ==========================================================================
#  Anthropic API 模型
# ==========================================================================


class AnthropicImageSource(BaseModel):
    """Anthropic 图像源"""

    type: str = Field(..., description="来源类型")
    media_type: Optional[str] = Field(
        None, description="媒体类型"
    )
    data: Optional[str] = Field(
        None, description="Base64 数据"
    )
    url: Optional[str] = Field(None, description="URL")


class AnthropicDocumentSource(BaseModel):
    """Anthropic 文档源"""

    type: str = Field(..., description="来源类型")
    media_type: Optional[str] = Field(
        None, description="媒体类型"
    )
    data: Optional[str] = Field(
        None, description="Base64 数据"
    )
    url: Optional[str] = Field(None, description="URL")
    file_id: Optional[str] = Field(
        None, description="文件 ID"
    )


class AnthropicContentBlock(BaseModel):
    """Anthropic 内容块"""

    type: str = Field(
        ...,
        description=(
            "内容类型: text, image, tool_use, "
            "tool_result, document"
        ),
    )
    text: Optional[str] = Field(None, description="文本内容")
    source: Optional[
        Union[AnthropicImageSource, AnthropicDocumentSource]
    ] = Field(None, description="来源")
    id: Optional[str] = Field(
        None, description="工具使用 ID"
    )
    name: Optional[str] = Field(
        None, description="工具名称"
    )
    input: Optional[Dict[str, Any]] = Field(
        None, description="工具输入"
    )
    tool_use_id: Optional[str] = Field(
        None, description="工具使用 ID (用于 tool_result)"
    )
    content: Optional[Union[str, List[Any]]] = Field(
        None, description="工具结果内容"
    )
    is_error: Optional[bool] = Field(
        None, description="是否错误"
    )
    cache_control: Optional[Dict[str, str]] = Field(
        None, description="缓存控制"
    )


class AnthropicMessage(BaseModel):
    """Anthropic 消息"""

    role: str = Field(..., description="消息角色")
    content: Union[str, List[AnthropicContentBlock]] = Field(
        ..., description="消息内容"
    )


class AnthropicToolInputSchema(BaseModel):
    """Anthropic 工具输入模式"""

    type: str = "object"
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None


class AnthropicTool(BaseModel):
    """Anthropic 工具"""

    name: str = Field(..., description="工具名称")
    description: Optional[str] = Field(
        None, description="工具描述"
    )
    input_schema: AnthropicToolInputSchema = Field(
        ..., description="输入模式"
    )
    cache_control: Optional[Dict[str, str]] = Field(
        None, description="缓存控制"
    )


class AnthropicToolChoice(BaseModel):
    """Anthropic 工具选择"""

    type: str = Field(..., description="选择类型")
    name: Optional[str] = Field(None)
    disable_parallel_tool_use: Optional[bool] = Field(None)


class AnthropicMetadata(BaseModel):
    """Anthropic 元数据"""

    user_id: Optional[str] = Field(
        None, description="用户 ID"
    )


class AnthropicMessagesRequest(BaseModel):
    """Anthropic 消息请求"""

    model: str = Field(..., description="模型名称")
    messages: List[AnthropicMessage] = Field(
        ..., description="消息列表"
    )
    max_tokens: int = Field(
        ..., ge=1, description="最大 token 数"
    )
    system: Optional[
        Union[str, List[AnthropicContentBlock]]
    ] = Field(None, description="系统提示")
    stop_sequences: Optional[List[str]] = Field(
        None, description="停止序列"
    )
    stream: bool = Field(
        default=False, description="是否流式"
    )
    temperature: Optional[float] = Field(
        None, ge=0, le=1, description="温度"
    )
    top_p: Optional[float] = Field(
        None, ge=0, le=1, description="Top P"
    )
    top_k: Optional[int] = Field(
        None, ge=0, description="Top K"
    )
    tools: Optional[List[AnthropicTool]] = Field(
        None, description="工具列表"
    )
    tool_choice: Optional[
        Union[AnthropicToolChoice, Dict[str, Any]]
    ] = Field(None, description="工具选择")
    metadata: Optional[AnthropicMetadata] = Field(
        None, description="元数据"
    )

    model_config = ConfigDict(extra="allow")


class AnthropicUsage(BaseModel):
    """Anthropic 使用量"""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


class AnthropicTextBlock(BaseModel):
    """Anthropic 文本块"""

    type: str = "text"
    text: str


class AnthropicToolUseBlock(BaseModel):
    """Anthropic 工具使用块"""

    type: str = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class AnthropicMessagesResponse(BaseModel):
    """Anthropic 消息响应"""

    id: str
    type: str = "message"
    role: str = "assistant"
    content: List[
        Union[AnthropicTextBlock, AnthropicToolUseBlock]
    ]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage


class AnthropicCountTokensRequest(BaseModel):
    """Anthropic 计数 Token 请求"""

    model: str = Field(..., description="模型名称")
    messages: List[AnthropicMessage] = Field(
        ..., description="消息列表"
    )
    system: Optional[
        Union[str, List[AnthropicContentBlock]]
    ] = Field(None, description="系统提示")
    tools: Optional[List[AnthropicTool]] = Field(
        None, description="工具列表"
    )
    tool_choice: Optional[
        Union[AnthropicToolChoice, Dict[str, Any]]
    ] = Field(None, description="工具选择")

    model_config = ConfigDict(extra="allow")


class AnthropicCountTokensResponse(BaseModel):
    """Anthropic 计数 Token 响应"""

    input_tokens: int


class AnthropicErrorDetail(BaseModel):
    """Anthropic 错误详情"""

    type: str
    message: str


class AnthropicErrorResponse(BaseModel):
    """Anthropic 错误响应"""

    type: str = "error"
    error: AnthropicErrorDetail


# ---------- Anthropic 批处理模型 ----------


class AnthropicBatchRequestParams(BaseModel):
    """Anthropic 批处理请求参数"""

    model: str
    max_tokens: int
    messages: List[AnthropicMessage]
    system: Optional[
        Union[str, List[AnthropicContentBlock]]
    ] = None
    stop_sequences: Optional[List[str]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    tools: Optional[List[AnthropicTool]] = None
    tool_choice: Optional[
        Union[AnthropicToolChoice, Dict[str, Any]]
    ] = None
    metadata: Optional[AnthropicMetadata] = None


class AnthropicBatchRequest(BaseModel):
    """Anthropic 批处理请求"""

    custom_id: str = Field(..., description="自定义 ID")
    params: AnthropicBatchRequestParams = Field(
        ..., description="请求参数"
    )


class AnthropicCreateBatchRequest(BaseModel):
    """Anthropic 创建批处理请求"""

    requests: List[AnthropicBatchRequest] = Field(
        ..., description="请求列表"
    )


class AnthropicBatchRequestCounts(BaseModel):
    """Anthropic 批处理请求计数"""

    processing: int
    succeeded: int
    errored: int
    canceled: int
    expired: int


class AnthropicBatchResponse(BaseModel):
    """Anthropic 批处理响应"""

    id: str
    type: str = "message_batch"
    processing_status: str
    request_counts: AnthropicBatchRequestCounts
    ended_at: Optional[str] = None
    created_at: str
    expires_at: str
    cancel_initiated_at: Optional[str] = None
    results_url: Optional[str] = None


class AnthropicBatchListResponse(BaseModel):
    """Anthropic 批处理列表响应"""

    data: List[AnthropicBatchResponse]
    has_more: bool
    first_id: Optional[str] = None
    last_id: Optional[str] = None


class AnthropicFileResponse(BaseModel):
    """Anthropic 文件响应"""

    id: str
    type: str = "file"
    filename: str
    size: int
    created_at: int
    purpose: str = "user_data"


class AnthropicFileListResponse(BaseModel):
    """Anthropic 文件列表响应"""

    data: List[AnthropicFileResponse]
    has_more: bool
    first_id: Optional[str] = None
    last_id: Optional[str] = None


class AnthropicDeletedResponse(BaseModel):
    """Anthropic 删除响应"""

    id: str
    type: str
    deleted: bool = True


class AnthropicModelInfo(BaseModel):
    """Anthropic 模型信息"""

    id: str
    type: str = "model"
    display_name: str
    created_at: str


class AnthropicModelsResponse(BaseModel):
    """Anthropic 模型列表响应"""

    data: List[AnthropicModelInfo]
    has_more: bool
    first_id: Optional[str] = None
    last_id: Optional[str] = None


# ==========================================================================
#  上传文件数据类
# ==========================================================================


@dataclass
class UploadedFile:
    """已上传文件"""

    id: str
    filename: str
    size: int
    content_type: str
    created_at: int
    purpose: str = "user_data"


# ==========================================================================
#  XML 工具描述格式化器
# ==========================================================================


def _format_tool_xml(function: Dict[str, Any]) -> str:
    """将函数定义字典转换为 NousXML 工具描述格式

    生成格式:
    <function>
    <name>function_name</name>
    <description>function description</description>
    <parameters>{...}</parameters>
    </function>
    """
    name = function.get("name", "")
    description = function.get("description", "")
    parameters = json.dumps(
        function.get("parameters", {}), ensure_ascii=False
    )
    return (
        f"<function>\n"
        f"<name>{name}</name>\n"
        f"<description>{description}</description>\n"
        f"<parameters>{parameters}</parameters>\n"
        f"</function>"
    )


def _format_function_call_tag(
    fn_name: str,
    fn_args: str,
    has_code_block: bool = False,
    code_content: Optional[str] = None,
) -> str:
    """将函数名和参数格式化为 NousXML 函数调用标记

    基础格式:
        <function=fn_name>{param: value}</function>
    代码模式格式:
        <function=fn_name>{code: }
        <code>
        code content
        </code>
        </function>
    """
    if has_code_block and code_content is not None:
        return (
            f"{FN_CALL_START_TAG}{fn_name}>{fn_args}\n"
            f"<code>\n{code_content}\n</code>\n"
            f"{FN_CALL_END_TAG}"
        )
    return f"{FN_CALL_START_TAG}{fn_name}>{fn_args}{FN_CALL_END_TAG}"


def _format_tool_response_tag(result_content: str) -> str:
    """将工具执行结果格式化为 NousXML tool_response 标记

    格式:
        <tool_response>
        result content
        </tool_response>
    """
    return (
        f"{TOOL_RESPONSE_START_TAG}\n"
        f"{result_content}\n"
        f"{TOOL_RESPONSE_END_TAG}"
    )


# ==========================================================================
#  QwenFnCall 提示词处理器 (NousXML 格式)
# ==========================================================================


class QwenFnCallPromptProcessor:
    """Qwen 函数调用提示词处理器 (NousXML 格式)

    负责:
    1. 预处理: 将 OpenAI/Anthropic 格式的工具定义和消息历史
       转换为 NousXML fncall 提示词格式
    2. 后处理: 从模型的原始输出中解析出结构化的函数调用，
       转换为 OpenAI tool_calls 或 Anthropic tool_use 格式
    """

    # ------------------------------------------------------------------
    # 系统提示词构建
    # ------------------------------------------------------------------

    @classmethod
    def build_tool_system_prompt(
        cls,
        tools: List[ToolDefinition],
        lang: str = "en",
        parallel_function_calls: bool = True,
    ) -> str:
        """构建 NousXML 风格的工具系统提示词

        将 OpenAI ToolDefinition 列表转换为 NousXML 格式提示词。

        Args:
            tools: OpenAI 格式工具定义列表
            lang: 语言代码 ('en' 或 'zh')
            parallel_function_calls: 是否支持并行调用

        Returns:
            构建好的系统提示词文本
        """
        if not tools:
            return ""

        functions: List[Dict[str, Any]] = []
        tool_names: List[str] = []

        for tool in tools:
            func = tool.function
            func_dict: Dict[str, Any] = {
                "name": func.name,
                "description": func.description or "",
                "parameters": func.parameters
                or {"type": "object", "properties": {}},
            }
            functions.append(func_dict)
            tool_names.append(func.name)

        tool_descs = "\n".join(
            _format_tool_xml(f) for f in functions
        )

        # 检测是否包含 code_interpreter 工具
        has_code_interpreter = SPECIAL_CODE_MODE and any(
            CODE_TOOL_PATTERN in name for name in tool_names
        )

        # 选择模板
        if has_code_interpreter:
            template_key = f"{lang}_ci"
        else:
            template_key = lang

        if template_key not in FN_CALL_TEMPLATE:
            template_key = (
                "en_ci" if has_code_interpreter else "en"
            )

        return FN_CALL_TEMPLATE[template_key].format(
            tool_descs=tool_descs
        )

    @classmethod
    def build_anthropic_tool_system_prompt(
        cls,
        tools: List[AnthropicTool],
        lang: str = "en",
        parallel_function_calls: bool = True,
    ) -> str:
        """构建 NousXML 风格的工具系统提示词 (从 Anthropic 工具定义)

        Args:
            tools: Anthropic 格式工具定义列表
            lang: 语言代码
            parallel_function_calls: 是否支持并行调用

        Returns:
            构建好的系统提示词文本
        """
        if not tools:
            return ""

        functions: List[Dict[str, Any]] = []
        tool_names: List[str] = []

        for tool in tools:
            parameters: Dict[str, Any] = {
                "type": tool.input_schema.type,
                "properties": tool.input_schema.properties
                or {},
            }
            if tool.input_schema.required:
                parameters["required"] = (
                    tool.input_schema.required
                )

            func_dict: Dict[str, Any] = {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": parameters,
            }
            functions.append(func_dict)
            tool_names.append(tool.name)

        tool_descs = "\n".join(
            _format_tool_xml(f) for f in functions
        )

        has_code_interpreter = SPECIAL_CODE_MODE and any(
            CODE_TOOL_PATTERN in name for name in tool_names
        )

        if has_code_interpreter:
            template_key = f"{lang}_ci"
        else:
            template_key = lang

        if template_key not in FN_CALL_TEMPLATE:
            template_key = (
                "en_ci" if has_code_interpreter else "en"
            )

        return FN_CALL_TEMPLATE[template_key].format(
            tool_descs=tool_descs
        )

    # ------------------------------------------------------------------
    # 消息预处理 (OpenAI 格式 -> 纯文本提示词)
    # ------------------------------------------------------------------

    @classmethod
    def preprocess_messages_for_qwen(
        cls,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        lang: str = "en",
        parallel_function_calls: bool = True,
    ) -> str:
        """将 OpenAI 格式的消息列表预处理为 NousXML fncall 格式的纯文本提示词

        处理流程:
        1. 将 tool_calls 消息转为 <function=name>args</function> 文本
        2. 将 tool 角色的结果转为 <tool_response> 文本并合并到 user 消息
        3. 将工具定义注入到 system message
        4. 构建最终发送给 ollama_client 的提示词

        Args:
            messages: OpenAI 格式消息列表
            tools: 工具定义列表
            lang: 语言代码
            parallel_function_calls: 是否支持并行调用

        Returns:
            发送给 ollama_client 的纯文本 prompt
        """
        prompt_parts: List[str] = []
        system_content: str = ""
        processed_messages: List[Dict[str, str]] = []

        for msg in messages:
            role = msg.role.lower()
            content_str = cls._extract_message_content(msg)

            if role == "system":
                system_content = content_str

            elif role == "tool":
                # 工具结果 -> <tool_response> 标记，合并到上一条 user 消息
                tool_result_text = _format_tool_response_tag(
                    content_str
                )
                if (
                    processed_messages
                    and processed_messages[-1]["role"]
                    == "user"
                ):
                    processed_messages[-1]["content"] += (
                        "\n" + tool_result_text
                    )
                else:
                    processed_messages.append(
                        {
                            "role": "user",
                            "content": tool_result_text,
                        }
                    )

            elif role == "assistant":
                assistant_content = content_str

                # 将 tool_calls 转为 NousXML 函数调用标记
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                        if not isinstance(fn_args, str):
                            fn_args = json.dumps(
                                fn_args,
                                ensure_ascii=False,
                            )

                        # 处理 code_interpreter 特殊模式
                        if (
                            SPECIAL_CODE_MODE
                            and CODE_TOOL_PATTERN
                            in fn_name
                        ):
                            fncall_text = cls._format_code_function_call(
                                fn_name, fn_args
                            )
                        else:
                            fncall_text = (
                                _format_function_call_tag(
                                    fn_name, fn_args
                                )
                            )

                        if (
                            assistant_content
                            and not assistant_content.endswith(
                                "\n"
                            )
                        ):
                            assistant_content += "\n"
                        assistant_content += fncall_text

                # 合并连续的 assistant 消息
                if (
                    processed_messages
                    and processed_messages[-1]["role"]
                    == "assistant"
                ):
                    prev = processed_messages[-1]["content"]
                    if prev and not prev.endswith("\n"):
                        processed_messages[-1][
                            "content"
                        ] += "\n"
                    processed_messages[-1]["content"] += (
                        assistant_content
                    )
                else:
                    processed_messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_content,
                        }
                    )

            elif role == "user":
                processed_messages.append(
                    {"role": "user", "content": content_str}
                )

            else:
                # 未知角色当作 user 处理
                processed_messages.append(
                    {"role": "user", "content": content_str}
                )

        # 注入工具系统提示词到 system message
        if tools:
            tool_system = cls.build_tool_system_prompt(
                tools,
                lang=lang,
                parallel_function_calls=parallel_function_calls,
            )
            if system_content:
                system_content = (
                    system_content + "\n\n" + tool_system
                )
            else:
                system_content = tool_system

        # 构建最终提示词
        if system_content:
            prompt_parts.append(
                f"<|system|>\n{system_content}"
            )

        for msg_dict in processed_messages:
            role = msg_dict["role"]
            content = msg_dict["content"]
            if role == "user":
                prompt_parts.append(
                    f"<|user|>\n{content}"
                )
            elif role == "assistant":
                prompt_parts.append(
                    f"<|assistant|>\n{content}"
                )

        return "\n".join(prompt_parts)

    @classmethod
    def preprocess_anthropic_messages_for_qwen(
        cls,
        messages: List[AnthropicMessage],
        system: Optional[
            Union[str, List[AnthropicContentBlock]]
        ] = None,
        tools: Optional[List[AnthropicTool]] = None,
        lang: str = "en",
        parallel_function_calls: bool = True,
    ) -> str:
        """将 Anthropic 格式的消息列表预处理为 NousXML fncall 格式的纯文本提示词"""
        prompt_parts: List[str] = []

        # 处理 system
        system_content: str = ""
        if system:
            if isinstance(system, str):
                system_content = system
            else:
                system_content = (
                    cls._anthropic_blocks_to_text(system)
                )

        # 注入工具系统提示词
        if tools:
            tool_system = (
                cls.build_anthropic_tool_system_prompt(
                    tools,
                    lang=lang,
                    parallel_function_calls=parallel_function_calls,
                )
            )
            if system_content:
                system_content = (
                    system_content + "\n\n" + tool_system
                )
            else:
                system_content = tool_system

        if system_content:
            prompt_parts.append(
                f"<|system|>\n{system_content}"
            )

        # 处理消息
        processed_messages: List[Dict[str, str]] = []

        for msg in messages:
            role = msg.role

            if isinstance(msg.content, str):
                content_text = msg.content
                if role == "user":
                    processed_messages.append(
                        {
                            "role": "user",
                            "content": content_text,
                        }
                    )
                elif role == "assistant":
                    processed_messages.append(
                        {
                            "role": "assistant",
                            "content": content_text,
                        }
                    )
            else:
                # 处理内容块列表
                text_parts: List[str] = []
                tool_call_parts: List[str] = []
                tool_result_parts: List[str] = []

                for block in msg.content:
                    if (
                        block.type == "text"
                        and block.text
                    ):
                        text_parts.append(block.text)

                    elif block.type == "tool_use":
                        func_name = block.name or ""
                        func_input = block.input or {}
                        func_args = json.dumps(
                            func_input,
                            ensure_ascii=False,
                        )

                        if (
                            SPECIAL_CODE_MODE
                            and CODE_TOOL_PATTERN
                            in func_name
                        ):
                            fncall_text = cls._format_code_function_call(
                                func_name, func_args
                            )
                        else:
                            fncall_text = (
                                _format_function_call_tag(
                                    func_name, func_args
                                )
                            )
                        tool_call_parts.append(fncall_text)

                    elif block.type == "tool_result":
                        result_content = ""
                        if isinstance(
                            block.content, str
                        ):
                            result_content = block.content
                        elif isinstance(
                            block.content, list
                        ):
                            result_content = cls._anthropic_blocks_to_text(
                                block.content
                            )
                        tool_result_parts.append(
                            _format_tool_response_tag(
                                result_content
                            )
                        )

                content_str = (
                    "\n".join(text_parts)
                    if text_parts
                    else ""
                )

                if role == "assistant":
                    full_content = content_str
                    if tool_call_parts:
                        if (
                            full_content
                            and not full_content.endswith(
                                "\n"
                            )
                        ):
                            full_content += "\n"
                        full_content += "\n".join(
                            tool_call_parts
                        )

                    if (
                        processed_messages
                        and processed_messages[-1]["role"]
                        == "assistant"
                    ):
                        prev = processed_messages[-1][
                            "content"
                        ]
                        if prev and not prev.endswith(
                            "\n"
                        ):
                            processed_messages[-1][
                                "content"
                            ] += "\n"
                        processed_messages[-1][
                            "content"
                        ] += full_content
                    else:
                        processed_messages.append(
                            {
                                "role": "assistant",
                                "content": full_content,
                            }
                        )

                elif role == "user":
                    if tool_result_parts:
                        result_text = "\n".join(
                            tool_result_parts
                        )

                        if (
                            processed_messages
                            and processed_messages[-1][
                                "role"
                            ]
                            == "user"
                        ):
                            processed_messages[-1][
                                "content"
                            ] += ("\n" + result_text)
                        else:
                            processed_messages.append(
                                {
                                    "role": "user",
                                    "content": result_text,
                                }
                            )

                        if content_str.strip():
                            processed_messages[-1][
                                "content"
                            ] += ("\n" + content_str)
                    else:
                        processed_messages.append(
                            {
                                "role": "user",
                                "content": content_str,
                            }
                        )

        # 构建提示词
        for msg_dict in processed_messages:
            role = msg_dict["role"]
            content = msg_dict["content"]
            if role == "user":
                prompt_parts.append(
                    f"<|user|>\n{content}"
                )
            elif role == "assistant":
                prompt_parts.append(
                    f"<|assistant|>\n{content}"
                )

        return "\n".join(prompt_parts)

    # ------------------------------------------------------------------
    # 响应后处理 (模型原始输出 -> 结构化工具调用)
    # ------------------------------------------------------------------

    @classmethod
    def postprocess_qwen_response(
        cls,
        raw_content: str,
        parallel_function_calls: bool = True,
    ) -> Tuple[Optional[str], Optional[str], List[ToolCall]]:
        """从模型的原始输出中解析 NousXML 函数调用

        Args:
            raw_content: 模型原始输出文本
            parallel_function_calls: 是否解析多个并行函数调用

        Returns:
            (reasoning_content, formal_content, tool_calls) 三元组
        """
        if not raw_content:
            return None, None, []

        # 提取推理内容
        reasoning_content, working_content = (
            ReasoningContentProcessor.extract_reasoning(
                raw_content
            )
        )

        if working_content is None:
            working_content = raw_content

        # 移除不完整的特殊标记
        working_content = (
            cls._remove_incomplete_special_tokens(
                working_content
            )
        )

        # 查找函数调用标记
        fn_marker_pos = working_content.find(
            FN_CALL_START_TAG
        )

        if fn_marker_pos < 0:
            # 没有函数调用
            formal_content = working_content.strip()
            return reasoning_content, formal_content, []

        # 分离思考文本和函数调用
        thought_text = working_content[
            :fn_marker_pos
        ].strip()
        fncall_text = working_content[fn_marker_pos:]

        # 解析函数调用
        tool_calls: List[ToolCall] = []

        # 按 <function= 分割
        parts = fncall_text.split(FN_CALL_START_TAG)

        for part in parts:
            if not part.strip():
                continue

            # 提取函数名: fn_name>...
            gt_idx = part.find(">")
            if gt_idx < 0:
                continue

            fn_name = part[:gt_idx].strip()
            rest = part[gt_idx + 1 :]

            # 提取参数: 在 </function> 之前的内容
            if FN_CALL_END_TAG not in rest:
                fn_args_raw = rest.strip()
            else:
                fn_parts = rest.split(
                    FN_CALL_END_TAG, 1
                )
                fn_args_raw = fn_parts[0].strip()

            # 处理 code_interpreter 特殊模式
            fn_args = cls._extract_function_args(
                fn_name, fn_args_raw
            )

            if not fn_args:
                fn_args = "{}"

            if fn_name:
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:24]}",
                        type="function",
                        function=FunctionCall(
                            name=fn_name,
                            arguments=fn_args,
                        ),
                    )
                )

        # 非并行模式只保留第一个
        if (
            not parallel_function_calls
            and len(tool_calls) > 1
        ):
            tool_calls = tool_calls[:1]

        return (
            reasoning_content,
            thought_text if thought_text else None,
            tool_calls,
        )

    @classmethod
    def postprocess_qwen_response_to_anthropic(
        cls,
        raw_content: str,
        parallel_function_calls: bool = True,
    ) -> Tuple[
        Optional[str],
        List[
            Union[AnthropicTextBlock, AnthropicToolUseBlock]
        ],
    ]:
        """从模型输出解析并转换为 Anthropic 格式

        Args:
            raw_content: 模型原始输出文本
            parallel_function_calls: 是否解析并行调用

        Returns:
            (stop_reason, content_blocks) 二元组
        """
        reasoning_content, formal_content, tool_calls = (
            cls.postprocess_qwen_response(
                raw_content,
                parallel_function_calls=parallel_function_calls,
            )
        )

        content_blocks: List[
            Union[
                AnthropicTextBlock, AnthropicToolUseBlock
            ]
        ] = []

        # 添加文本内容
        text_content = formal_content or ""
        if reasoning_content:
            text_content = (
                f"<thinking>\n{reasoning_content}\n"
                f"</thinking>\n{text_content}"
            )

        if text_content.strip():
            content_blocks.append(
                AnthropicTextBlock(
                    text=text_content.strip()
                )
            )

        if tool_calls:
            for tc in tool_calls:
                try:
                    args = tc.function.arguments
                    if isinstance(args, str):
                        try:
                            args_dict = json.loads(args)
                        except json.JSONDecodeError:
                            args_dict = {"raw": args}
                    else:
                        args_dict = (
                            args
                            if isinstance(args, dict)
                            else {"value": args}
                        )

                    content_blocks.append(
                        AnthropicToolUseBlock(
                            id=f"toolu_{uuid.uuid4().hex[:24]}",
                            name=tc.function.name,
                            input=args_dict,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "转换 Anthropic 工具使用失败: %s",
                        exc,
                    )
                    continue

            stop_reason = (
                AnthropicStopReason.TOOL_USE.value
            )
        else:
            stop_reason = (
                AnthropicStopReason.END_TURN.value
            )

        if not content_blocks:
            content_blocks.append(
                AnthropicTextBlock(text="")
            )

        return stop_reason, content_blocks

    # ------------------------------------------------------------------
    # 流式输出辅助
    # ------------------------------------------------------------------

    @classmethod
    def detect_fncall_in_stream(
        cls, accumulated_text: str
    ) -> bool:
        """检测流式输出中是否包含函数调用标记

        Args:
            accumulated_text: 已积累的输出文本

        Returns:
            是否检测到函数调用标记
        """
        if FN_CALL_START_TAG in accumulated_text:
            return True

        for i in range(1, len(FN_CALL_START_TAG)):
            prefix = FN_CALL_START_TAG[:i]
            if accumulated_text.endswith(prefix):
                return True

        return False

    @classmethod
    def split_stream_content(
        cls,
        accumulated_text: str,
    ) -> Tuple[str, str]:
        """分割流式内容为可显示部分和函数调用缓冲区

        Args:
            accumulated_text: 已积累的输出文本

        Returns:
            (displayable_text, fncall_buffer) 二元组
        """
        fn_pos = accumulated_text.find(FN_CALL_START_TAG)

        if fn_pos < 0:
            for i in range(
                len(FN_CALL_START_TAG) - 1, 0, -1
            ):
                prefix = FN_CALL_START_TAG[:i]
                if accumulated_text.endswith(prefix):
                    return (
                        accumulated_text[: -len(prefix)],
                        prefix,
                    )
            return accumulated_text, ""

        return (
            accumulated_text[:fn_pos],
            accumulated_text[fn_pos:],
        )

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @classmethod
    def _extract_message_content(
        cls, msg: ChatMessage
    ) -> str:
        """提取消息内容为纯文本"""
        if isinstance(msg.content, str):
            return msg.content or ""
        elif isinstance(msg.content, list):
            text_parts: List[str] = []
            for part in msg.content:
                if part.type == "text" and part.text:
                    text_parts.append(part.text)
                elif (
                    part.type == "image_url"
                    and part.image_url
                ):
                    text_parts.append("[Image]")
                elif (
                    part.type == "audio_url"
                    and part.audio_url
                ):
                    text_parts.append("[Audio]")
                elif (
                    part.type == "video_url"
                    and part.video_url
                ):
                    text_parts.append("[Video]")
                elif (
                    part.type == "file_url"
                    and part.file_url
                ):
                    text_parts.append("[File]")
                elif (
                    part.type == "input_audio"
                    and part.input_audio
                ):
                    text_parts.append("[AudioInput]")
            return "\n".join(text_parts)
        return ""

    @classmethod
    def _anthropic_blocks_to_text(
        cls,
        blocks: Union[
            List[AnthropicContentBlock], List[Any]
        ],
    ) -> str:
        """将 Anthropic 内容块列表转换为纯文本"""
        text_parts: List[str] = []

        for block in blocks:
            if isinstance(block, AnthropicContentBlock):
                if block.type == "text" and block.text:
                    text_parts.append(block.text)
                elif block.type == "image":
                    text_parts.append("[Image]")
                elif block.type == "document":
                    text_parts.append("[Document]")
                elif block.type == "tool_use":
                    tool_call = json.dumps(
                        {
                            "name": block.name,
                            "input": block.input,
                        },
                        ensure_ascii=False,
                    )
                    text_parts.append(tool_call)
                elif block.type == "tool_result":
                    result_content = block.content
                    if isinstance(result_content, list):
                        result_text = (
                            cls._anthropic_blocks_to_text(
                                result_content
                            )
                        )
                    else:
                        result_text = (
                            str(result_content)
                            if result_content
                            else ""
                        )
                    text_parts.append(result_text)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text_parts.append(
                        block.get("text", "")
                    )
                elif block_type == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str):
                        text_parts.append(content)
                    elif isinstance(content, list):
                        text_parts.append(
                            cls._anthropic_blocks_to_text(
                                content
                            )
                        )

        return "\n".join(text_parts)

    @classmethod
    def _remove_incomplete_special_tokens(
        cls, text: str
    ) -> str:
        """清理不完整的特殊标记"""
        if not text:
            return text

        text = text.rstrip()

        # 检查文本是否是 '<function=' 的不完整前缀
        if text in FN_CALL_START_TAG:
            text = ""
            return text

        # 检查文本是否以不完整的特殊标记结尾
        special_tokens = (
            FN_CALL_START_TAG,
            FN_CALL_END_TAG,
            TOOL_RESPONSE_START_TAG,
            TOOL_RESPONSE_END_TAG,
        )

        for token in special_tokens:
            for i in range(len(token) - 1, 0, -1):
                prefix = token[:i]
                if text.endswith(prefix):
                    candidate = text[-(len(prefix)) :]
                    if (
                        candidate == prefix
                        and not text.endswith(token)
                    ):
                        text = text[: -len(prefix)]
                        return text.rstrip()

        return text

    @classmethod
    def _extract_function_args(
        cls, fn_name: str, fn_args_raw: str
    ) -> str:
        """提取函数参数，处理 code_interpreter 特殊模式"""
        fn_args = fn_args_raw.strip()

        # 处理 code_interpreter 的 <code> 块
        if (
            SPECIAL_CODE_MODE
            and CODE_TOOL_PATTERN in fn_name
            and "<code>" in fn_args
            and "</code>" in fn_args
        ):
            code_snips = fn_args.split("<code>")
            args_part = code_snips[0].strip()

            try:
                args_dict = json.loads(args_part)
            except (json.JSONDecodeError, ValueError):
                args_dict = {}

            for i in range(1, len(code_snips)):
                code = (
                    code_snips[i]
                    .replace("</code>", "")
                    .strip()
                )
                args_dict["code"] = code

            fn_args = json.dumps(
                args_dict, ensure_ascii=False
            )
        else:
            fn_args = (
                cls._remove_trailing_comment_of_fn_args(
                    fn_args
                )
            )

        return fn_args

    @classmethod
    def _format_code_function_call(
        cls, fn_name: str, fn_args: str
    ) -> str:
        """格式化 code_interpreter 函数调用为含 <code> 块的格式"""
        try:
            args_dict = json.loads(fn_args)
        except (json.JSONDecodeError, ValueError):
            return _format_function_call_tag(
                fn_name, fn_args
            )

        code = args_dict.pop("code", "")
        if code:
            args_str = json.dumps(
                {**args_dict, "code": ""},
                ensure_ascii=False,
            )
            return _format_function_call_tag(
                fn_name,
                args_str,
                has_code_block=True,
                code_content=code,
            )

        return _format_function_call_tag(
            fn_name, fn_args
        )

    @classmethod
    def _remove_trailing_comment_of_fn_args(
        cls, fn_args: str
    ) -> str:
        """移除函数参数末尾的注释"""
        if not fn_args:
            return fn_args

        fn_args = fn_args.strip()

        if fn_args.endswith("}") or fn_args.endswith("]"):
            return fn_args

        last_brace = fn_args.rfind("}")
        last_bracket = fn_args.rfind("]")
        last_json_end = max(last_brace, last_bracket)

        if last_json_end > 0:
            candidate = fn_args[: last_json_end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return fn_args

    @classmethod
    def has_chinese_chars(cls, text: str) -> bool:
        """检测文本中是否包含中文字符"""
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False

    @classmethod
    def detect_language(
        cls,
        messages: Optional[List[ChatMessage]] = None,
        text: Optional[str] = None,
    ) -> str:
        """检测消息的语言，返回 'zh' 或 'en'"""
        if text and cls.has_chinese_chars(text):
            return "zh"

        if messages:
            for msg in messages:
                content_text = (
                    cls._extract_message_content(msg)
                )
                if cls.has_chinese_chars(content_text):
                    return "zh"

        return "en"


# ==========================================================================
#  推理内容处理器
# ==========================================================================


class ReasoningContentProcessor:
    """推理内容处理器

    处理 <think>...</think> 块的提取、检测和合并
    """

    THINK_PATTERN: re.Pattern[str] = re.compile(
        r"<think>(.*?)</think>", re.DOTALL
    )

    @classmethod
    def extract_reasoning(
        cls, content: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """从内容中提取推理内容和正式内容

        Args:
            content: 原始输出内容

        Returns:
            (reasoning_content, formal_content) 二元组
        """
        if not content:
            return None, None

        match = cls.THINK_PATTERN.search(content)

        if match:
            reasoning_content = match.group(1).strip()
            formal_content = cls.THINK_PATTERN.sub(
                "", content
            ).strip()
            return reasoning_content, formal_content
        else:
            return None, content

    @classmethod
    def has_reasoning_content(cls, content: str) -> bool:
        """检查内容是否包含推理内容"""
        if not content:
            return False
        return bool(cls.THINK_PATTERN.search(content))

    @classmethod
    def wrap_reasoning_content(
        cls, reasoning: str
    ) -> str:
        """将推理内容包装在 think 标签中"""
        return f"<think>{reasoning}</think>"

    @classmethod
    def merge_content(
        cls,
        reasoning_content: Optional[str],
        formal_content: Optional[str],
    ) -> str:
        """合并推理内容和正式内容"""
        parts: List[str] = []
        if reasoning_content:
            parts.append(
                cls.wrap_reasoning_content(
                    reasoning_content
                )
            )
        if formal_content:
            parts.append(formal_content)
        return "\n".join(parts)


# ==========================================================================
#  工具调用处理器 (兼容层)
# ==========================================================================


class ToolCallProcessor:
    """工具调用处理器

    提供兼容处理能力:
    - 从 NousXML 格式解析工具调用
    - 从 JSON 格式解析工具调用 (向后兼容)
    - 过滤流式输出中的工具调用内容
    """

    @classmethod
    def generate_tool_call_id(cls) -> str:
        """生成工具调用 ID"""
        return f"call_{uuid.uuid4().hex[:24]}"

    @classmethod
    def generate_anthropic_tool_id(cls) -> str:
        """生成 Anthropic 工具 ID"""
        return f"toolu_{uuid.uuid4().hex[:24]}"

    @classmethod
    def extract_tool_calls(
        cls,
        content: str,
    ) -> Tuple[str, List[ToolCall]]:
        """从内容中提取工具调用

        优先使用 NousXML 格式解析，
        如果没有 XML 标记则回退到 JSON 格式解析。

        Args:
            content: 模型输出内容

        Returns:
            (cleaned_content, tool_calls) 二元组
        """
        if not content:
            return "", []

        # 优先检查 NousXML 格式
        if FN_CALL_START_TAG in content:
            _, formal_content, tool_calls = (
                QwenFnCallPromptProcessor.postprocess_qwen_response(
                    content
                )
            )
            return formal_content or "", tool_calls

        # 回退到 JSON 格式解析
        content = content.strip()
        tool_calls: List[ToolCall] = []

        try:
            data = json.loads(content)
            calls = cls._extract_tool_calls_from_data(data)
            if calls:
                return "", calls
        except json.JSONDecodeError:
            pass

        # 尝试在代码块中查找
        code_blocks = re.findall(
            r"```(?:json)?\s*([\s\S]*?)\s*```", content
        )
        for block in code_blocks:
            try:
                data = json.loads(block.strip())
                calls = cls._extract_tool_calls_from_data(
                    data
                )
                if calls:
                    content = content.replace(
                        f"```json\n{block}\n```", ""
                    )
                    content = content.replace(
                        f"```\n{block}\n```", ""
                    )
                    tool_calls.extend(calls)
            except json.JSONDecodeError:
                continue

        cleaned_content = cls.filter_tool_content(content)
        return cleaned_content, tool_calls

    @classmethod
    def extract_anthropic_tool_uses(
        cls,
        content: str,
    ) -> Tuple[str, List[AnthropicToolUseBlock]]:
        """提取 Anthropic 工具使用"""
        cleaned_content, tool_calls = (
            cls.extract_tool_calls(content)
        )

        tool_uses: List[AnthropicToolUseBlock] = []
        for tc in tool_calls:
            try:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_use = AnthropicToolUseBlock(
                    id=cls.generate_anthropic_tool_id(),
                    name=tc.function.name,
                    input=(
                        args
                        if isinstance(args, dict)
                        else {"value": args}
                    ),
                )
                tool_uses.append(tool_use)
            except Exception as exc:
                logger.warning(
                    "转换 Anthropic 工具使用失败: %s", exc
                )
                continue

        return cleaned_content, tool_uses

    @classmethod
    def filter_tool_content(cls, text: str) -> str:
        """过滤掉工具调用内容，保留正常文本"""
        if not text:
            return text

        text = text.strip()

        # 移除 NousXML 函数调用标记
        text = re.sub(
            r"<function=[^>]*>[\s\S]*?</function>",
            "",
            text,
        )

        # 移除不完整的 <function= 标记
        fn_pos = text.find(FN_CALL_START_TAG)
        if fn_pos >= 0:
            text = text[:fn_pos].strip()

        # 移除 <tool_response>...</tool_response> 块
        text = re.sub(
            r"<tool_response>[\s\S]*?</tool_response>",
            "",
            text,
        )

        # 检查是否是完整的 JSON 工具调用
        if cls._is_complete_tool_call_json(text):
            return ""

        result = text.strip()
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    @classmethod
    def _is_complete_tool_call_json(
        cls, text: str
    ) -> bool:
        """检查是否是完整的工具调用 JSON"""
        if not text:
            return False
        text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False
        return cls._is_tool_call_structure(data)

    @classmethod
    def _is_tool_call_dict(cls, data: dict) -> bool:
        """检查字典是否是工具调用"""
        if not isinstance(data, dict):
            return False
        if "name" not in data:
            return False
        if not any(
            key in data
            for key in ("arguments", "parameters", "input")
        ):
            return False
        return True

    @classmethod
    def _is_tool_call_structure(cls, data: Any) -> bool:
        """检查数据结构是否是工具调用"""
        if isinstance(data, dict):
            if cls._is_tool_call_dict(data):
                return True
            if "tool_calls" in data and isinstance(
                data["tool_calls"], list
            ):
                return all(
                    cls._is_tool_call_structure(item)
                    for item in data["tool_calls"]
                )
            if "function_call" in data and isinstance(
                data["function_call"], dict
            ):
                return "name" in data["function_call"]
        elif isinstance(data, list):
            if len(data) == 0:
                return False
            return all(
                cls._is_tool_call_structure(item)
                for item in data
            )
        return False

    @classmethod
    def _extract_tool_calls_from_data(
        cls, data: Any
    ) -> List[ToolCall]:
        """从数据中提取工具调用"""
        tool_calls: List[ToolCall] = []

        if isinstance(data, dict):
            if cls._is_tool_call_dict(data):
                name = data.get("name", "")
                args = data.get(
                    "arguments",
                    data.get(
                        "parameters",
                        data.get("input", {}),
                    ),
                )
                if isinstance(args, dict):
                    args_str = json.dumps(
                        args, ensure_ascii=False
                    )
                else:
                    args_str = str(args)
                tool_calls.append(
                    ToolCall(
                        id=cls.generate_tool_call_id(),
                        type="function",
                        function=FunctionCall(
                            name=name,
                            arguments=args_str,
                        ),
                    )
                )
            elif "tool_calls" in data and isinstance(
                data["tool_calls"], list
            ):
                for tc_data in data["tool_calls"]:
                    if isinstance(tc_data, dict):
                        func = tc_data.get(
                            "function", tc_data
                        )
                        name = func.get("name", "")
                        args = func.get("arguments", {})
                        if isinstance(args, dict):
                            args_str = json.dumps(
                                args, ensure_ascii=False
                            )
                        else:
                            args_str = str(args)
                        tool_calls.append(
                            ToolCall(
                                id=cls.generate_tool_call_id(),
                                type="function",
                                function=FunctionCall(
                                    name=name,
                                    arguments=args_str,
                                ),
                            )
                        )
        elif isinstance(data, list):
            for item in data:
                if isinstance(
                    item, dict
                ) and cls._is_tool_call_dict(item):
                    name = item.get("name", "")
                    args = item.get(
                        "arguments",
                        item.get(
                            "parameters",
                            item.get("input", {}),
                        ),
                    )
                    if isinstance(args, dict):
                        args_str = json.dumps(
                            args, ensure_ascii=False
                        )
                    else:
                        args_str = str(args)
                    tool_calls.append(
                        ToolCall(
                            id=cls.generate_tool_call_id(),
                            type="function",
                            function=FunctionCall(
                                name=name,
                                arguments=args_str,
                            ),
                        )
                    )

        return tool_calls

    @classmethod
    def format_tools_for_prompt(
        cls, tools: List[ToolDefinition]
    ) -> str:
        """格式化工具为 NousXML 提示词"""
        return QwenFnCallPromptProcessor.build_tool_system_prompt(
            tools, lang="en", parallel_function_calls=True
        )

    @classmethod
    def format_anthropic_tools_for_prompt(
        cls, tools: List[AnthropicTool]
    ) -> str:
        """格式化 Anthropic 工具为 NousXML 提示词"""
        return QwenFnCallPromptProcessor.build_anthropic_tool_system_prompt(
            tools, lang="en", parallel_function_calls=True
        )

    @classmethod
    def format_tool_results_for_prompt(
        cls,
        tool_call_id: str,
        result: str,
        is_error: bool = False,
    ) -> str:
        """格式化工具结果为 NousXML tool_response 格式"""
        return _format_tool_response_tag(result)


# ==========================================================================
#  消息文件提取器
# ==========================================================================


class MessageFileExtractor:
    """消息文件提取器"""

    @classmethod
    def extract_files_from_messages(
        cls,
        messages: List[ChatMessage],
    ) -> List[Any]:
        """从消息中提取文件 (Ollama 中不需要上传文件，返回空列表)"""
        return []

    @classmethod
    def extract_files_from_anthropic_messages(
        cls,
        messages: List[AnthropicMessage],
    ) -> List[Any]:
        """从 Anthropic 消息中提取文件 (Ollama 中不需要上传文件，返回空列表)"""
        return []


# ==========================================================================
#  Anthropic 消息转换器
# ==========================================================================


class AnthropicMessageConverter:
    """Anthropic 消息转换器

    将 Anthropic 格式的消息转换为 NousXML fncall 格式的提示词
    """

    @classmethod
    def anthropic_to_prompt(
        cls,
        messages: List[AnthropicMessage],
        system: Optional[
            Union[str, List[AnthropicContentBlock]]
        ] = None,
        tools: Optional[List[AnthropicTool]] = None,
    ) -> str:
        """将 Anthropic 消息转换为 NousXML fncall 格式提示词"""
        # 检测语言
        lang = "en"
        for msg in messages:
            if isinstance(msg.content, str):
                if QwenFnCallPromptProcessor.has_chinese_chars(
                    msg.content
                ):
                    lang = "zh"
                    break
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if (
                        isinstance(
                            block, AnthropicContentBlock
                        )
                        and block.type == "text"
                        and block.text
                    ):
                        if QwenFnCallPromptProcessor.has_chinese_chars(
                            block.text
                        ):
                            lang = "zh"
                            break
                if lang == "zh":
                    break

        return QwenFnCallPromptProcessor.preprocess_anthropic_messages_for_qwen(
            messages=messages,
            system=system,
            tools=tools,
            lang=lang,
            parallel_function_calls=True,
        )

    @classmethod
    def _blocks_to_text(
        cls, blocks: List[AnthropicContentBlock]
    ) -> str:
        """将内容块列表转换为文本"""
        return QwenFnCallPromptProcessor._anthropic_blocks_to_text(
            blocks
        )


# ==========================================================================
#  消息批次存储
# ==========================================================================


class MessageBatchStore:
    """消息批次存储"""

    def __init__(self) -> None:
        self._batches: Dict[str, Dict[str, Any]] = {}
        self._lock: Lock = Lock()

    async def create_batch(
        self,
        requests: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """创建批次"""
        async with self._lock:
            batch_id = (
                f"msgbatch_{uuid.uuid4().hex[:24]}"
            )
            created_at = datetime.now(
                timezone.utc
            ).isoformat()

            batch: Dict[str, Any] = {
                "id": batch_id,
                "type": "message_batch",
                "processing_status": "in_progress",
                "request_counts": {
                    "processing": len(requests),
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 0,
                    "expired": 0,
                },
                "ended_at": None,
                "created_at": created_at,
                "expires_at": (
                    datetime.now(timezone.utc).replace(
                        hour=23,
                        minute=59,
                        second=59,
                    )
                    + timedelta(days=1)
                ).isoformat(),
                "cancel_initiated_at": None,
                "results_url": None,
                "_requests": requests,
                "_results": [],
            }

            self._batches[batch_id] = batch
            return batch

    async def get_batch(
        self, batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取批次"""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if batch:
                return {
                    k: v
                    for k, v in batch.items()
                    if not k.startswith("_")
                }
            return None

    async def list_batches(
        self,
        limit: int = 20,
        before_id: Optional[str] = None,
        after_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出批次"""
        async with self._lock:
            batches = list(self._batches.values())
            batches.sort(
                key=lambda x: x["created_at"],
                reverse=True,
            )

            if after_id:
                idx = next(
                    (
                        i
                        for i, b in enumerate(batches)
                        if b["id"] == after_id
                    ),
                    -1,
                )
                if idx >= 0:
                    batches = batches[:idx]

            if before_id:
                idx = next(
                    (
                        i
                        for i, b in enumerate(batches)
                        if b["id"] == before_id
                    ),
                    -1,
                )
                if idx >= 0:
                    batches = batches[idx + 1 :]

            batches = batches[:limit]

            return [
                {
                    k: v
                    for k, v in b.items()
                    if not k.startswith("_")
                }
                for b in batches
            ]

    async def cancel_batch(
        self, batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """取消批次"""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return None

            if batch["processing_status"] in (
                "ended",
                "canceled",
            ):
                return {
                    k: v
                    for k, v in batch.items()
                    if not k.startswith("_")
                }

            batch["processing_status"] = "canceling"
            batch["cancel_initiated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return {
                k: v
                for k, v in batch.items()
                if not k.startswith("_")
            }

    async def delete_batch(
        self, batch_id: str
    ) -> bool:
        """删除批次"""
        async with self._lock:
            if batch_id in self._batches:
                del self._batches[batch_id]
                return True
            return False

    async def get_batch_results(
        self,
        batch_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取批次结果"""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                return None
            return batch.get("_results", [])

    async def update_batch_result(
        self,
        batch_id: str,
        custom_id: str,
        result: Dict[str, Any],
    ) -> None:
        """更新批次结果"""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if batch:
                batch["_results"].append(
                    {
                        "custom_id": custom_id,
                        "result": result,
                    }
                )

                if result.get("type") == "succeeded":
                    batch["request_counts"][
                        "succeeded"
                    ] += 1
                else:
                    batch["request_counts"]["errored"] += 1

                batch["request_counts"]["processing"] -= 1

                if (
                    batch["request_counts"]["processing"]
                    == 0
                ):
                    batch[
                        "processing_status"
                    ] = "ended"
                    batch[
                        "ended_at"
                    ] = datetime.now(
                        timezone.utc
                    ).isoformat()


# ==========================================================================
#  Anthropic 文件存储
# ==========================================================================


class AnthropicFileStore:
    """Anthropic 文件存储"""

    def __init__(
        self, storage_dir: Optional[Path] = None
    ) -> None:
        self._files: Dict[str, UploadedFile] = {}
        self._file_contents: Dict[str, bytes] = {}
        self._lock: Lock = Lock()
        self._storage_dir = storage_dir or Path(
            "data/anthropic_files"
        )
        self._storage_dir.mkdir(
            parents=True, exist_ok=True
        )

    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        purpose: str = "user_data",
    ) -> UploadedFile:
        """上传文件"""
        async with self._lock:
            file_id = f"file_{uuid.uuid4().hex[:24]}"
            created_at = int(time.time())

            file_path = self._storage_dir / file_id
            with open(file_path, "wb") as f:
                f.write(content)

            uploaded_file = UploadedFile(
                id=file_id,
                filename=filename,
                size=len(content),
                content_type=content_type,
                created_at=created_at,
                purpose=purpose,
            )

            self._files[file_id] = uploaded_file
            self._file_contents[file_id] = content

            return uploaded_file

    async def get_file(
        self, file_id: str
    ) -> Optional[UploadedFile]:
        """获取文件"""
        async with self._lock:
            return self._files.get(file_id)

    async def get_file_content(
        self, file_id: str
    ) -> Optional[bytes]:
        """获取文件内容"""
        async with self._lock:
            if file_id in self._file_contents:
                return self._file_contents[file_id]

            file_path = self._storage_dir / file_id
            if file_path.exists():
                with open(file_path, "rb") as f:
                    content = f.read()
                self._file_contents[file_id] = content
                return content

            return None

    async def list_files(
        self,
        limit: int = 100,
        after_id: Optional[str] = None,
    ) -> List[UploadedFile]:
        """列出文件"""
        async with self._lock:
            files = list(self._files.values())
            files.sort(
                key=lambda x: x.created_at, reverse=True
            )

            if after_id:
                idx = next(
                    (
                        i
                        for i, f in enumerate(files)
                        if f.id == after_id
                    ),
                    -1,
                )
                if idx >= 0:
                    files = files[idx + 1 :]

            return files[:limit]

    async def delete_file(
        self, file_id: str
    ) -> bool:
        """删除文件"""
        async with self._lock:
            if file_id not in self._files:
                return False

            del self._files[file_id]
            if file_id in self._file_contents:
                del self._file_contents[file_id]

            file_path = self._storage_dir / file_id
            if file_path.exists():
                file_path.unlink()

            return True


# ==========================================================================
#  ID 生成器
# ==========================================================================


class IDGenerator:
    """ID 生成器工具类"""

    @staticmethod
    def generate_completion_id() -> str:
        """生成补全 ID"""
        return f"chatcmpl-{uuid.uuid4().hex[:24]}"

    @staticmethod
    def generate_anthropic_message_id() -> str:
        """生成 Anthropic 消息 ID"""
        return f"msg_{uuid.uuid4().hex[:24]}"

    @staticmethod
    def generate_system_fingerprint() -> str:
        """生成系统指纹"""
        return f"fp_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def generate_response_id() -> str:
        """生成响应 ID"""
        return f"resp_{uuid.uuid4().hex[:24]}"

    @staticmethod
    def generate_file_id() -> str:
        """生成文件 ID"""
        return f"file_{uuid.uuid4().hex[:24]}"

    @staticmethod
    def generate_batch_id() -> str:
        """生成批次 ID"""
        return f"msgbatch_{uuid.uuid4().hex[:24]}"


# ==========================================================================
#  消息构建器
# ==========================================================================


class MessageBuilder:
    """消息构建器 - 使用 NousXML fncall 格式构建提示词

    核心职责:
    将 OpenAI 格式的 ChatMessage 列表 (包含 tools) 转换为
    模型能理解的纯文本提示词 (含 <function=...> 标记)
    """

    @classmethod
    def build_prompt_from_messages(
        cls,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> str:
        """从消息构建 NousXML fncall 格式提示词

        Args:
            messages: OpenAI 格式消息列表
            tools: 工具定义列表

        Returns:
            NousXML 格式的纯文本提示词
        """
        lang = QwenFnCallPromptProcessor.detect_language(
            messages=messages
        )

        return QwenFnCallPromptProcessor.preprocess_messages_for_qwen(
            messages=messages,
            tools=tools,
            lang=lang,
            parallel_function_calls=True,
        )

    @classmethod
    def _extract_message_content(
        cls, msg: ChatMessage
    ) -> str:
        """提取消息内容"""
        return QwenFnCallPromptProcessor._extract_message_content(
            msg
        )

    @classmethod
    def _format_tool_calls(
        cls,
        tool_calls: List[ToolCall],
    ) -> List[Dict[str, Any]]:
        """格式化工具调用"""
        result: List[Dict[str, Any]] = []
        for tc in tool_calls:
            try:
                args = (
                    json.loads(tc.function.arguments)
                    if isinstance(
                        tc.function.arguments, str
                    )
                    else tc.function.arguments
                )
            except json.JSONDecodeError:
                args = tc.function.arguments
            result.append(
                {
                    "name": tc.function.name,
                    "arguments": args,
                }
            )
        return result


# ==========================================================================
#  导出
# ==========================================================================

__all__ = [
    # NousXML FnCall 常量
    "FN_CALL_START_TAG",
    "FN_CALL_END_TAG",
    "TOOL_RESPONSE_START_TAG",
    "TOOL_RESPONSE_END_TAG",
    "TOOLS_START_TAG",
    "TOOLS_END_TAG",
    "FN_STOP_WORDS",
    "SPECIAL_CODE_MODE",
    "CODE_TOOL_PATTERN",
    # 向后兼容别名
    "FN_NAME",
    "FN_ARGS",
    "FN_RESULT",
    "FN_EXIT",
    # 模板
    "FN_CALL_TEMPLATE",
    # 格式化辅助函数
    "_format_tool_xml",
    "_format_function_call_tag",
    "_format_tool_response_tag",
    # 配置
    "ServerConfig",
    # 枚举
    "AnthropicStopReason",
    "AnthropicContentType",
    "AnthropicMessageRole",
    "AnthropicBetaFeature",
    # OpenAI 兼容模型
    "ImageURL",
    "AudioURL",
    "VideoURL",
    "FileURL",
    "InputAudio",
    "ContentPart",
    "FunctionCall",
    "ToolCall",
    "ToolCallChunk",
    "ChatMessage",
    "FunctionDefinition",
    "ToolDefinition",
    "ResponseFormat",
    "ChatCompletionRequest",
    "ChatCompletionMessageResponse",
    "ChatCompletionChoice",
    "ChatCompletionUsage",
    "ChatCompletionResponse",
    "ChatCompletionChunkDelta",
    "ChatCompletionChunkChoice",
    "ChatCompletionChunk",
    "ImageGenerationRequest",
    "ImageData",
    "ImageGenerationResponse",
    "ModelInfo",
    "ModelsResponse",
    "ErrorDetail",
    "ErrorResponse",
    "ResponsesRequest",
    # 嵌入请求/响应
    "EmbeddingRequest",
    "EmbeddingData",
    "EmbeddingUsage",
    "EmbeddingResponse",
    # Anthropic 模型
    "AnthropicImageSource",
    "AnthropicDocumentSource",
    "AnthropicContentBlock",
    "AnthropicMessage",
    "AnthropicToolInputSchema",
    "AnthropicTool",
    "AnthropicToolChoice",
    "AnthropicMetadata",
    "AnthropicMessagesRequest",
    "AnthropicUsage",
    "AnthropicTextBlock",
    "AnthropicToolUseBlock",
    "AnthropicMessagesResponse",
    "AnthropicCountTokensRequest",
    "AnthropicCountTokensResponse",
    "AnthropicErrorDetail",
    "AnthropicErrorResponse",
    # Anthropic 批处理
    "AnthropicBatchRequestParams",
    "AnthropicBatchRequest",
    "AnthropicCreateBatchRequest",
    "AnthropicBatchRequestCounts",
    "AnthropicBatchResponse",
    "AnthropicBatchListResponse",
    "AnthropicFileResponse",
    "AnthropicFileListResponse",
    "AnthropicDeletedResponse",
    "AnthropicModelInfo",
    "AnthropicModelsResponse",
    # 数据类
    "UploadedFile",
    # 处理器
    "QwenFnCallPromptProcessor",
    "ToolCallProcessor",
    "ReasoningContentProcessor",
    "MessageFileExtractor",
    "AnthropicMessageConverter",
    # 存储
    "MessageBatchStore",
    "AnthropicFileStore",
    # 工具类
    "IDGenerator",
    "MessageBuilder",
]
